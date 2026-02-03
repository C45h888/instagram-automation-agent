from datetime import datetime, timezone
from fastapi import APIRouter, Request
from services.validation import PostApprovalRequest
from services.supabase_service import SupabaseService
from routes.approve_base import ApprovalConfig, approval_pipeline
from services.prompt_service import PromptService
from config import OLLAMA_MODEL, MAX_CAPTION_LENGTH, MAX_HASHTAG_COUNT

approve_post_router = APIRouter()


# ================================
# Hooks
# ================================
def _hard_rules(parsed, request):
    """Post-specific hard rules: hashtag count and caption length."""
    issues = []

    actual_hashtag_count = parsed.hashtag_count or len(parsed.hashtags)
    actual_caption_length = parsed.caption_length or len(parsed.proposed_caption)

    if actual_hashtag_count > MAX_HASHTAG_COUNT:
        issues.append(f"Too many hashtags ({actual_hashtag_count}, max {MAX_HASHTAG_COUNT})")

    if actual_caption_length > MAX_CAPTION_LENGTH:
        issues.append(f"Caption too long ({actual_caption_length} chars, max {MAX_CAPTION_LENGTH})")

    if not issues:
        return None  # No hard rule triggered

    recommendations = [
        "Reduce hashtags to 8-9 relevant tags" if "hashtag" in issues[0].lower() else None,
        "Shorten caption to under 2200 characters" if len(issues) > 1 or "Caption" in issues[0] else None,
    ]
    recommendations = [r for r in recommendations if r]

    return {
        "approved": False,
        "modifications": None,
        "quality_score": 0,
        "decision_reasoning": f"Hard rule violation: {'; '.join(issues)}",
        "issues": issues,
        "recommendations": recommendations,
        "audit_data": {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "agent_model": OLLAMA_MODEL,
            "rule_triggered": "hard_rule_violation"
        },
        "_action": "rejected",
        "_audit_details": {"reason": "hard_rule_violation", "issues": issues},
    }


def _fetch_context(parsed):
    return {
        "account": SupabaseService.get_account_info(parsed.business_account_id),
        "performance": SupabaseService.get_recent_post_performance(parsed.business_account_id),
    }


def _build_prompt(parsed, ctx):
    asset_tags = parsed.asset.tags if parsed.asset else []
    actual_hashtag_count = parsed.hashtag_count or len(parsed.hashtags)
    actual_caption_length = parsed.caption_length or len(parsed.proposed_caption)

    return PromptService.get("post").format(
        account_username=ctx["account"].get("username", "unknown"),
        account_type=ctx["account"].get("name", "business"),
        business_account_id=parsed.business_account_id,
        proposed_caption=parsed.proposed_caption[:2200],
        hashtags=", ".join(parsed.hashtags) if parsed.hashtags else "none",
        hashtag_count=actual_hashtag_count,
        caption_length=actual_caption_length,
        post_type=parsed.post_type,
        scheduled_time=parsed.scheduled_time or "not scheduled",
        asset_tags=", ".join(asset_tags) if asset_tags else "none",
        avg_likes=ctx["performance"].get("avg_likes", 0),
        avg_comments=ctx["performance"].get("avg_comments", 0),
        avg_engagement_rate=ctx["performance"].get("avg_engagement_rate", 0),
    )


def _build_response(parsed, result, latency, tools_called):
    quality_score = result.get("quality_score", 0)
    return {
        "approved": result.get("approved", False),
        "modifications": result.get("modifications"),
        "quality_score": quality_score,
        "decision_reasoning": result.get("reasoning", "No reasoning provided"),
        "engagement_prediction": result.get("engagement_prediction", parsed.engagement_prediction),
        "brand_alignment_score": quality_score / 10.0 if quality_score else 0,
    }


def _build_audit_details(parsed, result, latency):
    mods = result.get("modifications")
    return {
        "proposed_caption": parsed.proposed_caption[:200],
        "approved_caption": mods.get("caption")[:200] if mods and mods.get("caption") else None,
        "quality_score": result.get("quality_score", 0),
        "engagement_prediction": result.get("engagement_prediction", parsed.engagement_prediction),
        "reasoning": result.get("reasoning", ""),
        "latency_ms": latency,
    }


# ================================
# Config
# ================================
_config = ApprovalConfig(
    task_type="post",
    event_type="post_approval",
    resource_type="post",
    analysis_factors=["caption_quality", "brand_alignment", "hashtag_strategy", "engagement_potential", "compliance"],
    context_used=["account_info", "post_performance_benchmarks"],
    get_resource_id=lambda p: p.scheduled_post_id,
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
@approve_post_router.post("/approve/post")
async def approve_post(parsed: PostApprovalRequest, request: Request):
    """Approve or reject a proposed post caption from N8N."""
    return await approval_pipeline(parsed, request, _config)
