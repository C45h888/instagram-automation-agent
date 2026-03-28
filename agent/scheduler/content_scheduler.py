"""
Content Scheduler
==================
Scheduled batch pipeline that selects media assets, generates captions
via AgentService.bind_tools() (4-stage LLM pipeline), evaluates quality,
and optionally publishes via the outbound queue.

Replaces the N8N content-scheduler workflow entirely.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account (parallel, semaphore-limited):
     a. Check daily post cap
     b. UGC repost path: check granted UGC permissions → generate + publish
     c. Regular path: select best asset → 4-stage pipeline
        Stage 1: AgentService + evaluate_asset tool → quality tier decision
        Stage 2: Python calls generate_caption tool → caption text
        Stage 3: AgentService + evaluate_caption tool → approval decision
        Stage 4: AgentService + publish_content tool → job enqueued
     d. Store scheduled post (approved or rejected)
     e. If auto-publish + approved: queue handles HTTP call
     f. Log decision to audit_log
  3. Log batch summary + update Prometheus metrics

Error isolation: Each account is wrapped in try/except so a single
failure never crashes the batch.
"""

import asyncio
import json
import time
import uuid as uuid_mod

from config import (
    logger,
    CONTENT_SCHEDULER_MAX_CONCURRENT_GENERATIONS,
    CONTENT_SCHEDULER_MAX_POSTS_PER_DAY,
    CONTENT_SCHEDULER_AUTO_PUBLISH,
)
from services.supabase_service import SupabaseService
from services.agent_service import AgentService
from services.prompt_service import PromptService
from tools.content_tools import (
    select_asset,
    build_full_caption,
    _get_asset_public_url,
    _enqueue_publish,
    _check_ugc_permission,
    _fetch_asset_context,
    _assemble_asset_context_string,
)
from tools.content_tools import (
    evaluate_asset as tool_evaluate_asset,
    generate_caption as tool_generate_caption,
    evaluate_caption as tool_evaluate_caption,
    publish_content as tool_publish_content,
)


# ================================
# Entry Point (called by scheduler)
# ================================
async def content_scheduler_run():
    """Top-level entry point called by APScheduler at configured times.

    Iterates all active business accounts, generates posts,
    logs batch summary, and updates Prometheus metrics.
    """
    # Lazy import to avoid circular dependency at module load time
    from routes.metrics import (
        CONTENT_SCHEDULER_RUNS,
        CONTENT_SCHEDULER_POSTS,
        CONTENT_SCHEDULER_DURATION,
    )

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] Content scheduler cycle starting")

    stats = {"processed": 0, "approved": 0, "rejected": 0, "published": 0, "failed": 0, "no_assets": 0, "capped": 0, "errors": 0}

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping cycle")
            CONTENT_SCHEDULER_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s)")

        semaphore = asyncio.Semaphore(CONTENT_SCHEDULER_MAX_CONCURRENT_GENERATIONS)

        tasks = [
            _process_account_safe(run_id, account, semaphore)
            for account in accounts
        ]
        results = await asyncio.gather(*tasks)

        for account_stats in results:
            for key in stats:
                stats[key] += account_stats.get(key, 0)

        duration = time.time() - start
        status = "success" if stats["errors"] == 0 else "partial"

        _log_batch_summary(run_id, stats, duration)
        CONTENT_SCHEDULER_RUNS.labels(status=status).inc()
        CONTENT_SCHEDULER_DURATION.observe(duration)

        for action in ("approved", "rejected", "published", "failed", "no_assets", "error"):
            count = stats.get(action if action != "error" else "errors", 0)
            if count > 0:
                CONTENT_SCHEDULER_POSTS.labels(action=action).inc(count)

        logger.info(
            f"[{run_id}] Content scheduler cycle complete "
            f"({duration:.1f}s): {stats}"
        )

    except Exception as e:
        duration = time.time() - start
        logger.error(f"[{run_id}] Content scheduler cycle failed ({duration:.1f}s): {e}")
        CONTENT_SCHEDULER_RUNS.labels(status="error").inc()
        CONTENT_SCHEDULER_DURATION.observe(duration)

        SupabaseService.log_decision(
            event_type="content_scheduler_cycle_failed",
            action="error",
            resource_type="content_scheduler",
            resource_id=run_id,
            user_id="system",
            details={"run_id": run_id, "error": str(e), "duration_seconds": round(duration, 2)},
        )


