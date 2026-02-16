"""
Instagram Comment Webhook Handler
===================================
Receives ONLY direct webhook events from Meta's Instagram Graph API.
NOT an N8N forwarding layer — the agent is sovereign.

Flow: Instagram → HMAC-verified POST → analyze → auto-reply → audit_log

Endpoints:
  GET  /webhook/comment - Meta verification challenge
  POST /webhook/comment - Process incoming comment event
"""

from fastapi import APIRouter, Request

from config import INSTAGRAM_VERIFY_TOKEN, WEBHOOK_RATE_LIMIT
from services.validation import CommentWebhookData
from services.supabase_service import SupabaseService
from routes.webhook_base import WebhookConfig, webhook_pipeline
from tools.automation_tools import _reply_to_comment

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


def _fetch_context(parsed: CommentWebhookData) -> dict:
    """Fetch post and account context for comment analysis."""
    return {
        "post": SupabaseService.get_post_context(parsed.post_id),
        "account": SupabaseService.get_account_info(parsed.business_account_id),
    }


def _build_analysis_input(parsed: CommentWebhookData, ctx: dict) -> dict:
    """Build input for analyze_message tool."""
    return {
        "message_text": parsed.comment_text,
        "message_type": "comment",
        "sender_username": parsed.commenter_username,
        "account_context": ctx.get("account", {}),
        "post_context": ctx.get("post"),
        "dm_history": None,
        "customer_lifetime_value": 0.0,  # Could be fetched from DB if available
    }


def _build_response(parsed: CommentWebhookData, analysis: dict) -> dict:
    """Build response payload."""
    return {
        "processed": True,
        "comment_id": parsed.comment_id,
        "category": analysis.get("category"),
        "sentiment": analysis.get("sentiment"),
        "priority": analysis.get("priority"),
        "needs_human": analysis.get("needs_human", False),
        "suggested_reply": analysis.get("suggested_reply"),
        "confidence": analysis.get("confidence", 0),
    }


def _execute_reply(parsed: CommentWebhookData, analysis: dict) -> dict:
    """Execute comment reply if analysis approves."""
    suggested_reply = analysis.get("suggested_reply", "")

    if not suggested_reply:
        return {"executed": False, "reason": "no_reply_suggested"}

    # Only auto-reply if not escalated
    if analysis.get("needs_human"):
        return {"executed": False, "reason": "escalated_to_human"}

    result = _reply_to_comment(
        comment_id=parsed.comment_id,
        reply_text=suggested_reply,
        business_account_id=parsed.business_account_id,
        post_id=parsed.post_id,
    )

    return {
        "executed": result.get("success", False),
        "reply_sent": suggested_reply if result.get("success") else None,
        "execution_id": result.get("execution_id"),
        "error": result.get("error") if not result.get("success") else None,
    }


def _build_audit_details(parsed: CommentWebhookData, analysis: dict, exec_result: dict, latency: int) -> dict:
    """Build audit log details."""
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
_config = WebhookConfig(
    message_type="comment",
    event_type="webhook_comment_processed",
    resource_type="comment",
    parse_payload=_parse_payload,
    get_resource_id=lambda p: p.comment_id,
    get_user_id=lambda p: p.business_account_id,
    fetch_context=_fetch_context,
    build_analysis_input=_build_analysis_input,
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
