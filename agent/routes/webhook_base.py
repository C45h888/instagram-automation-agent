"""
Shared Webhook Pipeline
========================
Generic hook-based pipeline for Instagram webhook processing.
In the new architecture, webhooks write to Supabase only. Analysis and
reply execution are deferred to the engagement/dm monitors via
AgentService.bind_tools().

Features:
- HMAC-SHA256 signature verification
- Rate limiting via SlowAPI
- Request ID tracing
- Async execution
- Timeout protection
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Any

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from config import logger, INSTAGRAM_APP_SECRET
from services.supabase_service import SupabaseService
from routes.health import track_request
from routes.metrics import REQUEST_COUNT, REQUEST_LATENCY, APPROVAL_DECISIONS


@dataclass
class WebhookConfig:
    """Configuration for a specific webhook route."""
    message_type: str                           # "comment" or "dm"
    event_type: str                             # "webhook_comment_processed", etc.
    resource_type: str                          # "comment" or "dm"

    # Required hooks
    parse_payload: Callable[[dict], Any]        # raw_payload -> parsed model
    get_resource_id: Callable[[Any], str]       # parsed -> resource_id
    get_user_id: Callable[[Any], str]           # parsed -> business_account_id
    fetch_context: Callable[[Any], dict]        # parsed -> context dict
    build_analysis_input: Callable[[Any, dict], dict]  # parsed, context -> tool input
    build_response: Callable[[Any, dict], dict] # parsed, analysis -> response
    execute_reply: Callable[[Any, dict], dict]  # parsed, analysis -> execution result
    build_audit_details: Callable[[Any, dict, dict, int], dict]  # parsed, analysis, exec_result, latency

    # Optional hooks
    hard_rules: Optional[Callable[[Any, Request], Optional[dict]]] = None
    pre_execute_check: Optional[Callable[[Any, dict], Optional[dict]]] = None


def verify_instagram_signature(request: Request, body: bytes) -> bool:
    """Verify Instagram webhook signature using X-Hub-Signature-256 header.

    Instagram sends HMAC-SHA256 signature of the raw request body.
    Must be verified before processing any webhook.
    """
    if not INSTAGRAM_APP_SECRET:
        logger.warning("INSTAGRAM_APP_SECRET not set - skipping signature verification (dev mode)")
        return True

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format")
        return False

    expected_signature = signature_header[7:]  # Remove "sha256=" prefix

    computed_signature = hmac.new(
        INSTAGRAM_APP_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)


def _get_request_id(request: Request) -> str:
    """Extract request ID from request state (set by middleware)."""
    return getattr(request.state, "request_id", "unknown")


async def webhook_pipeline(raw_payload: dict, body: bytes, request: Request, config: WebhookConfig):
    """Generic webhook pipeline for Instagram messages.

    In the new architecture, webhooks write to Supabase only. The monitors
    (engagement_monitor, dm_monitor) poll Supabase, run analysis via
    AgentService.bind_tools(), and execute replies.

    Flow:
      1. Verify signature
      2. Parse payload
      3. Hard rules (short-circuit if triggered) — e.g., empty DM, attachments
      4. Fetch context / write-through to Supabase
      5. Build response (no analysis in webhook)
      6. Audit log
    """
    pipeline_start = time.time()
    request_id = _get_request_id(request)
    endpoint = f"/webhook/{config.message_type}"
    logger.info(f"[{request_id}] Starting {config.message_type} webhook pipeline")

    REQUEST_COUNT.labels(endpoint=endpoint, status="started").inc()

    # Step 1: Verify signature
    if not verify_instagram_signature(request, body):
        logger.warning(f"[{request_id}] Invalid webhook signature")
        REQUEST_COUNT.labels(endpoint=endpoint, status="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Step 2: Parse payload
    try:
        parsed = config.parse_payload(raw_payload)
    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse webhook payload: {e}")
        REQUEST_COUNT.labels(endpoint=endpoint, status="parse_error").inc()
        return JSONResponse(
            status_code=400,
            content={"error": "parse_error", "message": str(e), "request_id": request_id}
        )

    # Step 3: Hard rules (short-circuit)
    if config.hard_rules:
        hard_rule_response = config.hard_rules(parsed, request)
        if hard_rule_response is not None:
            action = hard_rule_response.pop("_action", "escalated")
            logger.info(f"[{request_id}] Hard rule triggered: {action}")
            audit_details = hard_rule_response.pop("_audit_details", {})
            audit_details["request_id"] = request_id

            SupabaseService.log_decision(
                event_type=config.event_type,
                action=action,
                resource_type=config.resource_type,
                resource_id=config.get_resource_id(parsed),
                user_id=config.get_user_id(parsed),
                details=audit_details,
                ip_address=request.client.host if request.client else "unknown",
            )

            hard_rule_response["request_id"] = request_id
            REQUEST_COUNT.labels(endpoint=endpoint, status="hard_rule").inc()
            return hard_rule_response

    # Step 4: Fetch context (optional — write-through for DM conversations, no-ops for comments)
    context = config.fetch_context(parsed) if config.fetch_context else {}

    # Step 5: In the new architecture, webhooks write to Supabase only.
    # Analysis and reply execution are handled by the engagement/dm monitors
    # via AgentService.bind_tools(). Webhooks return immediately after write.
    # analysis_result is kept as empty dict for hook compatibility.
    analysis_result: dict = {}

    latency = int((time.time() - pipeline_start) * 1000)
    track_request(latency)

    # Step 6: Pre-execute check (e.g., 24h window for DMs)
    # In new architecture, this is deferred to the monitor unless the webhook
    # has a pre_execute_check hook defined (DM webhook keeps it for attachment/empty checks).
    exec_result = {"executed": False, "reason": "deferred_to_monitor"}

    if config.pre_execute_check:
        pre_check = config.pre_execute_check(parsed, analysis_result)
        if pre_check is not None:
            exec_result = pre_check
            # If pre-check blocked execution (e.g., outside 24h window), skip execute_reply
        elif config.execute_reply:
            exec_result = config.execute_reply(parsed, analysis_result)
    elif config.execute_reply:
        # No pre-check needed — execute_reply is still called but returns no-op
        # when analysis_result is empty (suggested_reply not present)
        exec_result = config.execute_reply(parsed, analysis_result)

    # Step 7: Build response
    response = config.build_response(parsed, analysis_result)
    response["execution"] = exec_result
    response["request_id"] = request_id
    response["audit_data"] = {
        "request_id": request_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        # agent_model and analyzed_at are set by the monitor when it processes this record
        "latency_ms": latency,
        "note": "analysis deferred to engagement/dm monitor",
    }

    # Determine action for audit
    # In new architecture: webhooks write to Supabase only, monitors execute replies.
    # analysis_result is {} so needs_human check is always False here.
    if exec_result.get("executed"):
        action = "auto_replied"
    elif exec_result.get("reason") == "deferred_to_monitor":
        action = "queued_for_processing"
    else:
        action = "processed_no_reply"

    # Log to audit
    audit_details = config.build_audit_details(parsed, analysis_result, exec_result, latency)
    audit_details["request_id"] = request_id

    SupabaseService.log_decision(
        event_type=config.event_type,
        action=action,
        resource_type=config.resource_type,
        resource_id=config.get_resource_id(parsed),
        user_id=config.get_user_id(parsed),
        details=audit_details,
        ip_address=request.client.host if request.client else "unknown",
    )

    # Track metrics
    pipeline_latency = time.time() - pipeline_start
    REQUEST_COUNT.labels(endpoint=endpoint, status="success").inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(pipeline_latency)
    APPROVAL_DECISIONS.labels(task_type=config.message_type, decision=action).inc()

    logger.info(f"[{request_id}] {config.message_type} webhook completed: {action} (latency={latency}ms)")
    return response
