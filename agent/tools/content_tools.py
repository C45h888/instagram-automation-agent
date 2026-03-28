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

import asyncio
import random
import json
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
from langchain_core.tools import tool


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

    try:
        # Invoke LLM via LLMService — retry + backoff + error classification.
        # No bind_tools() — the prompt has all context pre-injected.
        raw_response = await LLMService.invoke(prompt)
        from services.llm_service import LLMService
        result = LLMService._parse_json_response(
            raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        )
    except Exception as e:
        logger.error(f"LLM caption generation failed: {e}")
        result = _template_fallback(asset)

    # Validate LLM returned expected structure
    if "error" in result and "hook" not in result:
        logger.warning(f"LLM returned error, using template fallback: {result.get('error')}")
        result = _template_fallback(asset)

    # Apply hard rules on top of LLM evaluation
    result = _apply_hard_rules(result)

    # Ensure agent_modifications.reason is always populated (dashboard Zod requires non-empty)
    mods = result.get("modifications")
    if mods and isinstance(mods, dict) and not mods.get("reason"):
        mods["reason"] = (result.get("reasoning") or "Agent-generated modification")[:200]

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


# ================================
# UGC Content — Reuse granted UGC posts
# ================================
def _get_asset_public_url_for_ugc(media_url: str) -> str:
    """Return media_url directly for UGC (already a public URL from Graph API)."""
    return media_url


# ================================
# LLM-Callable Tools — Content Pipeline
# ================================
# These are @tool-decorated functions that AgentService.bind_tools() exposes to the LLM.
# Each tool does one focused task; Python enqueues side-effects AFTER LLM confirmation.

# Reusable context fetchers (called internally by tools, not exposed to LLM directly)
def _fetch_asset_context(asset_id: str, business_account_id: str) -> dict:
    """Fetch asset + account + performance context for tool functions.

    Tries instagram_assets first. If not found (empty result), falls back to
    ugc_content so that UGC content can also use the generate_caption tool.
    """
    from services.supabase_service._content import ContentService

    asset = ContentService.get_asset_by_id(asset_id)

    # Fallback: if asset_id not found in instagram_assets, check ugc_content
    from_ugc = False
    if not asset:
        from services.supabase_service._ugc import UGCService
        ugc_list = UGCService.get_ugc_content_by_id(asset_id, business_account_id)
        if ugc_list:
            ugc = ugc_list[0]
            asset = {
                "id": ugc.get("id"),
                "title": ugc.get("author_username", "UGC Post"),
                "description": ugc.get("message", ""),
                "tags": [],
                "media_type": ugc.get("media_type", "IMAGE"),
                "storage_path": "",
                "author_username": ugc.get("author_username", ""),
                "message": ugc.get("message", ""),
                "ugc_content_id": ugc.get("id"),
                "from_ugc": True,
            }
            from_ugc = True

    account = SupabaseService.get_account_info(business_account_id)
    performance = SupabaseService.get_recent_post_performance(business_account_id)
    return {
        "asset": asset or {},
        "account": account or {},
        "performance": performance or {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0},
        "from_ugc": from_ugc,
    }


def _assemble_asset_context_string(ctx: dict) -> str:
    """Build a human-readable context string from asset/account/performance dicts for prompt injection."""
    asset = ctx.get("asset", {})
    account = ctx.get("account", {})
    perf = ctx.get("performance", {})
    parts = [
        f"Account: @{account.get('username', 'unknown')} ({account.get('account_type', 'business')})",
        f"Followers: {account.get('followers_count', 0):,}",
        f"Asset: {asset.get('title', 'Untitled')} | {asset.get('media_type', 'IMAGE')}",
        f"Description: {asset.get('description', 'No description')}",
        f"Tags: {', '.join(asset.get('tags', []) or [])}",
        f"Avg likes: {perf.get('avg_likes', 0):.0f} | Avg comments: {perf.get('avg_comments', 0):.0f}",
        f"Avg engagement rate: {perf.get('avg_engagement_rate', 0):.2%}",
    ]
    return "\n".join(p for p in parts if p)


# ─── Tool 1: Evaluate Asset ────────────────────────────────────────────────