# ================================
# Per-Account Processing (Error-Isolated)
# ================================
async def _process_account_safe(
    run_id: str, account: dict, semaphore: asyncio.Semaphore
) -> dict:
    """Wraps _process_account in try/except. NEVER fails the batch."""
    async with semaphore:
        try:
            return await _process_account(run_id, account)
        except Exception as e:
            account_id = account.get("id", "unknown")
            logger.error(f"[{run_id}] Account {account_id} failed: {e}")
            _log_account_error(run_id, account, e)
            return {"processed": 0, "errors": 1}


async def _process_account(run_id: str, account: dict) -> dict:
    """Generate one post for a single business account.

    Two parallel tracks per account:
    1. UGC repost: granted permissions → generate + publish UGC content
    2. Regular: select asset → 4-stage pipeline

    Daily cap applies across both tracks (total posts per day limit).
    """
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    stats = {"processed": 0, "approved": 0, "rejected": 0, "published": 0, "failed": 0, "no_assets": 0, "capped": 0, "ugc_reposted": 0, "errors": 0}

    # Check daily cap (applies to all posts, UGC + regular)
    posts_today = SupabaseService.get_posts_today_count(account_id)
    if posts_today >= CONTENT_SCHEDULER_MAX_POSTS_PER_DAY:
        logger.info(
            f"[{run_id}] @{account_username}: daily cap reached "
            f"({posts_today}/{CONTENT_SCHEDULER_MAX_POSTS_PER_DAY}) — skipping"
        )
        stats["capped"] = 1
        return stats

    # Track: did we already generate a post this cycle?
    post_generated = False

    # Track 1: UGC Repost Path
    ugc_result = await _process_ugc_repost(run_id, account)
    if ugc_result.get("action") == "ugc_reposted":
        stats["ugc_reposted"] = 1
        stats["published"] = 1
        post_generated = True
    elif ugc_result.get("action") == "no_ugc":
        pass  # No granted UGC, continue to regular path
    elif ugc_result.get("action") == "error":
        stats["errors"] = 1

    # Track 2: Regular Asset Path (only if no UGC post generated and cap not hit)
    if not post_generated:
        result = await _generate_post(run_id, account)
        action = result.get("action", "error")
        stats["processed"] = 1
        if action in stats:
            stats[action] += 1
        else:
            stats["errors"] = 1
        logger.info(f"[{run_id}] @{account_username}: {action}")
    else:
        logger.info(f"[{run_id}] @{account_username}: UGC repost used slot (skipping regular asset)")

    return stats


