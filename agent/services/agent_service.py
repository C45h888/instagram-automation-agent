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
import re
import time

from config import llm, logger
from tools import ALL_TOOLS
from prompts import SYSTEM_PROMPT
from routes.metrics import TOOL_CALLS, LLM_ERRORS

# Configurable max concurrent LLM inferences (protects Ollama CPU)
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))
_llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

# Per-tool timeout in seconds
TOOL_TIMEOUT_SECONDS = 5.0


class AgentService:
    """Invoke LLM with bound tools for context-aware analysis and automation."""

    def __init__(self):
        self.llm_with_tools = llm.bind_tools(ALL_TOOLS)
        self._tool_map = {t.name: t for t in ALL_TOOLS}
        logger.info(
            f"AgentService initialized with {len(ALL_TOOLS)} tools "
            f"(max_concurrent={MAX_CONCURRENT_LLM}, tool_timeout={TOOL_TIMEOUT_SECONDS}s): "
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

    async def _analyze(self, prompt: str) -> dict:
        """Async LLM invocation with parallel tool execution.

        Flow:
          1. Send prompt to LLM with tools bound (sync invoke in thread)
          2. If LLM requests tool calls, execute them in parallel
          3. If tools were called, do follow-up invoke with results
          4. Parse final response as JSON

        Returns dict with parsed result or error info.
        """
        start_time = time.time()

        try:
            # Prepend system prompt for consistent behavior
            full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

            # Step 1: Invoke LLM with tools (sync wrapped in thread)
            result = await asyncio.to_thread(self.llm_with_tools.invoke, full_prompt)
            tool_calls = getattr(result, "tool_calls", [])

            # Step 2: Execute tool calls in parallel if any
            tool_outputs = {}
            if tool_calls:
                tool_outputs = await self._execute_tool_calls_async(tool_calls)

                # If tools were called, do a follow-up invoke with tool results as context
                if tool_outputs:
                    enriched_prompt = self._build_enriched_prompt(full_prompt, tool_outputs)
                    result = await asyncio.to_thread(self.llm_with_tools.invoke, enriched_prompt)

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
        """Parse JSON from LLM response. Same logic as LLMService for consistency."""
        cleaned = raw.strip()

        # Direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Markdown code block
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # First { ... } block
        brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Failed to parse agent response as JSON: {cleaned[:200]}...")
        return {
            "error": "json_parse_failed",
            "raw_response": cleaned[:500],
        }

    # Backward compatibility: sync wrapper for tests
    def analyze(self, prompt: str) -> dict:
        """Sync wrapper - runs async analyze in new event loop."""
        return asyncio.run(self.analyze_async(prompt))
