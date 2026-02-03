from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from services.validation import DMApprovalRequest, validate_request
from services.supabase_service import SupabaseService
from routes.approve_base import run_approval
from prompts import PROMPTS
from config import logger, VIP_LIFETIME_VALUE_THRESHOLD, ESCALATION_INTENTS

approve_dm_bp = Blueprint("approve_dm", __name__)


@approve_dm_bp.route("/approve/dm-reply", methods=["POST"])
def approve_dm_reply():
    """Approve or reject a proposed DM reply from N8N.

    Includes escalation logic for VIP customers, negative sentiment, and complaints.
    Hard rules stay in this route — never delegated to LLM.
    Auth handled by middleware.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "validation_error", "message": "Request body must be JSON"}), 400

    # Validate request
    parsed, error = validate_request(DMApprovalRequest, data)
    if error:
        return error, 400

    # Hard rule: reject if outside 24h messaging window
    if not parsed.within_24h_window:
        response = {
            "approved": False,
            "modifications": None,
            "needs_escalation": False,
            "decision_reasoning": "Cannot send DM - outside 24-hour messaging window. Customer must message first.",
            "audit_data": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": "nemotron:8b-q5_K_M",
                "rule_triggered": "24h_window_expired"
            }
        }
        SupabaseService.log_decision(
            event_type="dm_reply_approval",
            action="rejected",
            resource_type="dm",
            resource_id=parsed.message_id,
            user_id=parsed.business_account_id,
            details={"reason": "24h_window_expired"},
            ip_address=request.remote_addr
        )
        return jsonify(response)

    # Hard rule: escalate VIP customers
    customer_history = parsed.customer_history
    lifetime_value = customer_history.lifetime_value if customer_history else 0
    sentiment_history = customer_history.sentiment_history if customer_history else "neutral"
    previous_interactions = customer_history.previous_interactions if customer_history else 0

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
        response = {
            "approved": False,
            "modifications": None,
            "needs_escalation": True,
            "escalation_reason": escalation_reason,
            "suggested_team": "support" if parsed.detected_intent in ESCALATION_INTENTS else "sales",
            "decision_reasoning": escalation_reason,
            "audit_data": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": "nemotron:8b-q5_K_M",
                "rule_triggered": "forced_escalation"
            }
        }
        SupabaseService.log_decision(
            event_type="dm_reply_approval",
            action="escalated",
            resource_type="dm",
            resource_id=parsed.message_id,
            user_id=parsed.business_account_id,
            details={"reason": escalation_reason, "lifetime_value": lifetime_value},
            ip_address=request.remote_addr
        )
        return jsonify(response)

    # Fetch context from Supabase
    account_info = SupabaseService.get_account_info(parsed.business_account_id)
    dm_history = SupabaseService.get_dm_history(parsed.sender_id, parsed.business_account_id)

    # Format DM history for prompt
    dm_history_str = "No previous DMs"
    if dm_history:
        dm_history_str = "\n".join([
            f"  [{m.get('direction', '?')}] {m.get('message_text', '')[:100]}"
            for m in dm_history[:5]
        ])

    # Build prompt
    prompt = PROMPTS["dm"].format(
        account_username=account_info.get("username", "unknown"),
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

    # Invoke agent with tools
    result, status_code = run_approval(prompt, "dm")
    if status_code != 200:
        return jsonify(result), status_code

    latency = result.pop("_latency_ms", 0)
    tools_called = result.pop("_tools_called", [])

    approved = result.get("approved", False)
    modifications = result.get("modifications")
    needs_escalation = result.get("needs_escalation", False)
    quality_score = result.get("quality_score", 0)
    reasoning = result.get("reasoning", "No reasoning provided")

    response = {
        "approved": approved,
        "modifications": modifications,
        "needs_escalation": needs_escalation,
        "decision_reasoning": reasoning,
        "confidence": quality_score / 10.0 if quality_score else 0,
        "quality_score": quality_score,
        "audit_data": {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "agent_model": "nemotron:8b-q5_K_M",
            "latency_ms": latency,
            "tools_called": tools_called,
            "analysis_factors": ["appropriateness", "personalization", "escalation_need", "format"],
            "context_used": ["account_info", "dm_history", "customer_history"]
        }
    }

    action = "escalated" if needs_escalation else ("approved" if approved else "rejected")

    SupabaseService.log_decision(
        event_type="dm_reply_approval",
        action=action,
        resource_type="dm",
        resource_id=parsed.message_id,
        user_id=parsed.business_account_id,
        details={
            "proposed_reply": parsed.proposed_reply,
            "approved_reply": modifications.get("reply_text") if modifications else None,
            "quality_score": quality_score,
            "needs_escalation": needs_escalation,
            "reasoning": reasoning,
            "latency_ms": latency
        },
        ip_address=request.remote_addr
    )

    return jsonify(response)