# ================================
# Single Post Pipeline — 4-Stage Agentic Flow
# ================================
async def _generate_post(run_id: str, account: dict) -> dict:
    """Full 4-stage pipeline for generating one post.

    Stage 1: AgentService.astream_analyze() + evaluate_asset tool → quality tier
    Stage 2: Python calls generate_caption tool → caption text (direct, not via AgentService)
    Stage 3: AgentService.astream_analyze() + evaluate_caption tool → approval
    Stage 4: AgentService.astream_analyze() + publish_content tool → job enqueued

    Why Stage 2 is Python-direct: generate_caption produces text that must be
    passed to Stage 3. Having Python call the tool and extract the text lets us
    inject it into Stage 3's prompt without relying on LLM tool-chaining.
    """
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")

    # ── Stage 0: Select asset ──────────────────────────────────────────────
    asset = await select_asset(account_id)
    if not asset:
        logger.info(f"[{run_id}] No eligible assets for account {account_id}")
        SupabaseService.log_decision(
            event_type="content_scheduler_no_assets",
            action="skipped",
            resource_type="content_scheduler",
            resource_id=run_id,
            user_id=account_id,
            details={"run_id": run_id, "account_username": account.get("username", "")},
        )
        return {"action": "no_assets"}

    asset_id = asset.get("id", "")
    asset_url = _get_asset_public_url(asset.get("storage_path", ""))
    selection_score = asset.get("_score", 0)
    selection_factors = asset.get("_factors", {})

    # ── Stage 1: Evaluate asset quality via AgentService ───────────────────
    agent = AgentService(scope="content")

    stage1_prompt = _build_evaluate_asset_prompt(asset, account, selection_score, selection_factors)
    accumulated = ""
    async for chunk in agent.astream_analyze(stage1_prompt):
        accumulated += chunk

    stage1_result = AgentService._parse_json_response(accumulated)
    tier = stage1_result.get("tier", "skip")
    quality_score = stage1_result.get("quality_score", 0)
    recommendations = stage1_result.get("recommendations", [])

    if tier == "skip":
        logger.info(f"[{run_id}] @{account_username}: asset {asset_id} skipped (tier={tier})")
        _log_evaluate_asset(run_id, asset, account, stage1_result)
        return {"action": "rejected"}

    # ── Stage 2: Generate caption ─────────────────────────────────────────
    # Direct Python call to the tool (not via AgentService) so we can
    # extract hook/body/cta/hashtags and inject them into Stage 3
    stage2_result = tool_generate_caption.invoke({
        "asset_id": asset_id,
        "business_account_id": account_id,
        "generation_mode": "full",
    })
    if "error" in stage2_result:
        logger.error(f"[{run_id}] Caption generation failed: {stage2_result['error']}")
        return {"action": "failed"}

    caption_data = {
        "hook": stage2_result.get("hook", ""),
        "body": stage2_result.get("body", ""),
        "cta": stage2_result.get("cta", ""),
        "hashtags": stage2_result.get("hashtags", []),
    }
    full_caption = build_full_caption(caption_data)
    caption_variant = stage2_result.get("caption_variant", "standard")

    # ── Stage 3: Evaluate caption quality via AgentService ─────────────────
    stage3_prompt = _build_evaluate_caption_prompt(
        caption_data=caption_data,
        account=account,
        caption_variant=caption_variant,
    )
    accumulated = ""
    async for chunk in agent.astream_analyze(stage3_prompt):
        accumulated += chunk

    stage3_result = AgentService._parse_json_response(accumulated)
    eval_approved = stage3_result.get("approved", False)
    eval_quality_score = stage3_result.get("quality_score", 0)
    eval_reasoning = stage3_result.get("reasoning", "")
    modifications = stage3_result.get("modifications")

    # Apply modifications if any (Python-side caption assembly from modified parts)
    if modifications and isinstance(modifications, dict):
        for key in ("hook", "body", "cta", "hashtags"):
            if modifications.get(key):
                caption_data[key] = modifications[key]
        full_caption = build_full_caption(caption_data)

    # ── Store scheduled post ────────────────────────────────────────────────
    evaluation_data = {
        "approved": eval_approved,
        "quality_score": eval_quality_score,
        "reasoning": eval_reasoning,
        "modifications": modifications,
    }

    post = SupabaseService.create_scheduled_post(
        business_account_id=account_id,
        run_id=run_id,
        asset=asset,
        asset_url=asset_url,
        selection_score=selection_score,
        selection_factors=selection_factors,
        caption_data={
            "full_caption": full_caption,
            **caption_data,
        },
        evaluation_data=evaluation_data,
    )
    post_id = post.get("id", "")

    _log_evaluate_asset(run_id, asset, account, stage1_result)
    SupabaseService.log_decision(
        event_type="content_scheduler_post_evaluated",
        action="approved" if eval_approved else "rejected",
        resource_type="scheduled_post",
        resource_id=post_id,
        user_id=account_id,
        details={
            "run_id": run_id,
            "asset_title": asset.get("title", ""),
            "selection_score": selection_score,
            "quality_score": eval_quality_score,
            "approved": eval_approved,
            "reasoning": eval_reasoning[:500],
            "caption_length": len(full_caption),
            "hashtag_count": len(caption_data.get("hashtags", [])),
        },
    )

    # ── Stage 4: Publish via AgentService ─────────────────────────────────
    if eval_approved and CONTENT_SCHEDULER_AUTO_PUBLISH:
        return await _handle_publish(
            run_id=run_id,
            post=post,
            account=account,
            asset=asset,
            caption_data=caption_data,
            full_caption=full_caption,
            caption_variant=caption_variant,
            agent=agent,
        )

    return {"action": "approved" if eval_approved else "rejected"}


