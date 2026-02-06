"""
Engagement Monitor
===================
Scheduled batch pipeline that scans unprocessed Instagram comments,
analyzes them via the LLM, and auto-replies or escalates.

Replaces the N8N engagement-monitor.json workflow entirely.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account, fetch unprocessed comments from Supabase
  3. Filter through Redis dedup (fast path)
  4. For each comment (parallel, semaphore-limited):
     a. Fetch post context
     b. Analyze via _analyze_message (LLM)
     c. Route: escalate / auto-reply / skip
     d. Mark processed in DB + Redis
     e. Log decision to audit_log
  5. Log batch summary + update Prometheus metrics

Error isolation: Each comment is wrapped in try/except so a single
failure never crashes the batch.
"""

import asyncio
import time
import uuid as uuid_mod

from config import (
    logger,
    ENGAGEMENT_MONITOR_MAX_COMMENTS_PER_RUN,
    ENGAGEMENT_MONITOR_MAX_CONCURRENT_ANALYSES,
    ENGAGEMENT_MONITOR_HOURS_BACK,
    ENGAGEMENT_MONITOR_AUTO_REPLY_ENABLED,
    ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD,
)
from services.supabase_service import SupabaseService
from scheduler.dedup_service import DedupService
from tools.automation_tools import _analyze_message, _reply_to_comment


# ================================
# Entry Point (called by scheduler)
# ================================
async def engagement_monitor_run():
    """Top-level entry point called by APScheduler every N minutes.

    Iterates all active business accounts, processes unprocessed comments,
    logs batch summary, and updates Prometheus metrics.
    """
    # Lazy import to avoid circular dependency at module load time
    from routes.metrics import (
        ENGAGEMENT_MONITOR_RUNS,
        ENGAGEMENT_MONITOR_COMMENTS,
        ENGAGEMENT_MONITOR_DURATION,
    )

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] Engagement monitor cycle starting")

    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping cycle")
            ENGAGEMENT_MONITOR_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s)")

        for account in accounts:
            account_stats = await _process_account(run_id, account)
            for key in stats:
                stats[key] += account_stats.get(key, 0)

        duration = time.time() - start
        status = "success" if stats["errors"] == 0 else "partial"

        _log_batch_summary(run_id, stats, duration)
        ENGAGEMENT_MONITOR_RUNS.labels(status=status).inc()
        ENGAGEMENT_MONITOR_DURATION.observe(duration)

        for action in ("replied", "escalated", "skipped", "error"):
            count = stats.get(action if action != "error" else "errors", 0)
            if count > 0:
                ENGAGEMENT_MONITOR_COMMENTS.labels(action=action).inc(count)

        logger.info(
            f"[{run_id}] Engagement monitor cycle complete "
            f"({duration:.1f}s): {stats}"
        )

    except Exception as e:
        duration = time.time() - start
        logger.error(f"[{run_id}] Engagement monitor cycle failed ({duration:.1f}s): {e}")
        ENGAGEMENT_MONITOR_RUNS.labels(status="error").inc()
        ENGAGEMENT_MONITOR_DURATION.observe(duration)

        # Log failure to audit
        SupabaseService.log_decision(
            event_type="engagement_monitor_cycle_failed",
            action="error",
            resource_type="engagement_monitor",
            resource_id=run_id,
            user_id="system",
            details={"run_id": run_id, "error": str(e), "duration_seconds": round(duration, 2)},
        )


# ================================
# Per-Account Processing
# ================================
async def _process_account(run_id: str, account: dict) -> dict:
    """Fetch and process unprocessed comments for a single business account."""
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    comments = SupabaseService.get_unprocessed_comments(
        business_account_id=account_id,
        limit=ENGAGEMENT_MONITOR_MAX_COMMENTS_PER_RUN,
        hours_back=ENGAGEMENT_MONITOR_HOURS_BACK,
    )

    if not comments:
        logger.debug(f"[{run_id}] @{account_username}: no unprocessed comments")
        return stats

    # Filter through Redis dedup (fast path)
    unprocessed = [
        c for c in comments
        if not DedupService.is_processed(c.get("instagram_comment_id", ""))
    ]

    if not unprocessed:
        logger.debug(f"[{run_id}] @{account_username}: all {len(comments)} comments already in dedup cache")
        return stats

    logger.info(f"[{run_id}] @{account_username}: processing {len(unprocessed)} comment(s)")

    # Process with semaphore (limit concurrent LLM calls)
    semaphore = asyncio.Semaphore(ENGAGEMENT_MONITOR_MAX_CONCURRENT_ANALYSES)
    tasks = [
        _process_comment_safe(run_id, comment, account, semaphore)
        for comment in unprocessed
    ]
    results = await asyncio.gather(*tasks)

    # Aggregate stats
    for result in results:
        action = result.get("action", "error")
        stats["processed"] += 1
        if action == "replied":
            stats["replied"] += 1
        elif action == "escalated":
            stats["escalated"] += 1
        elif action == "skipped":
            stats["skipped"] += 1
        else:
            stats["errors"] += 1

    logger.info(f"[{run_id}] @{account_username}: {stats}")
    return stats


