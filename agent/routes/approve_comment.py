from fastapi import APIRouter, Request
from services.validation import CommentApprovalRequest
from services.supabase_service import SupabaseService
from routes.approve_base import ApprovalConfig, approval_pipeline
from services.prompt_service import PromptService

approve_comment_router = APIRouter()


# ================================
# Hooks
# ================================
def _fetch_context(parsed):
    return {
        "post": SupabaseService.get_post_context(parsed.post_id),
        "account": SupabaseService.get_account_info(parsed.business_account_id),
    }


def _build_prompt(parsed, ctx):
    return PromptService.get("comment").format(
        account_username=ctx["account"].get("username", "unknown"),
        account_type=ctx["account"].get("name", "business"),
        business_account_id=parsed.business_account_id,
        post_id=parsed.post_id,
        post_caption=ctx["post"].get("caption", "N/A")[:300],
        like_count=ctx["post"].get("like_count", 0),
        comments_count=ctx["post"].get("comments_count", 0),
        engagement_rate=ctx["post"].get("engagement_rate", 0),
        comment_text=parsed.comment_text[:500],
        commenter_username=parsed.commenter_username or "unknown",
        detected_intent=parsed.detected_intent,
        sentiment=parsed.sentiment,
        proposed_reply=parsed.proposed_reply[:500],
    )


def _build_response(parsed, result, latency, tools_called):
    return {
        "approved": result.get("approved", False),
        "modifications": result.get("modifications"),
        "decision_reasoning": result.get("reasoning", "No reasoning provided"),
        "confidence": parsed.confidence,
        "quality_score": result.get("quality_score", 0),
        "sentiment": parsed.sentiment,
    }


def _build_audit_details(parsed, result, latency):
    mods = result.get("modifications")
    return {
        "proposed_reply": parsed.proposed_reply,
        "approved_reply": mods.get("reply_text") if mods else None,
        "quality_score": result.get("quality_score", 0),
        "reasoning": result.get("reasoning", ""),
        "latency_ms": latency,
    }


# ================================
# Config
# ================================
_config = ApprovalConfig(
    task_type="comment",
    event_type="comment_reply_approval",
    resource_type="comment",
    analysis_factors=["sentiment", "tone", "relevance", "brand_voice"],
    context_used=["post_caption", "engagement_metrics", "account_info"],
    get_resource_id=lambda p: p.comment_id,
    get_user_id=lambda p: p.business_account_id,
    fetch_context=_fetch_context,
    build_prompt=_build_prompt,
    build_response=_build_response,
    build_audit_details=_build_audit_details,
)


# ================================
# Route
# ================================
@approve_comment_router.post("/approve/comment-reply")
async def approve_comment_reply(parsed: CommentApprovalRequest, request: Request):
    """Approve or reject a proposed comment reply from N8N."""
    return await approval_pipeline(parsed, request, _config)