# ================================
# UGC Repost Path
# ================================
async def _process_ugc_repost(run_id: str, account: dict) -> dict:
    """Check for granted UGC permissions and repost if available.

    This runs before the regular asset path as an alternate track.
    Returns: {"action": "ugc_reposted"} | {"action": "no_ugc"} | {"action": "error"}
    """
    account_id = account.get("id", "unknown")

    ugc_items = SupabaseService.get_ugc_content_for_repost(account_id)
    if not ugc_items:
        return {"action": "no_ugc"}

    # Take the first granted UGC item
    ugc = ugc_items[0]
    ugc_content_id = ugc.get("id")
    permission_id = ugc.get("permission_id")

    logger.info(f"[{run_id}] @{account.get('username', '')}: processing granted UGC {ugc_content_id}")

    # Verify permission still granted at time of use
    if not _check_ugc_permission(ugc_content_id, account_id):
        logger.info(f"[{run_id}] UGC {ugc_content_id}: permission no longer granted")
        return {"action": "no_ugc"}

    # Build synthetic "asset" dict for the shared post creation path
    synthetic_asset = {
        "id": ugc_content_id,
        "ugc_content_id": ugc_content_id,
        "title": ugc.get("author_username", "UGC Post"),
        "description": ugc.get("message", ""),
        "tags": [],
        "media_type": ugc.get("media_type", "IMAGE"),
        "storage_path": "",
        "author_username": ugc.get("author_username", ""),
    }
    asset_url = ugc.get("media_url", "")

    # Generate caption via tool (Stage 2 equivalent)
    # We pass UGC context directly to bypass the normal asset fetch
    caption_result = _generate_ugc_caption(ugc, account)
    if "error" in caption_result:
        return {"action": "error"}

    caption_data = {
        "hook": caption_result.get("hook", ""),
        "body": caption_result.get("body", ""),
        "cta": caption_result.get("cta", ""),
        "hashtags": caption_result.get("hashtags", []),
    }
    full_caption = build_full_caption(caption_data)

    # Evaluate via AgentService (Stage 3 equivalent)
    agent = AgentService(scope="content")
    stage3_prompt = _build_evaluate_caption_prompt(
        caption_data=caption_data,
        account=account,
        caption_variant="ugc_attributed",
        from_ugc=True,
        author_username=ugc.get("author_username", ""),
    )
    accumulated = ""
    async for chunk in agent.astream_analyze(stage3_prompt):
        accumulated += chunk
    stage3_result = AgentService._parse_json_response(accumulated)
    eval_approved = stage3_result.get("approved", False)
    eval_quality_score = stage3_result.get("quality_score", 0)

    # Store scheduled post
    post = SupabaseService.create_scheduled_post(
        business_account_id=account_id,
        run_id=run_id,
        asset=synthetic_asset,
        asset_url=asset_url,
        selection_score=0,
        selection_factors={},
        caption_data={
            "full_caption": full_caption,
            **caption_data,
        },
        evaluation_data={
            "approved": eval_approved,
            "quality_score": eval_quality_score,
            "reasoning": stage3_result.get("reasoning", ""),
            "modifications": stage3_result.get("modifications"),
        },
        ugc_content_id=ugc_content_id,
    )
    post_id = post.get("id", "")

    SupabaseService.log_decision(
        event_type="content_scheduler_ugc_repost_evaluated",
        action="approved" if eval_approved else "rejected",
        resource_type="scheduled_post",
        resource_id=post_id,
        user_id=account_id,
        details={
            "run_id": run_id,
            "ugc_content_id": ugc_content_id,
            "author_username": ugc.get("author_username", ""),
            "approved": eval_approved,
            "quality_score": eval_quality_score,
        },
    )

    if eval_approved and CONTENT_SCHEDULER_AUTO_PUBLISH:
        # Publish with UGC gate
        if not _check_ugc_permission(ugc_content_id, account_id):
            _handle_ugc_permission_denied(run_id, post, account)
            return {"action": "error"}

        pub_result = await _handle_publish(
            run_id=run_id,
            post=post,
            account=account,
            asset=synthetic_asset,
            caption_data=caption_data,
            full_caption=full_caption,
            caption_variant="ugc_attributed",
            agent=agent,
        )
        if pub_result.get("action") == "published":
            SupabaseService.mark_ugc_reposted(ugc_content_id, account_id)
            return {"action": "ugc_reposted"}
        return pub_result

    return {"action": "approved" if eval_approved else "rejected"}


