"""
Content Scheduling Tools
========================
Pure-Python asset scoring, LLM-powered caption generation + self-evaluation
(single call), and backend publish proxy.

Called by content_scheduler.py — NOT registered as LangChain tools
(these are internal pipeline functions, not agent-callable tools).

Functions:
  - _score_asset:              4-factor scoring (freshness, performance, diversity, upload recency)
  - _select_asset:             Score + weighted random from top 30%
  - _generate_and_evaluate:    Single LLM call for caption + self-evaluation
  - _apply_hard_rules:         Post-LLM validation (hashtag count, length, quality)
  - _build_full_caption:       Assemble hook + body + cta + hashtags
  - _publish_post:             Backend proxy with retry
"""

import random
from datetime import datetime, timezone, timedelta

import uuid as _uuid

from config import (
    logger,
    SUPABASE_URL,
    POST_APPROVAL_THRESHOLD,
    MAX_CAPTION_LENGTH,
    MAX_HASHTAG_COUNT,
    CONTENT_SCHEDULER_MAX_ASSETS_TO_SCORE,
)
from services.supabase_service import SupabaseService


# ================================
# Singleton Agent Service (lazy import to avoid circular)
# ================================
_agent_service = None


def _get_agent_service():
    """Lazy import to avoid circular dependency."""
    global _agent_service
    if _agent_service is None:
        from services.agent_service import AgentService
        _agent_service = AgentService()
    return _agent_service


# ================================
# Asset Scoring — Pure Python, No I/O
# ================================
def _score_asset(asset: dict, recent_post_tags: list, now: datetime) -> dict:
    """Score an asset on 4 factors normalized to 100.

    Factors:
      - Freshness    (35): Days since last posted. Never posted = 35.
      - Performance  (25): Historical avg_engagement. No history = 15 (neutral).
      - Diversity    (25): Tag overlap with recent posts (Jaccard distance).
      - Upload Recency (15): Newer uploads preferred.

    Args:
        asset: Dict with keys: last_posted, post_count, avg_engagement, tags, created_at
        recent_post_tags: List of hashtag arrays from recent published posts
        now: Current UTC datetime

    Returns:
        {"total": float, "factors": {"freshness": float, ...}}
    """
    factors = {}

    # --- Freshness (35 max) ---
    last_posted = asset.get("last_posted")
    if not last_posted:
        factors["freshness"] = 35.0
    else:
        if isinstance(last_posted, str):
            last_posted = datetime.fromisoformat(last_posted.replace("Z", "+00:00"))
        days_since = (now - last_posted).total_seconds() / 86400
        if days_since <= 7:
            # Should be filtered out by SQL, but safety net
            factors["freshness"] = 0.0
        elif days_since >= 30:
            factors["freshness"] = 35.0
        else:
            # Linear interpolation: 7 days = 0, 30 days = 35
            factors["freshness"] = ((days_since - 7) / 23) * 35.0

    # --- Performance (25 max) ---
    post_count = asset.get("post_count", 0) or 0
    avg_engagement = asset.get("avg_engagement", 0) or 0
    if post_count > 0 and avg_engagement > 0:
        # Normalize: engagement of 1.0 (100%) = max score
        factors["performance"] = min(avg_engagement * 25, 25.0)
    else:
        # Neutral default for unposted assets
        factors["performance"] = 15.0

    # --- Diversity (25 max) ---
    asset_tags = asset.get("tags") or []
    if isinstance(asset_tags, str):
        asset_tags = [t.strip() for t in asset_tags.split(",") if t.strip()]
    asset_tags_set = set(t.lower() for t in asset_tags)

    if not asset_tags_set or not recent_post_tags:
        # No tags or no recent posts = max diversity
        factors["diversity"] = 25.0
    else:
        # Union of all recent post tags
        recent_tags_union = set()
        for tag_list in recent_post_tags:
            if isinstance(tag_list, list):
                recent_tags_union.update(t.lower() for t in tag_list)

        if not recent_tags_union:
            factors["diversity"] = 25.0
        else:
            # Jaccard overlap: intersection / union
            intersection = asset_tags_set & recent_tags_union
            union = asset_tags_set | recent_tags_union
            overlap = len(intersection) / len(union) if union else 0
            # 0 overlap = 25, full overlap = 5
            factors["diversity"] = 25.0 - (overlap * 20.0)

    # --- Upload Recency (15 max) ---
    created_at = asset.get("created_at")
    if created_at:
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        days_since_upload = (now - created_at).total_seconds() / 86400
        if days_since_upload < 7:
            factors["upload_recency"] = 15.0
        elif days_since_upload >= 30:
            factors["upload_recency"] = 5.0
        else:
            # Linear decay: 7 days = 15, 30 days = 5
            factors["upload_recency"] = 15.0 - ((days_since_upload - 7) / 23) * 10.0
    else:
        factors["upload_recency"] = 10.0  # Neutral if no created_at

    total = sum(factors.values())
    return {"total": round(total, 2), "factors": {k: round(v, 2) for k, v in factors.items()}}