# ================================
# Per-Comment Processing (Error-Isolated)
# ================================
async def _process_comment_safe(
    run_id: str, comment: dict, account: dict, semaphore: asyncio.Semaphore
) -> dict:
    """Wraps _process_comment in try/except. NEVER fails the batch."""
    async with semaphore:
        try:
            return await _process_comment(run_id, comment, account)
        except Exception as e:
            comment_id = comment.get("id", "unknown")
            logger.error(f"[{run_id}] Comment {comment_id} failed: {e}")
            _log_comment_error(run_id, comment, account, e)
            return {"action": "error", "comment_id": comment_id, "error": str(e)}


async def _process_comment(run_id: str, comment: dict, account: dict) -> dict:
    """Single comment pipeline: context -> analyze -> route -> execute -> mark -> log."""
    comment_id = comment.get("id", "")
    instagram_comment_id = comment.get("instagram_comment_id", "")
    comment_text = comment.get("text", "")
    author = comment.get("author_username", "unknown")
    media_id = comment.get("media_id", "")

    # 1. Fetch post context
    post_ctx = SupabaseService.get_post_context_by_uuid(media_id)

    # 2. Analyze via existing _analyze_message (runs LLM + hard escalation rules)
    analysis = await asyncio.to_thread(
        _analyze_message,
        message_text=comment_text,
        message_type="comment",
        sender_username=author,
        account_context=account,
        post_context=post_ctx,
        dm_history=None,
        customer_lifetime_value=0.0,
    )

    # 3. Route based on analysis result
    if analysis.get("needs_human"):
        return _handle_escalation(run_id, comment, account, analysis)

    suggested_reply = analysis.get("suggested_reply", "")
    confidence = analysis.get("confidence", 0)

    if (
        suggested_reply
        and confidence >= ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD
        and ENGAGEMENT_MONITOR_AUTO_REPLY_ENABLED
    ):
        return _handle_auto_reply(run_id, comment, account, analysis, post_ctx)

    return _handle_skip(run_id, comment, account, analysis)


# ================================
# Action Handlers
# ================================
def _handle_escalation(run_id: str, comment: dict, account: dict, analysis: dict) -> dict:
    """Log escalation, mark processed without reply."""
    comment_id = comment.get("id", "")
    instagram_comment_id = comment.get("instagram_comment_id", "")

    SupabaseService.mark_comment_processed(comment_id, was_replied=False)
    DedupService.mark_processed(instagram_comment_id)

    SupabaseService.log_decision(
        event_type="engagement_monitor_escalation",
        action="escalated",
        resource_type="comment",
        resource_id=comment_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "comment_text": comment.get("text", "")[:200],
            "author": comment.get("author_username", ""),
            "category": analysis.get("category"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority"),
            "confidence": analysis.get("confidence"),
            "escalation_reason": analysis.get("escalation_reason", "needs_human flagged"),
            "media_id": comment.get("media_id", ""),
        },
    )

    logger.info(
        f"[{run_id}] Escalated comment {comment_id} "
        f"(reason: {analysis.get('escalation_reason', 'needs_human')})"
    )
    return {"action": "escalated", "comment_id": comment_id}


