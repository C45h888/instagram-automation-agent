"""
Agent Service
==============
Lightweight LLM+tools layer using llm.bind_tools() (NOT AgentExecutor).
Single-pass: LLM receives tools -> may call them -> we execute -> return result.

Features:
  - asyncio.Semaphore to limit concurrent Ollama inferences
  - ChatOllama with sync invoke() wrapped in asyncio.to_thread()
  - Parallel tool execution via asyncio.gather()
  - Per-tool timeout with graceful fallback

Upgrade path: If multi-step reasoning is needed later, swap to AgentExecutor.
The tools and prompts are already compatible.
"""

import asyncio
import json
import os
import random
import time

from config import llm, logger
from prompts import SYSTEM_PROMPT
from metrics import TOOL_CALLS, LLM_ERRORS
from services.llm_service import LLMService

# Configurable max concurrent LLM inferences (protects Ollama CPU)
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))
_llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

# Per-tool timeout in seconds
TOOL_TIMEOUT_SECONDS = 5.0

# ================================
# Scoped Tool Sets
# ================================
# Import individual tools directly (not from tools/__init__.py which only has lists).
# This avoids circular import issues — automation_tools now routes through LLMService
# directly (no AgentService dependency), and supabase_tools uses lazy imports.
from tools.supabase_tools import (
    get_post_context_tool,
    get_account_info_tool,
    get_recent_comments_tool,
    get_dm_history_tool,
    get_dm_conversation_context_tool,
    get_post_performance_tool,
    log_decision_tool,
)
from tools.automation_tools import (
    analyze_message_tool,
    reply_to_comment_tool,
    reply_to_dm_tool,
)

ENGAGEMENT_SCOPE_TOOLS = [
    # Supabase read tools needed for engagement analysis
    get_post_context_tool,
    get_account_info_tool,
    get_recent_comments_tool,
    log_decision_tool,
    # Automation execution tools
    analyze_message_tool,
    reply_to_comment_tool,
    reply_to_dm_tool,
]

CONTENT_SCOPE_TOOLS = [
    get_post_context_tool,
    get_account_info_tool,
    get_post_performance_tool,
    log_decision_tool,
]

ATTRIBUTION_SCOPE_TOOLS = [
    get_dm_history_tool,
    get_account_info_tool,
    log_decision_tool,
]

SCOPED_TOOLS = {
    "engagement": ENGAGEMENT_SCOPE_TOOLS,
    "content": CONTENT_SCOPE_TOOLS,
    "attribution": ATTRIBUTION_SCOPE_TOOLS,
}


