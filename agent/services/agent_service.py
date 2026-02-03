"""
Agent Service
==============
Lightweight LLM+tools layer using llm.bind_tools() (NOT AgentExecutor).
Single-pass: LLM receives tools → may call them → we execute → return result.

Upgrade path: If multi-step reasoning is needed later, swap to AgentExecutor.
The tools and prompts are already compatible.
"""

import json
import re
import time

from config import llm, logger
from tools import SUPABASE_TOOLS


class AgentService:
    """Invoke LLM with bound Supabase tools for context-aware analysis."""

    def __init__(self):
        self.llm_with_tools = llm.bind_tools(SUPABASE_TOOLS)
        self._tool_map = {t.name: t for t in SUPABASE_TOOLS}
        logger.info(f"AgentService initialized with {len(SUPABASE_TOOLS)} tools: {list(self._tool_map.keys())}")

    def analyze(self, prompt: str) -> dict:
        """Invoke LLM with bound tools. Single-pass tool execution.

        Flow:
          1. Send prompt to LLM with tools bound
          2. If LLM requests tool calls, execute them
          3. Parse final response as JSON

        Returns dict with parsed result or error info.
        """
        start_time = time.time()

        try:
            # Step 1: Invoke LLM with tools
            result = self.llm_with_tools.invoke(prompt)
            tool_calls = getattr(result, "tool_calls", [])

            # Step 2: Execute tool calls if any
            tool_outputs = {}
            if tool_calls:
                tool_outputs = self._execute_tool_calls(tool_calls)

                # If tools were called, do a follow-up invoke with tool results as context
                if tool_outputs:
                    enriched_prompt = self._build_enriched_prompt(prompt, tool_outputs)
                    result = self.llm_with_tools.invoke(enriched_prompt)

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
            return {
                "error": "agent_execution_failed",
                "message": str(e),
                "_latency_ms": latency_ms,
            }

    def _execute_tool_calls(self, tool_calls: list) -> dict:
        """Execute tool calls requested by the LLM."""
        outputs = {}
        for call in tool_calls:
            tool_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            tool_args = call.get("args", {}) if isinstance(call, dict) else getattr(call, "args", {})

            tool = self._tool_map.get(tool_name)
            if not tool:
                logger.warning(f"LLM requested unknown tool: {tool_name}")
                continue

            try:
                result = tool.invoke(tool_args)
                outputs[tool_name] = result
                logger.info(f"Tool '{tool_name}' executed successfully")
            except Exception as e:
                logger.error(f"Tool '{tool_name}' failed: {e}")
                outputs[tool_name] = {"error": str(e)}

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
