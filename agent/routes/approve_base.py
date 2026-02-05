"""
Shared Approval Pipeline
=========================
Generic hook-based pipeline used by all /approve/* routes.
Each route provides an ApprovalConfig with hooks for its unique logic.
The pipeline handles: hard rules -> context fetch -> prompt build -> LLM call ->
response build -> audit logging.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Any

from fastapi import Request
from fastapi.responses import JSONResponse
from services.agent_service import AgentService
from services.supabase_service import SupabaseService
from routes.health import track_request
from routes.metrics import REQUEST_COUNT, REQUEST_LATENCY, APPROVAL_DECISIONS, LLM_ERRORS
from config import logger, OLLAMA_MODEL
from services.prompt_service import PromptService

# Single shared instance — initialized once, reused across all routes
agent_service = AgentService()


@dataclass
class ApprovalConfig:
    """Configuration for a specific approval route."""
    task_type: str                              # "comment", "dm", "post"
    event_type: str                             # "comment_reply_approval", etc.
    resource_type: str                          # "comment", "dm", "post"
    analysis_factors: list[str]                 # for audit_data
    context_used: list[str]                     # for audit_data

    # Required hooks
    get_resource_id: Callable[[Any], str]       # parsed -> resource_id
    get_user_id: Callable[[Any], str]           # parsed -> user_id (business_account_id)
    fetch_context: Callable[[Any], dict]        # parsed -> context dict
    build_prompt: Callable[[Any, dict], str]    # parsed, context -> prompt string
    build_response: Callable[[Any, dict, int, list], dict]  # parsed, result, latency, tools -> response
    build_audit_details: Callable[[Any, dict, int], dict]   # parsed, result, latency -> details

    # Optional hooks
    hard_rules: Optional[Callable[[Any, Request], Optional[dict]]] = None  # parsed, request -> response or None


def _get_request_id(request: Request) -> str:
    """Extract request ID from request state (set by middleware)."""
    return getattr(request.state, "request_id", "unknown")


async def approval_pipeline(parsed: Any, request: Request, config: ApprovalConfig):
    """Generic approval pipeline. Routes call this with their config.

    Flow:
      1. Hard rules (short-circuit if triggered)
      2. Fetch context from Supabase
      3. Build prompt with context
      4. Run LLM approval (in thread pool)
      5. Build response via route hook
      6. Inject standard audit_data
      7. Log decision to audit_log
    """
    pipeline_start = time.time()
    request_id = _get_request_id(request)
    endpoint = f"/approve/{config.task_type}"
    logger.info(f"[{request_id}] Starting {config.task_type} approval pipeline")

    # Track request start
    REQUEST_COUNT.labels(endpoint=endpoint, status="started").inc()

    # Step 1: Hard rules (short-circuit)
    if config.hard_rules:
        hard_rule_response = config.hard_rules(parsed, request)
        if hard_rule_response is not None:
            logger.info(f"[{request_id}] Hard rule triggered, short-circuiting")
            # Include request_id in audit details
            audit_details = hard_rule_response.pop("_audit_details", {})
            audit_details["request_id"] = request_id
            # Log and return early
            SupabaseService.log_decision(
                event_type=config.event_type,
                action=hard_rule_response.pop("_action", "rejected"),
                resource_type=config.resource_type,
                resource_id=config.get_resource_id(parsed),
                user_id=config.get_user_id(parsed),
                details=audit_details,
                ip_address=request.client.host,
            )
            hard_rule_response["request_id"] = request_id
            return hard_rule_response

    # Step 2: Fetch context
    context = config.fetch_context(parsed)

    # Step 3: Build prompt
    prompt = config.build_prompt(parsed, context)

    # Step 4: Run LLM approval (semaphore-limited, runs in thread pool)
    result = await agent_service.analyze_async(prompt)

    if "error" in result and result["error"] != "json_parse_failed":
        logger.error(f"[{request_id}] Agent failed for {config.task_type} approval: {result}")
        # Track LLM error and request failure
        LLM_ERRORS.labels(error_type=result.get("error", "unknown")).inc()
        REQUEST_COUNT.labels(endpoint=endpoint, status="error").inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - pipeline_start)
        return JSONResponse(
            status_code=503,
            content={
                "approved": "pending_manual_review",
                "error": "model_unavailable",
                "message": "AI model could not process request. Please retry.",
                "request_id": request_id,
            }
        )

    latency = result.pop("_latency_ms", 0)
    tools_called = result.pop("_tools_called", [])
    track_request(latency)

    # Step 5: Build response (route-specific)
    response = config.build_response(parsed, result, latency, tools_called)

    # Step 6: Inject standard audit_data (includes request_id for tracing)
    response["audit_data"] = {
        "request_id": request_id,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "agent_model": OLLAMA_MODEL,
        "latency_ms": latency,
        "tools_called": tools_called,
        "analysis_factors": config.analysis_factors,
        "context_used": config.context_used,
        "prompt_version": PromptService.get_version(config.task_type),
    }

    # Step 7: Determine action and log
    action = response.pop("_action_override", None)
    if not action:
        action = "approved" if response.get("approved") else "rejected"

    details = config.build_audit_details(parsed, result, latency)
    details["request_id"] = request_id  # Include in audit log for correlation

    SupabaseService.log_decision(
        event_type=config.event_type,
        action=action,
        resource_type=config.resource_type,
        resource_id=config.get_resource_id(parsed),
        user_id=config.get_user_id(parsed),
        details=details,
        ip_address=request.client.host,
    )

    # Track metrics
    pipeline_latency = time.time() - pipeline_start
    REQUEST_COUNT.labels(endpoint=endpoint, status="success").inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(pipeline_latency)
    APPROVAL_DECISIONS.labels(task_type=config.task_type, decision=action).inc()

    logger.info(f"[{request_id}] {config.task_type} approval completed: {action} (latency={latency}ms)")
    return response
