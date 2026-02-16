"""
Instagram DM Webhook Handler
=============================
Receives ONLY direct webhook events from Meta's Instagram Graph API.
NOT an N8N forwarding layer — the agent is sovereign.

Respects 24h messaging window before executing replies.

Endpoints:
  GET  /webhook/dm - Meta verification challenge
  POST /webhook/dm - Process incoming DM event
"""

from fastapi import APIRouter, Request
from typing import Optional

from config import INSTAGRAM_VERIFY_TOKEN, WEBHOOK_RATE_LIMIT
from services.validation import DMWebhookData
from services.supabase_service import SupabaseService
from routes.webhook_base import WebhookConfig, webhook_pipeline
from tools.automation_tools import _reply_to_dm

webhook_dm_router = APIRouter()


# ================================
# Hooks
# ================================
def _parse_payload(raw: dict) -> DMWebhookData:
    """Parse Instagram DM webhook payload.

    Instagram sends:
    {
      "object": "instagram",
      "entry": [{
        "id": "<page_id>",
        "time": 1234567890,
        "messaging": [{
          "sender": {"id": "<sender_id>"},
          "recipient": {"id": "<recipient_id>"},
          "timestamp": 1234567890,
          "message": {
            "mid": "<message_id>",
            "text": "message text",
            "attachments": [...]  # optional
          }
        }]
      }]
    }
    """
    entry = raw.get("entry", [{}])[0]
    messaging = entry.get("messaging", [{}])[0]
    message = messaging.get("message", {})

    ig_page_id = entry.get("id", "")
    return DMWebhookData(
        message_id=message.get("mid", ""),
        message_text=message.get("text", ""),
        sender_username="",  # Not provided in webhook, could fetch separately
        sender_id=messaging.get("sender", {}).get("id", ""),
        # Resolve IG numeric Page ID → Supabase UUID for backend proxy calls
        business_account_id=(
            SupabaseService.get_account_uuid_by_instagram_id(ig_page_id)
            or ig_page_id  # fallback: pipeline logs the failure gracefully
        ),
        conversation_id=messaging.get("sender", {}).get("id", ""),  # Conversation ID = sender ID
        timestamp=str(messaging.get("timestamp", "")),
        has_attachments=bool(message.get("attachments")),
    )


def _hard_rules(parsed: DMWebhookData, request: Request) -> Optional[dict]:
    """DM-specific hard rules.

    Skip auto-reply if:
    - Message has attachments (images/videos)
    - Message is empty
    """
    if parsed.has_attachments:
        return {
            "processed": True,
            "needs_human": True,
            "escalation_reason": "Message contains attachments - requires human review",
            "_action": "escalated",
            "_audit_details": {"reason": "has_attachments"},
        }

    if not parsed.message_text.strip():
        return {
            "processed": True,
            "needs_human": False,
            "skipped": True,
            "skip_reason": "Empty message",
            "_action": "skipped",
            "_audit_details": {"reason": "empty_message"},
        }

    return None


def _fetch_context(parsed: DMWebhookData) -> dict:
    """Fetch account, DM history, and conversation context."""
    return {
        "account": SupabaseService.get_account_info(parsed.business_account_id),
        "dm_history": SupabaseService.get_dm_history(parsed.sender_id, parsed.business_account_id),
        "conversation": SupabaseService.get_dm_conversation_context(parsed.sender_id, parsed.business_account_id),
    }


def _build_analysis_input(parsed: DMWebhookData, ctx: dict) -> dict:
    """Build input for analyze_message tool."""
    # Extract customer lifetime value if available from context
    customer_value = 0.0

    return {
        "message_text": parsed.message_text,
        "message_type": "dm",
        "sender_username": parsed.sender_username or f"user_{parsed.sender_id[-6:]}",
        "account_context": ctx.get("account", {}),
        "post_context": None,
        "dm_history": ctx.get("dm_history"),
        "customer_lifetime_value": customer_value,
    }


