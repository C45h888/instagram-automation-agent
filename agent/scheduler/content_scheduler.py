"""
Content Scheduler
==================
Scheduled batch pipeline that selects media assets, generates captions
via single LLM call, evaluates quality, and optionally publishes.

Replaces the N8N content-scheduler workflow entirely.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account:
     a. Check daily post cap
     b. Select best asset (4-factor scoring + weighted random)
     c. Fetch performance benchmarks
     d. Generate + evaluate caption (single LLM call)
     e. Apply hard rules (hashtag count, length, quality)
     f. Store scheduled post (approved or rejected)
     g. If auto-publish enabled + approved: publish via backend proxy
     h. Log decision to audit_log
  3. Log batch summary + update Prometheus metrics

Error isolation: Each account is wrapped in try/except so a single
failure never crashes the batch.
"""

import asyncio
import time
import uuid as uuid_mod

from config import (
    logger,
    CONTENT_SCHEDULER_MAX_CONCURRENT_GENERATIONS,
    CONTENT_SCHEDULER_MAX_POSTS_PER_DAY,
    CONTENT_SCHEDULER_AUTO_PUBLISH,
)
from services.supabase_service import SupabaseService
from tools.content_tools import (
    select_asset,
    generate_and_evaluate,
    build_full_caption,
    publish_post,
    _get_asset_public_url,
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
    """Generate one post for a single business account."""
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    stats = {"processed": 0, "approved": 0, "rejected": 0, "published": 0, "failed": 0, "no_assets": 0, "capped": 0, "errors": 0}

    # Check daily cap
    posts_today = SupabaseService.get_posts_today_count(account_id)
    if posts_today >= CONTENT_SCHEDULER_MAX_POSTS_PER_DAY:
        logger.info(
            f"[{run_id}] @{account_username}: daily cap reached "
            f"({posts_today}/{CONTENT_SCHEDULER_MAX_POSTS_PER_DAY}) — skipping"
        )
        stats["capped"] = 1
        return stats

    result = await _generate_post(run_id, account)
    stats["processed"] = 1

    action = result.get("action", "error")
    if action in stats:
        stats[action] += 1
    else:
        stats["errors"] += 1

    logger.info(f"[{run_id}] @{account_username}: {action}")
    return stats


# ================================
# Single Post Pipeline
# ================================
async def _generate_post(run_id: str, account: dict) -> dict:
    """Full pipeline for generating one post.

    Steps:
      1. Select best asset
      2. Fetch performance benchmarks
      3. Generate + evaluate caption (single LLM call)
      4. Build full caption string
      5. Store scheduled post
      6. If auto-publish + approved: publish
      7. Log decision
    """
    account_id = account.get("id", "unknown")

    # Step 1: Select asset
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

    # Step 2: Performance benchmarks
    performance = SupabaseService.get_recent_post_performance(account_id)

    # Step 3: Generate + evaluate (single LLM call)
    evaluation = await generate_and_evaluate(asset, account, performance)

    # Step 4: Build full caption
    full_caption = build_full_caption(evaluation)

    # Step 5: Build public URL for asset
    asset_url = _get_asset_public_url(asset.get("storage_path", ""))

    # Step 6: Store scheduled post
    caption_data = {
        "full_caption": full_caption,
        "hook": evaluation.get("hook", ""),
        "body": evaluation.get("body", ""),
        "cta": evaluation.get("cta", ""),
        "hashtags": evaluation.get("hashtags", []),
    }
    evaluation_data = {
        "approved": evaluation.get("approved", False),
        "quality_score": evaluation.get("quality_score", 0),
        "reasoning": evaluation.get("reasoning", ""),
        "modifications": evaluation.get("modifications"),
    }

    post = SupabaseService.create_scheduled_post(
        business_account_id=account_id,
        run_id=run_id,
        asset=asset,
        asset_url=asset_url,
        selection_score=asset.get("_score", 0),
        selection_factors=asset.get("_factors", {}),
        caption_data=caption_data,
        evaluation_data=evaluation_data,
    )

    post_id = post.get("id", "")
    is_approved = evaluation.get("approved", False)

    # Step 7: Log evaluation decision
    SupabaseService.log_decision(
        event_type="content_scheduler_post_evaluated",
        action="approved" if is_approved else "rejected",
        resource_type="scheduled_post",
        resource_id=post_id,
        user_id=account_id,
        details={
            "run_id": run_id,
            "asset_title": asset.get("title", ""),
            "asset_path": asset.get("storage_path", ""),
            "selection_score": asset.get("_score", 0),
            "quality_score": evaluation.get("quality_score", 0),
            "approved": is_approved,
            "reasoning": evaluation.get("reasoning", "")[:500],
            "caption_length": len(full_caption),
            "hashtag_count": len(evaluation.get("hashtags", [])),
        },
    )

    # Step 8: Publish if approved + auto-publish enabled
    if is_approved and CONTENT_SCHEDULER_AUTO_PUBLISH:
        pub_result = await publish_post(
            scheduled_post_id=post_id,
            business_account_id=account_id,
            image_url=asset_url,
            caption=full_caption,
            media_type=asset.get("media_type", "IMAGE"),
        )

        if pub_result.get("success"):
            # Update asset metadata
            SupabaseService.update_asset_after_post(asset.get("id", ""))

            SupabaseService.log_decision(
                event_type="content_scheduler_post_published",
                action="published",
                resource_type="scheduled_post",
                resource_id=post_id,
                user_id=account_id,
                details={
                    "run_id": run_id,
                    "instagram_media_id": pub_result.get("instagram_media_id"),
                    "asset_title": asset.get("title", ""),
                },
            )
            return {"action": "published"}
        else:
            SupabaseService.log_decision(
                event_type="content_scheduler_post_publish_failed",
                action="failed",
                resource_type="scheduled_post",
                resource_id=post_id,
                user_id=account_id,
                details={
                    "run_id": run_id,
                    "error": pub_result.get("error", "unknown"),
                    "asset_title": asset.get("title", ""),
                },
            )
            return {"action": "failed"}

    return {"action": "approved" if is_approved else "rejected"}


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
