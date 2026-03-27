"""
Instagram Comment Webhook Handler
===================================
Receives ONLY direct webhook events from Meta's Instagram Graph API.
NOT an N8N forwarding layer — the agent is sovereign.

New architecture: Webhook writes to Supabase only. The engagement_monitor
polls Supabase, runs AgentService.bind_tools() for analysis, and executes
replies. This separates concerns and avoids the recursion loop.

Flow: Instagram → HMAC-verified POST → write to Supabase → return
(Analysis and reply execution deferred to engagement_monitor)

Endpoints:
  GET  /webhook/comment - Meta verification challenge
  POST /webhook/comment - Process incoming comment event
"""

from fastapi import APIRouter, Request

from config import INSTAGRAM_VERIFY_TOKEN, WEBHOOK_RATE_LIMIT
from services.validation import CommentWebhookData
from services.supabase_service import SupabaseService
from routes.webhook_base import WebhookConfig, webhook_pipeline

webhook_comment_router = APIRouter()


# ================================
# Hooks
# ================================
def _parse_payload(raw: dict) -> CommentWebhookData:
    """Parse Instagram comment webhook payload.

    Instagram sends:
    {
      "object": "instagram",
      "entry": [{
        "id": "<page_id>",
        "time": 1234567890,
        "changes": [{
          "field": "comments",
          "value": {
            "id": "<comment_id>",
            "text": "comment text",
            "from": {"id": "<user_id>", "username": "user"},
            "media": {"id": "<media_id>"}
          }
        }]
      }]
    }
    """
    entry = raw.get("entry", [{}])[0]
    changes = entry.get("changes", [{}])[0]
    value = changes.get("value", {})

    ig_page_id = entry.get("id", "")
    return CommentWebhookData(
        comment_id=value.get("id", ""),
        comment_text=value.get("text", ""),
        post_id=value.get("media", {}).get("id", ""),
        commenter_username=value.get("from", {}).get("username", "unknown"),
        commenter_id=value.get("from", {}).get("id", ""),
        # Resolve IG numeric Page ID → Supabase UUID for backend proxy calls
        business_account_id=(
            SupabaseService.get_account_uuid_by_instagram_id(ig_page_id)
            or ig_page_id  # fallback: pipeline logs the failure gracefully
        ),
        timestamp=str(entry.get("time", "")),
    )


def _build_response(parsed: CommentWebhookData, analysis: dict) -> dict:
    """Build response payload.

    In the new architecture, analysis is empty (deferred to monitor).
    Returns a queued-for-processing response.
    """
    return {
        "processed": True,
        "status": "queued_for_processing",
        "comment_id": parsed.comment_id,
        "source": "webhook",
    }


def _execute_reply(parsed: CommentWebhookData, analysis: dict) -> dict:
    """Execute comment reply — NO-OP in new architecture.

    Analysis and reply execution are deferred to the engagement monitor.
    This hook is kept to preserve the response structure but returns no-op.
    """
    return {"executed": False, "reason": "deferred_to_monitor"}


def _build_audit_details(parsed: CommentWebhookData, analysis: dict, exec_result: dict, latency: int) -> dict:
    """Build audit log details and write-through to instagram_comments (RC-A/RC-D fix).

    Upserts the comment with processed_by_automation=True so the engagement monitor's
    get_unprocessed_comments() query skips it on the next batch cycle, eliminating
    the duplicate-reply race condition.
    """
    SupabaseService.upsert_webhook_comment(
        instagram_comment_id=parsed.comment_id,
        media_instagram_id=parsed.post_id,
        business_account_id=parsed.business_account_id,
        text=parsed.comment_text,
        author_username=parsed.commenter_username,
        author_instagram_id=parsed.commenter_id,
        created_at=parsed.timestamp,
        automated_response_sent=exec_result.get("executed", False),
        response_text=exec_result.get("reply_sent"),
    )
    return {
        "comment_text": parsed.comment_text[:200],
        "commenter": parsed.commenter_username,
        "post_id": parsed.post_id,
        "category": analysis.get("category"),
        "sentiment": analysis.get("sentiment"),
        "priority": analysis.get("priority"),
        "confidence": analysis.get("confidence"),
        "needs_human": analysis.get("needs_human"),
        "suggested_reply": analysis.get("suggested_reply"),
        "reply_executed": exec_result.get("executed", False),
        "execution_id": exec_result.get("execution_id"),
        "latency_ms": latency,
    }


# ================================
# Config
# ================================
# In new architecture: webhooks write to Supabase only.
# _fetch_context and _build_analysis_input removed (deferred to engagement_monitor).
# _execute_reply kept as no-op to preserve response structure.
_config = WebhookConfig(
    message_type="comment",
    event_type="webhook_comment_processed",
    resource_type="comment",
    parse_payload=_parse_payload,
    get_resource_id=lambda p: p.comment_id,
    get_user_id=lambda p: p.business_account_id,
    build_response=_build_response,
    execute_reply=_execute_reply,
    build_audit_details=_build_audit_details,
)


# ================================
# Routes
# ================================
@webhook_comment_router.get("/webhook/comment")
async def verify_comment_webhook(request: Request):
    """Instagram webhook verification (GET request).

    Instagram sends:
    - hub.mode=subscribe
    - hub.verify_token=<your_token>
    - hub.challenge=<challenge_string>

    Must return hub.challenge to verify.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == INSTAGRAM_VERIFY_TOKEN:
        return int(challenge) if challenge else challenge

    return {"error": "verification_failed"}


@webhook_comment_router.post("/webhook/comment")
async def process_comment_webhook(request: Request):
    """Process incoming Instagram comment webhook."""
    body = await request.body()
    raw_payload = await request.json()

    return await webhook_pipeline(raw_payload, body, request, _config)