def _generate_ugc_caption(ugc: dict, account: dict) -> dict:
    """Generate caption for UGC content using the generate_caption tool.

    Sets caption_variant='ugc_attributed' so the LLM knows to include attribution.
    """
    # Call the tool directly with UGC metadata
    result = tool_generate_caption.invoke({
        "asset_id": ugc.get("id", ""),
        "business_account_id": account.get("id", ""),
        "generation_mode": "full",
    })
    return result


# ================================
# Stage 4: Publish Handler (shared by regular + UGC path)
# ================================
async def _handle_publish(
    run_id: str,
    post: dict,
    account: dict,
    asset: dict,
    caption_data: dict,
    full_caption: str,
    caption_variant: str,
    agent: AgentService,
) -> dict:
    """Stage 4: LLM confirms publish via publish_content tool, Python enqueues."""
    post_id = post.get("id", "")
    account_id = account.get("id", "")
    asset_url = asset.get("storage_path") and _get_asset_public_url(asset.get("storage_path", "")) or asset.get("asset_url", "")

    # Build Stage 4 prompt: LLM calls publish_content tool
    stage4_prompt = _build_publish_prompt(
        post_id=post_id,
        account=account,
        asset=asset,
        caption_data=caption_data,
        full_caption=full_caption,
        caption_variant=caption_variant,
    )

    accumulated = ""
    async for chunk in agent.astream_analyze(stage4_prompt):
        accumulated += chunk

    stage4_result = AgentService._parse_json_response(accumulated)
    job_payload = stage4_result.get("job_payload")

    if not job_payload:
        logger.warning(f"[{run_id}] publish_content returned no job_payload")
        return {"action": "failed"}

    # Enqueue via Python
    enqueue_result = _enqueue_publish(job_payload)

    if enqueue_result.get("success"):
        SupabaseService.update_scheduled_post_status(post_id, "publishing")
        # Only update instagram_assets — UGC has no corresponding asset row to update
        if not asset.get("ugc_content_id"):
            SupabaseService.update_asset_after_post(asset.get("id", ""))
        SupabaseService.log_decision(
            event_type="content_scheduler_post_published",
            action="published",
            resource_type="scheduled_post",
            resource_id=post_id,
            user_id=account_id,
            details={
                "run_id": run_id,
                "caption_variant": caption_variant,
                "queued": True,
            },
        )
        return {"action": "published"}
    else:
        SupabaseService.update_scheduled_post_status(
            post_id, "failed",
            extra_fields={"publish_error": enqueue_result.get("error", "enqueue_failed")},
        )
        return {"action": "failed"}


def _handle_ugc_permission_denied(run_id: str, post: dict, account: dict):
    """Log when UGC permission was revoked between evaluation and publish."""
    SupabaseService.log_decision(
        event_type="content_scheduler_ugc_permission_denied",
        action="skipped",
        resource_type="scheduled_post",
        resource_id=post.get("id", ""),
        user_id=account.get("id", ""),
        details={"run_id": run_id, "ugc_content_id": post.get("ugc_content_id", "")},
    )


# ================================
# Prompt Builders (for AgentService stages)
# ================================
def _build_evaluate_asset_prompt(asset: dict, account: dict, selection_score: float, selection_factors: dict) -> str:
    """Build prompt for Stage 1: evaluate_asset tool call."""
    from datetime import datetime, timezone
    from tools.content_tools import _fetch_asset_context, _assemble_asset_context_string

    asset_id = asset.get("id", "")
    account_id = account.get("id", "")

    # Get additional context via tools-like fetch
    ctx = _fetch_asset_context(asset_id, account_id)
    performance = ctx.get("performance", {})
    days_since = None
    if asset.get("last_posted"):
        try:
            last_posted = asset.get("last_posted")
            if isinstance(last_posted, str):
                last_posted = datetime.fromisoformat(last_posted.replace("Z", "+00:00"))
            days_since = (datetime.now(timezone.utc) - last_posted).days
        except Exception:
            days_since = None

    from_ugc = bool(asset.get("ugc_content_id"))
    ugc_permission_status = None
    if from_ugc:
        from tools.content_tools import _get_ugc_permission_status
        ugc_permission_status = _get_ugc_permission_status(asset.get("ugc_content_id"), account_id)

    prompt = PromptService.get("evaluate_asset").format(
        account_username=account.get("username", "unknown"),
        account_type=account.get("account_type", "business"),
        followers_count=account.get("followers_count", 0),
        asset_title=asset.get("title", "Untitled"),
        asset_description=asset.get("description", "No description"),
        asset_tags=", ".join(asset.get("tags", []) or []),
        media_type=asset.get("media_type", "IMAGE"),
        selection_score=selection_score,
        selection_factors_json=json.dumps(selection_factors),
        from_ugc=str(from_ugc).lower(),
        ugc_permission_status=str(ugc_permission_status or "not_applicable"),
        avg_engagement=performance.get("avg_engagement_rate", 0),
        days_since_posted=str(days_since if days_since is not None else "never"),
    )
    return prompt


