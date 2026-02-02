import json
import re
import time
import requests
from config import llm, OLLAMA_HOST, logger


class LLMService:
    """Wraps LangChain/Ollama interactions with safe JSON parsing and retry."""

    @staticmethod
    def analyze(prompt: str, retry: bool = True) -> dict:
        """Invoke Nemotron via Ollama and parse JSON response.

        Returns dict with parsed result or error info.
        Retries once on failure if retry=True.
        """
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
