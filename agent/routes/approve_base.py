"""
Shared Approval Flow
=====================
Common LLM invocation + error handling used by all /approve/* routes.
Routes remain responsible for: validation, hard rules, response shaping.
"""

from flask import jsonify
from services.agent_service import AgentService
from routes.health import track_request
from config import logger

# Single shared instance — initialized once, reused across all routes
agent_service = AgentService()


def run_approval(prompt: str, task_type: str) -> tuple[dict, int]:
    """Invoke agent with prompt, handle errors, track latency.

    Args:
        prompt: Fully formatted prompt string for the LLM.
        task_type: Label for logging (e.g. "comment", "dm", "post").

    Returns:
        (result_dict, status_code) — caller builds the final response from result_dict.
        On success: result_dict contains parsed LLM output + _latency_ms.
        On failure: returns a 503 tuple directly.
    """
    result = agent_service.analyze(prompt)

    # LLM failure (not a JSON parse issue — those still contain usable data)
    if "error" in result and result["error"] != "json_parse_failed":
        logger.error(f"Agent failed for {task_type} approval: {result}")
        return {
            "approved": "pending_manual_review",
            "error": "model_unavailable",
            "message": "AI model could not process request. Please retry.",
        }, 503

    latency = result.pop("_latency_ms", 0)
    tools_called = result.pop("_tools_called", [])
    track_request(latency)

    # Attach metadata for routes to use
    result["_latency_ms"] = latency
    result["_tools_called"] = tools_called

    return result, 200