def _build_evaluate_caption_prompt(
    caption_data: dict,
    account: dict,
    caption_variant: str,
    from_ugc: bool = False,
    author_username: str = "",
) -> str:
    """Build prompt for Stage 3: evaluate_caption tool call.

    The full caption text is assembled and passed as context so the LLM
    can evaluate without needing a separate tool call to receive it.
    """
    full_caption = build_full_caption(caption_data)

    # Fetch real performance data for context
    performance = SupabaseService.get_recent_post_performance(account.get("id", ""))

    if from_ugc:
        ugc_verification = (
            "- This is UGC attributed content. Verify:\n"
            f"  1. @{author_username} attribution is present in the hook\n"
            "  2. Original creator is credited\n"
        )
    else:
        ugc_verification = "- Standard brand content."

    prompt = PromptService.get("evaluate_caption").format(
        account_username=account.get("username", "unknown"),
        account_type=account.get("account_type", "business"),
        followers_count=account.get("followers_count", 0),
        avg_likes=performance.get("avg_likes", 0),
        avg_comments=performance.get("avg_comments", 0),
        caption_text=full_caption,
        caption_variant=caption_variant,
        from_ugc=str(from_ugc).lower(),
        ugc_verification=ugc_verification,
    )
    return prompt


def _build_publish_prompt(
    post_id: str,
    account: dict,
    asset: dict,
    caption_data: dict,
    full_caption: str,
    caption_variant: str,
) -> str:
    """Build prompt for Stage 4: publish_content tool call."""
    asset_url = asset.get("asset_url") or (
        _get_asset_public_url(asset.get("storage_path", "")) if asset.get("storage_path") else ""
    )

    return (
        f"You are preparing to publish a scheduled Instagram post.\n\n"
        f"Scheduled Post ID: {post_id}\n"
        f"Business Account ID: {account.get('id', '')}\n"
        f"Image URL: {asset_url}\n"
        f"Caption:\n{full_caption}\n\n"
        f"Media Type: {asset.get('media_type', 'IMAGE')}\n"
        f"Caption Variant: {caption_variant}\n\n"
        f"Call publish_content to validate and enqueue this post for publishing.\n"
        f"Return {{validated: true, job_payload: {{...}}}} if all fields are valid."
    )


def _log_evaluate_asset(run_id: str, asset: dict, account: dict, result: dict):
    """Log evaluate_asset decision to audit_log."""
    SupabaseService.log_decision(
        event_type="content_scheduler_asset_evaluated",
        action=result.get("tier", "skip"),
        resource_type="instagram_assets",
        resource_id=asset.get("id", ""),
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "tier": result.get("tier"),
            "quality_score": result.get("quality_score"),
            "recommendations": result.get("recommendations", []),
            "reasoning": result.get("reasoning", "")[:500],
        },
    )


# ================================
# Helpers
# ================================
def _log_account_error(run_id: str, account: dict, error: Exception):
    """Log a processing error for a single account."""
    SupabaseService.log_decision(
        event_type="content_scheduler_account_error",
        action="error",
        resource_type="content_scheduler",
        resource_id=run_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "account_username": account.get("username", ""),
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def _log_batch_summary(run_id: str, stats: dict, duration: float):
    """Log cycle completion with aggregate stats to audit_log."""
    SupabaseService.log_decision(
        event_type="content_scheduler_cycle_complete",
        action="batch_processed",
        resource_type="content_scheduler",
        resource_id=run_id,
        user_id="system",
        details={
            "run_id": run_id,
            "duration_seconds": round(duration, 2),
            **stats,
        },
    )