def _pre_execute_check(parsed: DMWebhookData, analysis: dict) -> Optional[dict]:
    """Check 24h window before executing DM reply.

    Returns execution result dict if reply should be blocked,
    or None if reply can proceed.
    """
    # Fetch fresh conversation context to verify window
    conv_ctx = SupabaseService.get_dm_conversation_context(
        parsed.sender_id,
        parsed.business_account_id
    )

    within_window = conv_ctx.get("within_window", False)

    if not within_window:
        return {
            "executed": False,
            "reason": "outside_24h_window",
            "message": "Cannot send DM - outside 24-hour messaging window",
        }

    return None  # Proceed with execution


def _build_response(parsed: DMWebhookData, analysis: dict) -> dict:
    """Build response payload."""
    return {
        "processed": True,
        "message_id": parsed.message_id,
        "sender_id": parsed.sender_id,
        "category": analysis.get("category"),
        "sentiment": analysis.get("sentiment"),
        "priority": analysis.get("priority"),
        "needs_human": analysis.get("needs_human", False),
        "escalation_reason": analysis.get("escalation_reason"),
        "suggested_reply": analysis.get("suggested_reply"),
        "confidence": analysis.get("confidence", 0),
    }


def _execute_reply(parsed: DMWebhookData, analysis: dict) -> dict:
    """Execute DM reply if analysis approves."""
    suggested_reply = analysis.get("suggested_reply", "")

    if not suggested_reply:
        return {"executed": False, "reason": "no_reply_suggested"}

    # Only auto-reply if not escalated
    if analysis.get("needs_human"):
        return {"executed": False, "reason": "escalated_to_human"}

    result = _reply_to_dm(
        conversation_id=parsed.conversation_id,
        recipient_id=parsed.sender_id,
        message_text=suggested_reply,
        business_account_id=parsed.business_account_id,
    )

    return {
        "executed": result.get("success", False),
        "reply_sent": suggested_reply if result.get("success") else None,
        "execution_id": result.get("execution_id"),
        "error": result.get("error") if not result.get("success") else None,
    }


def _build_audit_details(parsed: DMWebhookData, analysis: dict, exec_result: dict, latency: int) -> dict:
    """Build audit log details."""
    return {
        "message_text": parsed.message_text[:200],
        "sender_id": parsed.sender_id,
        "category": analysis.get("category"),
        "sentiment": analysis.get("sentiment"),
        "priority": analysis.get("priority"),
        "confidence": analysis.get("confidence"),
        "needs_human": analysis.get("needs_human"),
        "escalation_reason": analysis.get("escalation_reason"),
        "suggested_reply": analysis.get("suggested_reply"),
        "reply_executed": exec_result.get("executed", False),
        "execution_id": exec_result.get("execution_id"),
        "execution_error": exec_result.get("error"),
        "latency_ms": latency,
    }


# ================================
# Config
# ================================
_config = WebhookConfig(
    message_type="dm",
    event_type="webhook_dm_processed",
    resource_type="dm",
    parse_payload=_parse_payload,
    get_resource_id=lambda p: p.message_id,
    get_user_id=lambda p: p.business_account_id,
    hard_rules=_hard_rules,
    fetch_context=_fetch_context,
    build_analysis_input=_build_analysis_input,
    build_response=_build_response,
    execute_reply=_execute_reply,
    build_audit_details=_build_audit_details,
    pre_execute_check=_pre_execute_check,
)


# ================================
# Routes
# ================================
@webhook_dm_router.get("/webhook/dm")
async def verify_dm_webhook(request: Request):
    """Instagram webhook verification."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == INSTAGRAM_VERIFY_TOKEN:
        return int(challenge) if challenge else challenge

    return {"error": "verification_failed"}


@webhook_dm_router.post("/webhook/dm")
async def process_dm_webhook(request: Request):
    """Process incoming Instagram DM webhook."""
    body = await request.body()
    raw_payload = await request.json()

    return await webhook_pipeline(raw_payload, body, request, _config)
