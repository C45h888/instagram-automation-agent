from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from services.validation import PostApprovalRequest, validate_request
from services.supabase_service import SupabaseService
from routes.approve_base import run_approval
from prompts import PROMPTS
from config import logger, MAX_CAPTION_LENGTH, MAX_HASHTAG_COUNT

approve_post_bp = Blueprint("approve_post", __name__)


@approve_post_bp.route("/approve/post", methods=["POST"])
def approve_post():
    """Approve or reject a proposed post caption from N8N.

    Includes hard rules for hashtag count and caption length.
    Auth handled by middleware.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "validation_error", "message": "Request body must be JSON"}), 400

    # Validate request
    parsed, error = validate_request(PostApprovalRequest, data)
    if error:
        return error, 400

    # Hard rules (override LLM)
    issues = []

    actual_hashtag_count = parsed.hashtag_count or len(parsed.hashtags)
    actual_caption_length = parsed.caption_length or len(parsed.proposed_caption)

    if actual_hashtag_count > MAX_HASHTAG_COUNT:
        issues.append(f"Too many hashtags ({actual_hashtag_count}, max {MAX_HASHTAG_COUNT})")

    if actual_caption_length > MAX_CAPTION_LENGTH:
        issues.append(f"Caption too long ({actual_caption_length} chars, max {MAX_CAPTION_LENGTH})")

    if issues:
        response = {
            "approved": False,
            "modifications": None,
            "quality_score": 0,
            "decision_reasoning": f"Hard rule violation: {'; '.join(issues)}",
            "issues": issues,
            "recommendations": [
                "Reduce hashtags to 8-9 relevant tags" if "hashtag" in issues[0].lower() else None,
                "Shorten caption to under 2200 characters" if len(issues) > 1 or "Caption" in issues[0] else None,
            ],
            "audit_data": {
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
                "agent_model": "nemotron:8b-q5_K_M",
                "rule_triggered": "hard_rule_violation"
            }
        }
        response["recommendations"] = [r for r in response["recommendations"] if r]

        SupabaseService.log_decision(
            event_type="post_approval",
            action="rejected",
            resource_type="post",
            resource_id=parsed.scheduled_post_id,
            user_id=parsed.business_account_id,
            details={"reason": "hard_rule_violation", "issues": issues},
            ip_address=request.remote_addr
        )
        return jsonify(response)

    # Fetch context from Supabase
    account_info = SupabaseService.get_account_info(parsed.business_account_id)
    performance = SupabaseService.get_recent_post_performance(parsed.business_account_id)

    # Build prompt
    asset_tags = parsed.asset.tags if parsed.asset else []

    prompt = PROMPTS["post"].format(
        account_username=account_info.get("username", "unknown"),
        account_type=account_info.get("name", "business"),
        business_account_id=parsed.business_account_id,
        proposed_caption=parsed.proposed_caption[:2200],
        hashtags=", ".join(parsed.hashtags) if parsed.hashtags else "none",
        hashtag_count=actual_hashtag_count,
        caption_length=actual_caption_length,
        post_type=parsed.post_type,
        scheduled_time=parsed.scheduled_time or "not scheduled",
        asset_tags=", ".join(asset_tags) if asset_tags else "none",
        avg_likes=performance.get("avg_likes", 0),
        avg_comments=performance.get("avg_comments", 0),
        avg_engagement_rate=performance.get("avg_engagement_rate", 0),
    )

    # Invoke agent with tools
    result, status_code = run_approval(prompt, "post")
    if status_code != 200:
        return jsonify(result), status_code

    latency = result.pop("_latency_ms", 0)
    tools_called = result.pop("_tools_called", [])

    approved = result.get("approved", False)
    modifications = result.get("modifications")
    quality_score = result.get("quality_score", 0)
    engagement_prediction = result.get("engagement_prediction", parsed.engagement_prediction)
    reasoning = result.get("reasoning", "No reasoning provided")

    response = {
        "approved": approved,
        "modifications": modifications,
        "quality_score": quality_score,
        "decision_reasoning": reasoning,
        "engagement_prediction": engagement_prediction,
        "brand_alignment_score": quality_score / 10.0 if quality_score else 0,
        "audit_data": {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "agent_model": "nemotron:8b-q5_K_M",
            "latency_ms": latency,
            "tools_called": tools_called,
            "analysis_factors": ["caption_quality", "brand_alignment", "hashtag_strategy", "engagement_potential", "compliance"],
            "context_used": ["account_info", "post_performance_benchmarks"]
        }
    }

    SupabaseService.log_decision(
        event_type="post_approval",
        action="approved" if approved else "rejected",
        resource_type="post",
        resource_id=parsed.scheduled_post_id,
        user_id=parsed.business_account_id,
        details={
            "proposed_caption": parsed.proposed_caption[:200],
            "approved_caption": modifications.get("caption")[:200] if modifications and modifications.get("caption") else None,
            "quality_score": quality_score,
            "engagement_prediction": engagement_prediction,
            "reasoning": reasoning,
            "latency_ms": latency
        },
        ip_address=request.remote_addr
    )

    return jsonify(response)