def _handle_auto_reply(
    run_id: str, comment: dict, account: dict, analysis: dict, post_ctx: dict
) -> dict:
    """Execute reply, log outcome, mark processed."""
    comment_id = comment.get("id", "")
    instagram_comment_id = comment.get("instagram_comment_id", "")
    suggested_reply = analysis.get("suggested_reply", "")

    # Execute reply via existing tool (backend proxy with retry)
    result = _reply_to_comment(
        comment_id=instagram_comment_id,
        reply_text=suggested_reply,
        business_account_id=account.get("id", ""),
        post_id=post_ctx.get("instagram_media_id", ""),
    )

    was_replied = result.get("success", False)

    # Mark processed in DB
    SupabaseService.mark_comment_processed(
        comment_id,
        response_text=suggested_reply if was_replied else None,
        was_replied=was_replied,
    )
    DedupService.mark_processed(instagram_comment_id)

    # Feedback loop: log execution outcome for pattern learning
    _log_execution_outcome(run_id, comment, result, account)

    # Audit log
    action = "auto_replied" if was_replied else "reply_failed"
    SupabaseService.log_decision(
        event_type="engagement_monitor_comment_processed",
        action=action,
        resource_type="comment",
        resource_id=comment_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "comment_text": comment.get("text", "")[:200],
            "author": comment.get("author_username", ""),
            "category": analysis.get("category"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority"),
            "confidence": analysis.get("confidence"),
            "suggested_reply": suggested_reply,
            "reply_sent": was_replied,
            "execution_id": result.get("execution_id"),
            "error": result.get("error") if not was_replied else None,
        },
    )

    if was_replied:
        logger.info(f"[{run_id}] Auto-replied to comment {comment_id}")
    else:
        logger.warning(f"[{run_id}] Reply failed for comment {comment_id}: {result.get('error')}")

    return {"action": "replied" if was_replied else "reply_failed", "comment_id": comment_id}


def _handle_skip(run_id: str, comment: dict, account: dict, analysis: dict) -> dict:
    """Mark processed with no reply (praise, general, low confidence)."""
    comment_id = comment.get("id", "")
    instagram_comment_id = comment.get("instagram_comment_id", "")

    SupabaseService.mark_comment_processed(comment_id, was_replied=False)
    DedupService.mark_processed(instagram_comment_id)

    SupabaseService.log_decision(
        event_type="engagement_monitor_comment_processed",
        action="skipped",
        resource_type="comment",
        resource_id=comment_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "comment_text": comment.get("text", "")[:200],
            "author": comment.get("author_username", ""),
            "category": analysis.get("category"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority"),
            "confidence": analysis.get("confidence"),
            "skip_reason": _get_skip_reason(analysis),
        },
    )

    logger.debug(f"[{run_id}] Skipped comment {comment_id} ({_get_skip_reason(analysis)})")
    return {"action": "skipped", "comment_id": comment_id}


# ================================
# Helpers
# ================================
def _get_skip_reason(analysis: dict) -> str:
    """Determine why a comment was skipped (for audit logging)."""
    if not analysis.get("suggested_reply"):
        return "no_reply_suggested"
    confidence = analysis.get("confidence", 0)
    if confidence < ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD:
        return f"low_confidence ({confidence:.2f} < {ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD})"
    if not ENGAGEMENT_MONITOR_AUTO_REPLY_ENABLED:
        return "auto_reply_disabled"
    return "general_skip"


def _log_execution_outcome(run_id: str, comment: dict, result: dict, account: dict):
    """Log reply success/failure for agent learning (feedback loop).

    Uses the same event pattern as the /log-outcome endpoint
    so outcomes are queryable in the same way.
    """
    SupabaseService.log_decision(
        event_type="comment_execution_outcome",
        action="success" if result.get("success") else "failed",
        resource_type="comment",
        resource_id=comment.get("id", ""),
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "execution_id": result.get("execution_id"),
            "success": result.get("success"),
            "error": result.get("error"),
            "instagram_response": result.get("instagram_response"),
            "source": "engagement_monitor",
        },
    )


def _log_comment_error(run_id: str, comment: dict, account: dict, error: Exception):
    """Log a processing error for a single comment (error isolation)."""
    comment_id = comment.get("id", "")

    # Still mark as processed to prevent infinite retry loops
    SupabaseService.mark_comment_processed(comment_id, was_replied=False)
    DedupService.mark_processed(comment.get("instagram_comment_id", ""))

    SupabaseService.log_decision(
        event_type="engagement_monitor_comment_error",
        action="error",
        resource_type="comment",
        resource_id=comment_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "comment_text": comment.get("text", "")[:200],
            "author": comment.get("author_username", ""),
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def _log_batch_summary(run_id: str, stats: dict, duration: float):
    """Log cycle completion with aggregate stats to audit_log."""
    SupabaseService.log_decision(
        event_type="engagement_monitor_cycle_complete",
        action="batch_processed",
        resource_type="engagement_monitor",
        resource_id=run_id,
        user_id="system",
        details={
            "run_id": run_id,
            "duration_seconds": round(duration, 2),
            **stats,
        },
    )