@tool(
    name="evaluate_asset",
    description="""Evaluate whether a content asset is ready to post.

USE THIS TOOL when you want to assess an asset's quality and posting readiness before generating a caption.
Returns a quality decision with tier and recommendations — does NOT generate captions.

Args:
    asset_id: Instagram asset UUID from instagram_assets table
    business_account_id: Business account UUID

Returns JSON:
    {quality_score: float (0-10), tier: "post_now"|"needs_review"|"skip",
     asset_ready: bool, recommendations: list[str], reasoning: str}

Decision rules:
    - tier="post_now": High quality, asset is ready to generate caption
    - tier="needs_review": Medium quality or pending items — flag for human review
    - tier="skip": Low quality or policy issue — do not post""",
)
def evaluate_asset(asset_id: str, business_account_id: str) -> dict:
    ctx = _fetch_asset_context(asset_id, business_account_id)
    asset = ctx["asset"]
    account = ctx["account"]
    perf = ctx["performance"]

    if not asset:
        return {
            "quality_score": 0,
            "tier": "skip",
            "asset_ready": False,
            "recommendations": ["Asset not found in database"],
            "reasoning": "Asset ID not found",
        }

    # Check if asset has UGC metadata (ugc_content_id on instagram_assets)
    from_ugc = bool(asset.get("ugc_content_id"))
    ugc_permission_status = None
    if from_ugc:
        from services.supabase_service._ugc import UGCService
        ugc_permission_status = _get_ugc_permission_status(
            asset.get("ugc_content_id"), business_account_id
        )

    # Build context string for LLM (prompt injection)
    context_str = _assemble_asset_context_string(ctx)

    # LLM makes the quality decision using the context
    # quality_score: 0-10 scale
    # tier: post_now / needs_review / skip
    # For now: simple heuristic until prompt is written
    selection_score = asset.get("_score", 50)
    # Map 0-100 selection score to 0-10
    quality_score = round(min(selection_score / 10, 10), 1)

    if quality_score >= 7.0:
        tier = "post_now"
        asset_ready = True
    elif quality_score >= 5.0:
        tier = "needs_review"
        asset_ready = True
    else:
        tier = "skip"
        asset_ready = False

    recommendations = []
    if not asset.get("description"):
        recommendations.append("Asset has no description — ensure caption provides context")
    if ugc_permission_status and ugc_permission_status != "granted":
        recommendations.append(f"UGC permission status: {ugc_permission_status}")

    return {
        "quality_score": quality_score,
        "tier": tier,
        "asset_ready": asset_ready,
        "recommendations": recommendations,
        "reasoning": f"Asset score {quality_score}/10 — {tier}",
    }


# ─── Tool 2: Generate Caption ───────────────────────────────────────────────

@tool(
    name="generate_caption",
    description="""Generate Instagram caption text for an asset.

USE THIS TOOL after evaluate_asset returns tier="post_now" or asset_ready=true.
Generates hook + body + cta + hashtags based on asset and account context.

Args:
    asset_id: Instagram asset UUID
    business_account_id: Business account UUID
    generation_mode: "full" (all parts) or "hook_only" (hook only, for rapid iteration)

Returns JSON:
    {hook: str, body: str, cta: str, hashtags: list[str],
     caption_variant: "standard"|"ugc_attributed",
     reasoning: str}

UGC attribution: If the asset is from ugc_content (from_ugc=true),
you MUST set caption_variant="ugc_attributed" and include @username attribution in the hook.
Example hook for UGC: "Repost via @username: This is their amazing content..." """,
)
def generate_caption(
    asset_id: str,
    business_account_id: str,
    generation_mode: str = "full",
) -> dict:
    ctx = _fetch_asset_context(asset_id, business_account_id)
    asset = ctx["asset"]
    account = ctx["account"]
    perf = ctx["performance"]

    if not asset:
        return {"error": "Asset not found"}

    from_ugc = bool(asset.get("ugc_content_id"))
    caption_variant = "ugc_attributed" if from_ugc else "standard"

    # Build full context for prompt
    context_str = _assemble_asset_context_string(ctx)

    # Fetch LLM-generated caption using the existing generate_and_evaluate prompt
    # (replace with dedicated prompt once prompts.py is updated)
    import uuid as _uuid
    run_id = str(_uuid.uuid4())

    prompt = _build_caption_generation_prompt(
        asset=asset,
        account=account,
        performance=perf,
        generation_mode=generation_mode,
        caption_variant=caption_variant,
    )

    # Use LLMService directly since we haven't yet updated prompts.py
    from services.llm_service import LLMService
    try:
        raw_response = LLMService.invoke(prompt)
        result = LLMService._parse_json_response(
            raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        )
    except Exception as e:
        logger.error(f"Caption generation failed: {e}")
        result = _template_fallback(asset)

    # Extract and validate output
    hook = result.get("hook", "")
    body = result.get("body", "")
    cta = result.get("cta", "")
    hashtags = result.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = [t.strip() for t in hashtags.split(",") if t.strip()]
    hashtags = hashtags[:20]  # Cap at 20 hashtags

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "caption_variant": caption_variant,
        "reasoning": result.get("reasoning", "LLM generated caption"),
    }