class AgentService:
    """Invoke LLM with bound tools for context-aware analysis and automation.

    Args:
        scope: One of "engagement", "content", "attribution". Takes precedence
               over the tools parameter if both are provided.
        tools: Explicit list of tools to bind. Used when scope is None.
               Defaults to all tools if neither scope nor tools is provided.
    """

    def __init__(self, scope: str = None, tools: list = None):
        if scope is not None and scope in SCOPED_TOOLS:
            tool_list = SCOPED_TOOLS[scope]
        elif tools is not None:
            tool_list = tools
        else:
            # Backward compatibility: default to ALL_TOOLS
            from tools import ALL_TOOLS
            tool_list = ALL_TOOLS

        self.llm_with_tools = llm.bind_tools(tool_list)
        self._tool_map = {t.name: t for t in tool_list}
        self._scope = scope
        logger.info(
            f"AgentService initialized (scope={scope or 'none'}, tools={len(tool_list)}): "
            f"{list(self._tool_map.keys())}"
        )

    async def analyze_async(self, prompt: str) -> dict:
        """Async entry point with semaphore-limited concurrency.

        Uses ChatOllama.invoke() wrapped in asyncio.to_thread().
        Tools execute in parallel via asyncio.gather().
        At most MAX_CONCURRENT_LLM inferences run simultaneously.
        """
        async with _llm_semaphore:
            return await self._analyze(prompt)

    async def astream_analyze(self, prompt: str, on_event=None):
        """Async streaming entry point with semaphore-limited concurrency.

        Args:
            prompt: Prompt to send to LLM
            on_event: Optional async callback(event: dict) for tool_call/tool_done events

        Yields:
            str: Text chunks from the LLM response
        """
        async with _llm_semaphore:
            async for chunk in self._astream(prompt, on_event=on_event):
                yield chunk

    async def _analyze(self, prompt: str) -> dict:
        """Async LLM invocation with parallel tool execution.

        Flow:
          1. Send prompt to LLM with tools bound (retry via LLMService.invoke)
          2. If LLM requests tool calls, execute them in parallel
          3. If tools were called, do follow-up invoke with results (retry via LLMService.invoke)
          4. Parse final response as JSON

        Returns dict with parsed result or error info.
        """
        start_time = time.time()

        try:
            # Prepend system prompt for consistent behavior
            full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

            # Step 1: Invoke LLM with tools (retry via LLMService.invoke)
            result = await LLMService.invoke(full_prompt, llm_instance=self.llm_with_tools)
            tool_calls = getattr(result, "tool_calls", [])

            # Step 2: Execute tool calls in parallel if any
            tool_outputs = {}
            if tool_calls:
                tool_outputs = await self._execute_tool_calls_async(tool_calls)

                # If tools were called, do a follow-up invoke with tool results as context (retry via LLMService.invoke)
                if tool_outputs:
                    enriched_prompt = self._build_enriched_prompt(full_prompt, tool_outputs)
                    result = await LLMService.invoke(enriched_prompt, llm_instance=self.llm_with_tools)

            latency_ms = int((time.time() - start_time) * 1000)

            # Step 3: Parse response
            raw_text = result.content if hasattr(result, "content") else str(result)
            parsed = self._parse_json_response(raw_text)
            parsed["_latency_ms"] = latency_ms
            parsed["_tools_called"] = list(tool_outputs.keys()) if tool_outputs else []

            return parsed

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"AgentService analysis failed (latency={latency_ms}ms): {e}")
            LLM_ERRORS.labels(error_type="agent_execution_failed").inc()
            return {
                "error": "agent_execution_failed",
                "message": str(e),
                "_latency_ms": latency_ms,
            }

    async def _astream(self, prompt: str, on_event=None):
        """Async streaming LLM invocation with tool support and retry.

        Flow:
          1. Stream first pass — yields tokens to caller in real time while accumulating
             chunks for tool call detection. Retries on transient failures.
          2. If tool calls detected in accumulated result: execute tools, stream second
             pass with enriched context. Tool outputs injected via _build_enriched_prompt.
          3. If no tool calls: stream is already complete, response delivered in step 1.

        Path A (no tools): single streaming pass, first token arrives immediately.
        Path B (tools needed): first pass accumulates tool call JSON (no text tokens),
        tools execute, second streaming pass delivers the final answer.

        Retry: Streaming retry restarts the entire pass from the beginning. This is
        acceptable because we can't buffer mid-stream — client may have received partial
        tokens from the failed pass, but the retry delivers fresh tokens from start.
        """
        start_time = time.time()
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        # ─── Streaming pass helper with retry ─────────────────────────────────
        async def _stream_pass(prompt_text: str, pass_label: str):
            """Stream a single pass with exponential-backoff retry.

            Yields text chunks to the outer caller in real time.
            Returns the accumulated AIMessageChunk so the caller can read tool_calls.
            """
            accumulated = None

            for attempt in range(LLMService.DEFAULT_MAX_RETRIES):
                try:
                    async for chunk in self.llm_with_tools.astream(prompt_text):
                        text = chunk.content if hasattr(chunk, "content") else ""
                        if text:
                            yield text
                        accumulated = chunk if accumulated is None else accumulated + chunk
                    break  # success — exit retry loop

                except Exception as e:
                    if not LLMService._is_retryable(e):
                        logger.error(f"[_astream] {pass_label} failed (non-retryable): {e}")
                        raise

                    if attempt == LLMService.DEFAULT_MAX_RETRIES - 1:
                        logger.error(
                            f"[_astream] {pass_label} exhausted {LLMService.DEFAULT_MAX_RETRIES} attempts: {e}"
                        )
                        raise

                    delay = (
                        LLMService.DEFAULT_BASE_DELAY * (2 ** attempt)
                        + random.uniform(0, LLMService.JITTER_RANGE)
                    )
                    logger.warning(
                        f"[_astream] {pass_label} failed (attempt {attempt + 1}/"
                        f"{LLMService.DEFAULT_MAX_RETRIES}), retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    accumulated = None  # reset — stream restarts from beginning

            # Return accumulated so caller can read tool_calls
            return accumulated

        # ─── Pass 1 ────────────────────────────────────────────────────────────
        try:
            accumulated = await _stream_pass(full_prompt, "pass-1")
            tool_calls = getattr(accumulated, "tool_calls", []) if accumulated else []

            # ─── Tool execution ───────────────────────────────────────────────
            tool_outputs = {}
            if tool_calls:
                for call in tool_calls:
                    tool_name = (
                        call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                    )
                    if on_event:
                        await on_event({"event_type": "tool_call", "tool_name": tool_name})

                tool_start = time.time()
                tool_outputs = await self._execute_tool_calls_async(tool_calls)
                tool_elapsed_ms = int((time.time() - tool_start) * 1000)

                for call in tool_calls:
                    tool_name = (
                        call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                    )
                    if on_event:
                        await on_event(
                            {"event_type": "tool_done", "tool_name": tool_name, "elapsed_ms": tool_elapsed_ms}
                        )

                # ─── Pass 2 ─────────────────────────────────────────────────
                if tool_outputs:
                    enriched_prompt = self._build_enriched_prompt(full_prompt, tool_outputs)
                    await _stream_pass(enriched_prompt, "pass-2")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"AgentService stream failed (latency={latency_ms}ms): {e}")
            LLM_ERRORS.labels(error_type="agent_stream_failed").inc()
            yield json.dumps({"error": "agent_stream_failed", "message": str(e)})

    async def _execute_tool_calls_async(self, tool_calls: list) -> dict:
        """Execute tool calls in parallel with timeout handling.

        Each tool is wrapped in asyncio.wait_for with TOOL_TIMEOUT_SECONDS.
        On timeout, returns a fallback error response instead of blocking.
        """
        async def execute_single_tool(call) -> tuple[str, dict]:
            """Execute a single tool with timeout protection."""
            tool_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            tool_args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})

            tool = self._tool_map.get(tool_name)
            if not tool:
                logger.warning(f"LLM requested unknown tool: {tool_name}")
                return tool_name, {"error": "unknown_tool", "message": f"Tool '{tool_name}' not found"}

            try:
                # Run sync tool in thread pool with timeout
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool.invoke, tool_args),
                    timeout=TOOL_TIMEOUT_SECONDS
                )
                logger.info(f"Tool '{tool_name}' executed successfully")
                TOOL_CALLS.labels(tool_name=tool_name).inc()
                return tool_name, result

            except asyncio.TimeoutError:
                logger.warning(f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT_SECONDS}s")
                TOOL_CALLS.labels(tool_name=f"{tool_name}_timeout").inc()
                return tool_name, {
                    "error": "timeout",
                    "message": f"Tool '{tool_name}' timed out after {TOOL_TIMEOUT_SECONDS}s"
                }
            except Exception as e:
                logger.error(f"Tool '{tool_name}' failed: {e}")
                TOOL_CALLS.labels(tool_name=f"{tool_name}_error").inc()
                return tool_name, {"error": str(e)}

        # Execute all tools in parallel
        tasks = [execute_single_tool(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results, handling any unexpected exceptions
        outputs = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected tool execution error: {result}")
                continue
            tool_name, output = result
            if tool_name:
                outputs[tool_name] = output

        return outputs

    def _build_enriched_prompt(self, original_prompt: str, tool_outputs: dict) -> str:
        """Append tool results to the original prompt for a follow-up invoke."""
        context_parts = [original_prompt, "\n\n--- TOOL RESULTS ---"]
        for tool_name, output in tool_outputs.items():
            serialized = json.dumps(output, default=str, indent=2) if not isinstance(output, str) else output
            context_parts.append(f"\n[{tool_name}]:\n{serialized}")
        context_parts.append("\n\nUsing the above data, provide your final analysis as JSON.")
        return "\n".join(context_parts)

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """Parse JSON from LLM response. Delegates to LLMService._parse_json_response."""
        return LLMService._parse_json_response(raw)

    # Backward compatibility: sync wrapper for tests
    def analyze(self, prompt: str) -> dict:
        """Sync wrapper - runs async analyze in new event loop."""
        return asyncio.run(self.analyze_async(prompt))