# ================================
# Asset Selection — Orchestrator
# ================================
async def select_asset(business_account_id: str) -> dict | None:
    """Select the best asset for posting using scored weighted random.

    Pipeline:
      1. Fetch eligible assets (7-day cooldown already applied by SQL)
      2. Fetch recent post tags for diversity scoring
      3. Score each asset
      4. Weighted random from top 30%

    Returns asset dict with score/factors attached, or None if no eligible assets.
    """
    assets = SupabaseService.get_eligible_assets(
        business_account_id,
        limit=CONTENT_SCHEDULER_MAX_ASSETS_TO_SCORE,
    )

    if not assets:
        logger.info(f"No eligible assets for account {business_account_id}")
        return None

    recent_tags = SupabaseService.get_recent_post_tags(business_account_id)
    now = datetime.now(timezone.utc)

    # Score all assets
    scored = []
    for asset in assets:
        score = _score_asset(asset, recent_tags, now)
        scored.append({**asset, "_score": score["total"], "_factors": score["factors"]})

    # Sort descending by score
    scored.sort(key=lambda a: a["_score"], reverse=True)

    # Take top 30% (minimum 1)
    top_count = max(1, len(scored) * 30 // 100)
    candidates = scored[:top_count]

    # Weighted random selection (weights = scores)
    weights = [c["_score"] for c in candidates]
    # Ensure no zero weights
    weights = [max(w, 0.1) for w in weights]

    selected = random.choices(candidates, weights=weights, k=1)[0]

    logger.info(
        f"Selected asset '{selected.get('title', 'untitled')}' "
        f"(score={selected['_score']}, path={selected.get('storage_path', '?')})"
    )
    return selected


# ================================
# Public URL for Supabase Storage Asset
# ================================
def _get_asset_public_url(storage_path: str) -> str:
    """Build public URL for an asset in the instagram-assets bucket."""
    base = SUPABASE_URL.rstrip("/")
    return f"{base}/storage/v1/object/public/instagram-assets/{storage_path}"


# ================================
# Caption Generation + Self-Evaluation (Single LLM Call)
# ================================
async def generate_and_evaluate(
    asset: dict,
    account: dict,
    performance: dict,
) -> dict:
    """Generate caption + evaluate quality in a single LLM call.

    Mirrors _analyze_message pattern from automation_tools.py.

    Args:
        asset: Selected asset dict (with _score, _factors)
        account: Business account dict (username, account_type, followers_count)
        performance: From get_recent_post_performance (avg_likes, avg_comments, avg_engagement_rate)

    Returns:
        {hook, body, cta, hashtags, quality_score, approved, modifications, reasoning}
    """
    from services.prompt_service import PromptService

    now = datetime.now(timezone.utc)

    prompt = PromptService.get("generate_and_evaluate_caption").format(
        account_username=account.get("username", "unknown"),
        account_type=account.get("account_type", "business"),
        followers_count=account.get("followers_count", 0),
        asset_title=asset.get("title", "Untitled"),
        asset_description=asset.get("description", "No description"),
        asset_tags=", ".join(asset.get("tags", []) if isinstance(asset.get("tags"), list) else []),
        media_type=asset.get("media_type", "IMAGE"),
        avg_likes=performance.get("avg_likes", 0),
        avg_comments=performance.get("avg_comments", 0),
        avg_engagement_rate=performance.get("avg_engagement_rate", 0),
        hour=now.hour,
        day_of_week=now.strftime("%A"),
        selection_score=asset.get("_score", 0),
    )

    agent = _get_agent_service()

    try:
        result = await agent.analyze_async(prompt)
    except Exception as e:
        logger.error(f"LLM caption generation failed: {e}")
        result = _template_fallback(asset)

    # Validate LLM returned expected structure
    if "error" in result and "hook" not in result:
        logger.warning(f"LLM returned error, using template fallback: {result.get('error')}")
        result = _template_fallback(asset)

    # Apply hard rules on top of LLM evaluation
    result = _apply_hard_rules(result)

    return result


def _template_fallback(asset: dict) -> dict:
    """Fallback caption when LLM generation fails."""
    tags = asset.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    title = asset.get("title", "")
    description = asset.get("description", "")

    return {
        "hook": title or "Check this out!",
        "body": description or "",
        "cta": "What do you think? Let us know in the comments!",
        "hashtags": tags[:8] if tags else [],
        "quality_score": 0,
        "approved": False,
        "modifications": None,
        "reasoning": "LLM generation failed — template caption for manual review",
    }


# ================================
# Hard Rules — Post-LLM Validation
# ================================
def _apply_hard_rules(result: dict) -> dict:
    """Override LLM evaluation with hard rules.

    Mirrors _apply_hard_escalation_rules pattern from automation_tools.py.
    """
    reasons = []

    # Rule 1: Too many hashtags
    hashtags = result.get("hashtags", [])
    if isinstance(hashtags, list) and len(hashtags) > MAX_HASHTAG_COUNT:
        result["approved"] = False
        reasons.append(f"Too many hashtags ({len(hashtags)} > {MAX_HASHTAG_COUNT})")

    # Rule 2: Caption too long
    full_caption = build_full_caption(result)
    if len(full_caption) > MAX_CAPTION_LENGTH:
        result["approved"] = False
        reasons.append(f"Caption too long ({len(full_caption)} > {MAX_CAPTION_LENGTH} chars)")

    # Rule 3: Quality score below threshold
    quality_score = result.get("quality_score", 0)
    if isinstance(quality_score, (int, float)):
        # LLM scores on 0-10 scale, threshold is 0-1 scale
        normalized = quality_score / 10.0 if quality_score > 1 else quality_score
        if normalized < POST_APPROVAL_THRESHOLD:
            result["approved"] = False
            reasons.append(
                f"Quality score too low ({quality_score} → {normalized:.2f} < {POST_APPROVAL_THRESHOLD})"
            )

    if reasons:
        existing_reasoning = result.get("reasoning", "")
        separator = " | " if existing_reasoning else ""
        result["reasoning"] = existing_reasoning + separator + " | ".join(reasons)

    return result


# ================================
# Caption Assembly
# ================================
def build_full_caption(result: dict) -> str:
    """Assemble hook + body + cta + hashtags into full Instagram caption."""
    parts = []

    hook = result.get("hook", "")
    if hook:
        parts.append(hook)

    body = result.get("body", "")
    if body:
        parts.append(body)

    cta = result.get("cta", "")
    if cta:
        parts.append(cta)

    hashtags = result.get("hashtags", [])
    if hashtags and isinstance(hashtags, list):
        tag_str = " ".join(
            f"#{tag.lstrip('#')}" for tag in hashtags if tag
        )
        if tag_str:
            parts.append(tag_str)

    return "\n\n".join(parts)


# ================================
# Publishing — Queue-First
# ================================
async def publish_post(
    scheduled_post_id: str,
    business_account_id: str,
    image_url: str,
    caption: str,
    media_type: str = "IMAGE",
) -> dict:
    """Enqueue publish job via outbound queue (queue-first pattern).

    Flow:
      1. Set status → 'publishing' (prevents double-publish)
      2. Enqueue job to Redis/Supabase outbound queue
      3. Worker handles HTTP call + 'published'/'failed' transitions

    Returns:
        {"success": bool, "queued": bool, "job_id": str | None, "error": str | None}
    """
    from services.outbound_queue import OutboundQueue

    # Transition: approved → publishing (prevents double-publish on re-enqueue)
    if not SupabaseService.update_scheduled_post_status(scheduled_post_id, "publishing"):
        logger.error(f"Failed to set 'publishing' status for post {scheduled_post_id}")
        return {"success": False, "queued": False, "error": "status_update_failed"}

    job = {
        "job_id": str(_uuid.uuid4()),
        "action_type": "publish_post",
        "priority": "normal",
        "endpoint": "/api/instagram/publish-post",
        "payload": {
            "business_account_id": business_account_id,
            "image_url": image_url,
            "caption": caption,
            "media_type": media_type,
            "scheduled_post_id": scheduled_post_id,
        },
        "business_account_id": business_account_id,
        "idempotency_key": f"post:{scheduled_post_id}",
        "source": "content_scheduler",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
    }

    result = OutboundQueue.enqueue(job)
    if not result.get("success"):
        logger.error(f"Failed to enqueue publish job for post {scheduled_post_id}: {result.get('error')}")
        SupabaseService.update_scheduled_post_status(
            scheduled_post_id, "failed",
            extra_fields={"publish_error": "queue_enqueue_failed"},
        )
        return {"success": False, "queued": False, "error": "queue_enqueue_failed"}

    return {
        "success": True,
        "queued": True,
        "job_id": result.get("job_id"),
        "error": None,
    }