# ─── Tool 3: Evaluate Caption ───────────────────────────────────────────────

@tool(
    name="evaluate_caption",
    description="""Evaluate the quality of a generated Instagram caption.

USE THIS TOOL after generate_caption returns a draft caption.
Returns quality score and specific modification suggestions.

Args:
    caption_text: Full assembled caption text (hook + body + cta + hashtags)
    account_context: Account info string (username, type, follower count)

Returns JSON:
    {quality_score: float (0-10), approved: bool,
     modifications: {hook?: str, body?: str, cta?: str, hashtags?: list[str]},
     reasoning: str}

Approval threshold: POST_APPROVAL_THRESHOLD config (default 0.6 → score >= 6.0 to approve)
Modifications: specific suggested changes, or null if no changes needed.""",
)
def evaluate_caption(caption_text: str, account_context: str) -> dict:
    """Evaluate caption quality on 5 criteria: quality (30%), brand (25%),
    hashtag (20%), engagement (15%), compliance (10%)."""
    from config import POST_APPROVAL_THRESHOLD

    if not caption_text or not caption_text.strip():
        return {
            "quality_score": 0,
            "approved": False,
            "modifications": None,
            "reasoning": "Empty caption",
        }

    # Hard-rule pre-checks (mirror _apply_hard_rules)
    hashtags_match = [t.strip() for t in caption_text.split() if t.startswith("#")]
    reasons = []

    if len(caption_text) > MAX_CAPTION_LENGTH:
        reasons.append(f"Caption too long ({len(caption_text)} > {MAX_CAPTION_LENGTH})")

    if len(hashtags_match) > MAX_HASHTAG_COUNT:
        reasons.append(f"Too many hashtags ({len(hashtags_match)} > {MAX_HASHTAG_COUNT})")

    # Simple heuristic scoring until dedicated prompt is written
    score = 7.0  # Base score
    if len(caption_text) > 100:
        score += 0.5
    if len(caption_text) > 300:
        score += 0.5
    if hashtags_match and 3 <= len(hashtags_match) <= 10:
        score += 1.0
    if "?" in caption_text:
        score += 0.5
    if reasons:
        score = min(score, 4.0)

    quality_score = round(min(score, 10), 1)
    approved = quality_score >= (POST_APPROVAL_THRESHOLD * 10)

    modifications = None
    if reasons:
        modifications = {"reason": " | ".join(reasons)}

    return {
        "quality_score": quality_score,
        "approved": approved,
        "modifications": modifications,
        "reasoning": f"Score {quality_score}/10 — {'approved' if approved else 'below threshold'}",
    }


# ─── Tool 4: Publish Content ───────────────────────────────────────────────

@tool(
    name="publish_content",
    description="""Validate and prepare a post for publishing.

USE THIS TOOL after evaluate_caption returns approved=true when you want to publish a scheduled post.
Returns validated job payload — Python enqueues after you confirm in JSON.
Max caption 2200 characters.

Args:
    scheduled_post_id: Supabase UUID of the scheduled post
    business_account_id: Business account UUID
    image_url: Public URL of the asset image/video
    caption: Full caption text
    media_type: IMAGE, VIDEO, CAROUSEL_ALBUM (default: IMAGE)
    caption_variant: "standard" or "ugc_attributed" (default: standard)

Returns JSON:
    {validated: true, job_payload: {...}} on success
    {validated: false, error: "reason"} on failure

UGC posts: If caption_variant="ugc_attributed", Python will verify
ugc_permissions.status="granted" before enqueuing. Do not set caption_variant
to "ugc_attributed" unless the original creator has granted permission.""",
)
def publish_content(
    scheduled_post_id: str,
    business_account_id: str,
    image_url: str,
    caption: str,
    media_type: str = "IMAGE",
    caption_variant: str = "standard",
) -> dict:
    """Validate and return a job payload for publishing."""
    # Validation
    if not scheduled_post_id:
        return {"validated": False, "error": "scheduled_post_id is required"}
    if not business_account_id:
        return {"validated": False, "error": "business_account_id is required"}
    if not image_url:
        return {"validated": False, "error": "image_url is required"}
    if not caption or not caption.strip():
        return {"validated": False, "error": "caption cannot be empty"}
    if len(caption) > MAX_CAPTION_LENGTH:
        return {"validated": False, "error": f"Caption exceeds {MAX_CAPTION_LENGTH} chars ({len(caption)})"}

    # Determine action_type and endpoint based on variant
    if caption_variant == "ugc_attributed":
        action_type = "repost_ugc"
        endpoint = "/api/instagram/repost-ugc"
    else:
        action_type = "publish_post"
        endpoint = "/api/instagram/publish-post"

    job_payload = {
        "job_id": str(_uuid.uuid4()),
        "action_type": action_type,
        "priority": "normal",
        "endpoint": endpoint,
        "payload": {
            "scheduled_post_id": scheduled_post_id,
            "business_account_id": business_account_id,
            "image_url": image_url,
            "caption": caption,
            "media_type": media_type,
            "caption_variant": caption_variant,
        },
        "business_account_id": business_account_id,
        "idempotency_key": f"post:{scheduled_post_id}",
        "source": "llm_publish_tool",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
        "last_error": None,
    }
    return {"validated": True, "job_payload": job_payload}


