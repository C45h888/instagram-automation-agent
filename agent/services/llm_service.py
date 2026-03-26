import asyncio
import json
import random
import re
import time
import requests
from config import llm, OLLAMA_HOST, logger


class LLMService:
    """Wraps LangChain/Ollama interactions with safe JSON parsing and retry."""

    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 1.0  # seconds
    JITTER_RANGE = 0.5        # seconds added to each backoff step

    # ─────────────────────────────────────────────
    # Core async invoke with exponential backoff
    # ─────────────────────────────────────────────

    @classmethod
    async def invoke(
        cls,
        prompt: str,
        llm_instance=None,
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
    ):
        """Invoke LLM with exponential backoff retry.

        Args:
            prompt: The prompt to send.
            llm_instance: Which LLM to call. Defaults to base llm from config.
                         Pass a tool-bound llm_with_tools variant for scoped calls.
            max_retries: Maximum retry attempts (default 3).
            base_delay: Initial backoff delay in seconds (default 1.0).

        Returns:
            AIMessage response from the LLM.

        Raises:
            The final exception after all retries are exhausted.
        """
        if llm_instance is None:
            llm_instance = llm

        last_error = None

        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(llm_instance.invoke, prompt)

            except Exception as e:
                last_error = e

                if not cls._is_retryable(e):
                    logger.error(f"LLM invoke failed (non-retryable): {e}")
                    raise

                if attempt == max_retries - 1:
                    logger.error(
                        f"LLM invoke exhausted {max_retries} attempts: {e}"
                    )
                    raise

                delay = (base_delay * (2 ** attempt)) + random.uniform(0, cls.JITTER_RANGE)
                logger.warning(
                    f"LLM invoke failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay:.1f}s: {e}"
                )
                await asyncio.sleep(delay)

        # Satisfies type checker — should never reach here
        raise last_error

    # ─────────────────────────────────────────────
    # Deprecated: old sync analyze() — do not use
    # ─────────────────────────────────────────────

    @staticmethod
    def analyze(prompt: str, retry: bool = True) -> dict:
        """DEPRECATED — use invoke() instead. Synchronous, 1x instant retry."""
        start_time = time.time()

        try:
            raw_response = llm.invoke(prompt)
            latency_ms = int((time.time() - start_time) * 1000)

            parsed = LLMService._parse_json_response(raw_response)
            parsed["_latency_ms"] = latency_ms
            return parsed

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LLM inference failed (latency={latency_ms}ms): {e}")

            if retry:
                logger.info("Retrying LLM inference (attempt 2)...")
                return LLMService.analyze(prompt, retry=False)

            return {
                "error": "llm_inference_failed",
                "message": str(e),
                "_latency_ms": latency_ms
            }

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """Parse JSON from LLM response. Tries direct parse, then regex extraction.
        Never uses eval() - always json.loads() for safety.
        """
        cleaned = raw.strip()

        # Try direct JSON parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding first { ... } block
        brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # All parsing failed
        logger.warning(f"Failed to parse LLM response as JSON: {cleaned[:200]}...")
        return {
            "error": "json_parse_failed",
            "raw_response": cleaned[:500]
        }

    @staticmethod
    def is_available() -> dict:
        """Check if Ollama is reachable and model is loaded."""
        try:
            resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return {
                    "available": True,
                    "models_loaded": model_names
                }
            return {"available": False, "reason": f"Status {resp.status_code}"}
        except Exception as e:
            return {"available": False, "reason": str(e)}

    # ─────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """Return True if this error is transient and retry might help.

        Only retry infrastructure/network errors — not logic errors
        (JSON parse, validation, bad prompts).
        """
        msg = str(error).lower()
        retryable = [
            "connection",
            "timeout",
            "unavailable",
            "busy",
            "500",
            "503",
            "429",
            "rate limit",
            "model loading",
            "econnreset",
            "eof",
            "broken pipe",
            "network",
        ]
        return any(kw in msg for kw in retryable)
