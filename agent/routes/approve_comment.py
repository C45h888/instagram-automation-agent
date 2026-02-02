from flask import Blueprint, request, jsonify
from services.validation import require_api_key, CommentApprovalRequest, validate_request
from services.supabase_service import SupabaseService
from services.llm_service import LLMService
from routes.health import track_request
from prompts import PROMPTS
from config import logger

approve_comment_bp = Blueprint("approve_comment", __name__)


@approve_comment_bp.route("/approve/comment-reply", methods=["POST"])
@require_api_key
def approve_comment_reply():
    """Approve or reject a proposed comment reply from N8N.

    N8N sends proposed reply + context → Agent evaluates → returns decision.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "validation_error", "message": "Request body must be JSON"}), 400

    # Validate request
    parsed, error = validate_request(CommentApprovalRequest, data)
    if error:
        return error, 400

    # Fetch context from Supabase
    post_context = SupabaseService.get_post_context(parsed.post_id)
    account_info = SupabaseService.get_account_info(parsed.business_account_id)

    # Build prompt with all context
    prompt = PROMPTS["comment"].format(
        account_username=account_info.get("instagram_business_username", "unknown"),
        account_type=account_info.get("name", "business"),
        post_caption=post_context.get("caption", "N/A")[:300],
        like_count=post_context.get("like_count", 0),
        comments_count=post_context.get("comments_count", 0),
        engagement_rate=post_context.get("engagement_rate", 0),
        comment_text=parsed.comment_text[:500],
        commenter_username=parsed.commenter_username or "unknown",
        detected_intent=parsed.detected_intent,
        sentiment=parsed.sentiment,
        proposed_reply=parsed.proposed_reply[:500],
    )

    # Invoke Nemotron
    result = LLMService.analyze(prompt)

    # Handle LLM failure
    if "error" in result and result["error"] != "json_parse_failed":
        logger.error(f"LLM failed for comment approval: {result}")
        return jsonify({
            "approved": "pending_manual_review",
            "error": "model_unavailable",
            "message": "AI model could not process request. Please retry.",
        }), 503

    latency = result.pop("_latency_ms", 0)
    track_request(latency)

    # Build response
    approved = result.get("approved", False)
    modifications = result.get("modifications")
    quality_score = result.get("quality_score", 0)
    reasoning = result.get("reasoning", "No reasoning provided")

    response = {
        "approved": approved,
        "modifications": modifications,
        "decision_reasoning": reasoning,
        "confidence": parsed.confidence,
        "quality_score": quality_score,
        "sentiment": parsed.sentiment,
        "audit_data": {
            "analyzed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "agent_model": "nemotron:8b-q5_K_M",
            "latency_ms": latency,
            "analysis_factors": ["sentiment", "tone", "relevance", "brand_voice"],
            "context_used": ["post_caption", "engagement_metrics", "account_info"]
        }
    }

    # Log to audit_log
    SupabaseService.log_decision(
        event_type="comment_reply_approval",
        action="approved" if approved else "rejected",
        resource_type="comment",
        resource_id=parsed.comment_id,
        user_id=parsed.business_account_id,
        details={
            "proposed_reply": parsed.proposed_reply,
            "approved_reply": modifications.get("reply_text") if modifications else None,
            "quality_score": quality_score,
            "reasoning": reasoning,
            "latency_ms": latency
        },
        ip_address=request.remote_addr
    )

    return jsonify(response)