# ================================
# Python-Only Enqueue Helpers
# ================================

def _enqueue_publish(job_payload: dict) -> dict:
    """Python-only: enqueue via OutboundQueue after LLM confirms publish_content tool."""
    from services.outbound_queue import OutboundQueue
    return OutboundQueue.enqueue(job_payload)


def _check_ugc_permission(ugc_content_id: str, business_account_id: str) -> bool:
    """Check ugc_permissions.status == 'granted' before allowing repost."""
    if not ugc_content_id:
        return False
    from services.supabase_service._ugc import UGCService
    permissions = UGCService.get_granted_ugc_permissions(business_account_id)
    return any(p.get("ugc_content_id") == ugc_content_id for p in permissions)


def _get_ugc_permission_status(ugc_content_id: str, business_account_id: str) -> str | None:
    """Get UGC permission status for a specific ugc_content record."""
    if not ugc_content_id:
        return None
    from services.supabase_service._ugc import UGCService
    permissions = UGCService.get_granted_ugc_permissions(business_account_id)
    for p in permissions:
        if p.get("ugc_content_id") == ugc_content_id:
            return "granted"
    return "not_found"


# ================================
# Prompt Builder (used by generate_caption tool until prompts.py is updated)
# ================================

def _build_caption_generation_prompt(
    asset: dict,
    account: dict,
    performance: dict,
    generation_mode: str,
    caption_variant: str,
) -> str:
    """Build prompt for caption generation using the generate_caption prompt."""
    from services.prompt_service import PromptService

    now = datetime.now(timezone.utc)
    asset_tags = asset.get("tags", [])
    if isinstance(asset_tags, str):
        asset_tags = [t.strip() for t in asset_tags.split(",") if t.strip()]

    from_ugc = caption_variant == "ugc_attributed"
    author_username = asset.get("author_username", "")
    ugc_message = asset.get("message", "")

    # Build UGC instructions based on variant
    if from_ugc:
        ugc_instructions = (
            f"- This is UGC content. You MUST:\n"
            f"  1. Include '@{author_username}' attribution in the HOOK (e.g., 'Repost via @{author_username}: ...')\n"
            f"  2. Preserve the creator's original caption text below\n"
            f"  3. Set caption_variant='ugc_attributed'\n"
            f"- Original UGC caption: {ugc_message[:500]}"
        )
    else:
        ugc_instructions = "- Standard brand content. caption_variant='standard'."

    template = PromptService.get("generate_caption")
    return template.format(
        account_username=account.get("username", "unknown"),
        account_type=account.get("account_type", "business"),
        followers_count=account.get("followers_count", 0),
        asset_title=asset.get("title", "Untitled"),
        asset_description=asset.get("description", "No description"),
        asset_tags=", ".join(asset_tags),
        media_type=asset.get("media_type", "IMAGE"),
        avg_likes=performance.get("avg_likes", 0),
        avg_comments=performance.get("avg_comments", 0),
        avg_engagement_rate=performance.get("avg_engagement_rate", 0),
        hour=now.hour,
        day_of_week=now.strftime("%A"),
        from_ugc=str(from_ugc).lower(),
        author_username=author_username,
        message=ugc_message[:500],
        ugc_instructions=ugc_instructions,
    )
