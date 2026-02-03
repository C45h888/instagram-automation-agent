from datetime import datetime, timezone
from fastapi import APIRouter, Request
from services.validation import DMApprovalRequest
from services.supabase_service import SupabaseService
from routes.approve_base import ApprovalConfig, approval_pipeline
from services.prompt_service import PromptService
from config import OLLAMA_MODEL, VIP_LIFETIME_VALUE_THRESHOLD, ESCALATION_INTENTS

approve_dm_router = APIRouter()


# ================================
# Hooks
# ================================
def _hard_rules(parsed, request):
    """DM-specific hard rules: 24h window, VIP escalation, intent escalation."""
    # Reject if outside 24h messaging window
    if not parsed.within_24h_window:
        return {
            "approved": False,
            "modifications": None,
            "needs_escalation": False,
            "decision_reasoning": "Cannot send DM - outside 24-hour messaging window. Customer must message first.",
            "audit_data": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": OLLAMA_MODEL,
                "rule_triggered": "24h_window_expired"
            },
            "_action": "rejected",
            "_audit_details": {"reason": "24h_window_expired"},
        }

    # VIP / escalation checks
    customer_history = parsed.customer_history
    lifetime_value = customer_history.lifetime_value if customer_history else 0

    force_escalate = False
    escalation_reason = ""

    if lifetime_value > VIP_LIFETIME_VALUE_THRESHOLD:
        force_escalate = True
        escalation_reason = f"VIP customer (lifetime value ${lifetime_value}) - requires human attention"

    if parsed.sentiment in ("negative", "angry") and parsed.detected_intent in ESCALATION_INTENTS:
        force_escalate = True
        escalation_reason = f"Negative sentiment with {parsed.detected_intent} intent - requires human support"

    if parsed.detected_intent in ESCALATION_INTENTS:
        force_escalate = True
        escalation_reason = f"Intent '{parsed.detected_intent}' requires human judgment"

    if force_escalate:
        return {
            "approved": False,
            "modifications": None,
            "needs_escalation": True,
            "escalation_reason": escalation_reason,
            "suggested_team": "support" if parsed.detected_intent in ESCALATION_INTENTS else "sales",
            "decision_reasoning": escalation_reason,
            "audit_data": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": OLLAMA_MODEL,
                "rule_triggered": "forced_escalation"
            },
            "_action": "escalated",
            "_audit_details": {"reason": escalation_reason, "lifetime_value": lifetime_value},
        }

    return None  # No hard rule triggered — continue to LLM


def _fetch_context(parsed):
    return {
        "account": SupabaseService.get_account_info(parsed.business_account_id),
        "dm_history": SupabaseService.get_dm_history(parsed.sender_id, parsed.business_account_id),
    }


def _build_prompt(parsed, ctx):
    customer_history = parsed.customer_history
    lifetime_value = customer_history.lifetime_value if customer_history else 0
    sentiment_history = customer_history.sentiment_history if customer_history else "neutral"
    previous_interactions = customer_history.previous_interactions if customer_history else 0

    dm_history = ctx["dm_history"]
    dm_history_str = "No previous DMs"
    if dm_history:
        dm_history_str = "\n".join([
            f"  [{m.get('direction', '?')}] {m.get('message_text', '')[:100]}"
            for m in dm_history[:5]
        ])

    return PromptService.get("dm").format(
        account_username=ctx["account"].get("username", "unknown"),
        business_account_id=parsed.business_account_id,
        dm_text=parsed.dm_text[:500],
        sender_username=parsed.sender_username,
        sender_id=parsed.sender_id,
        detected_intent=parsed.detected_intent,
        sentiment=parsed.sentiment,
        priority=parsed.priority,
        within_24h_window=parsed.within_24h_window,
        previous_interactions=previous_interactions,
        sentiment_history=sentiment_history,
        lifetime_value=lifetime_value,
        dm_history=dm_history_str,
        proposed_reply=parsed.proposed_reply[:300],
    )


def _build_response(parsed, result, latency, tools_called):
    needs_escalation = result.get("needs_escalation", False)
    quality_score = result.get("quality_score", 0)
    approved = result.get("approved", False)

    resp = {
        "approved": approved,
        "modifications": result.get("modifications"),
        "needs_escalation": needs_escalation,
        "decision_reasoning": result.get("reasoning", "No reasoning provided"),
        "confidence": quality_score / 10.0 if quality_score else 0,
        "quality_score": quality_score,
    }

    # Override action for audit log
    if needs_escalation:
        resp["_action_override"] = "escalated"

    return resp


def _build_audit_details(parsed, result, latency):
    mods = result.get("modifications")
    return {
        "proposed_reply": parsed.proposed_reply,
        "approved_reply": mods.get("reply_text") if mods else None,
        "quality_score": result.get("quality_score", 0),
        "needs_escalation": result.get("needs_escalation", False),
        "reasoning": result.get("reasoning", ""),
        "latency_ms": latency,
    }


# ================================
# Config
# ================================
_config = ApprovalConfig(
    task_type="dm",
    event_type="dm_reply_approval",
    resource_type="dm",
    analysis_factors=["appropriateness", "personalization", "escalation_need", "format"],
    context_used=["account_info", "dm_history", "customer_history"],
    get_resource_id=lambda p: p.message_id,
    get_user_id=lambda p: p.business_account_id,
    hard_rules=_hard_rules,
    fetch_context=_fetch_context,
    build_prompt=_build_prompt,
    build_response=_build_response,
    build_audit_details=_build_audit_details,
)


# ================================
# Route
# ================================
@approve_dm_router.post("/approve/dm-reply")
async def approve_dm_reply(parsed: DMApprovalRequest, request: Request):
    """Approve or reject a proposed DM reply from N8N."""
    return await approval_pipeline(parsed, request, _config)
