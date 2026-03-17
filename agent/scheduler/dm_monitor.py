"""
DM Monitor
===========
Scheduled batch pipeline that scans unprocessed inbound Instagram DMs,
analyzes them via the LLM, and auto-replies or escalates.

Fallback layer for when Instagram push webhooks (POST /webhook/dm) are not
configured or temporarily unavailable. Polls Supabase every N minutes for
inbound messages with is_from_business=false and processed_by_automation=false.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account, fetch unprocessed inbound DMs from Supabase
     (is_from_business=false, processed_by_automation=false, sent_at within 24h)
  3. Filter through Redis dedup (fast path)
  4. For each message (parallel, semaphore-limited):
     a. Fetch DM history for context
     b. Analyze via _analyze_message (LLM)
     c. Route: escalate / auto-reply / skip
     d. Mark processed in DB + Redis
     e. Log decision to audit_log
  5. Log batch summary + update Prometheus metrics

Error isolation: Each message is wrapped in try/except so a single
failure never crashes the batch.

Note: The webhook handler (routes/webhook_dm.py) is the primary path.
This scheduler is the secondary fallback only.
"""

import asyncio
import time
import uuid as uuid_mod

from config import (
    logger,
    DM_MONITOR_MAX_MESSAGES_PER_RUN,
    DM_MONITOR_MAX_CONCURRENT_ANALYSES,
    DM_MONITOR_HOURS_BACK,
    DM_MONITOR_AUTO_REPLY_ENABLED,
    DM_MONITOR_CONFIDENCE_THRESHOLD,
)
from services.supabase_service import SupabaseService, _redis, _redis_available
from tools.automation_tools import _analyze_message, _reply_to_dm


# ================================
# Redis Dedup (DM-scoped key prefix, separate from comment dedup)
# ================================
_DM_DEDUP_PREFIX = "dm_monitor:processed_ids"
_DM_DEDUP_TTL = 86400  # 24 hours


def _is_dm_processed(message_id: str, account_id: str) -> bool:
    """Redis fast-path check. Falls back to False (DB filter is authoritative)."""
    if not _redis_available or not message_id or not account_id:
        return False
    try:
        return bool(_redis.sismember(f"{_DM_DEDUP_PREFIX}:{account_id}", message_id))
    except Exception:
        return False


def _mark_dm_dedup(message_id: str, account_id: str):
    """Add message ID to per-account Redis dedup set with TTL."""
    if not _redis_available or not message_id or not account_id:
        return
    try:
        key = f"{_DM_DEDUP_PREFIX}:{account_id}"
        _redis.sadd(key, message_id)
        _redis.expire(key, _DM_DEDUP_TTL)
    except Exception as e:
        logger.debug(f"Redis DM dedup mark failed (non-critical): {e}")


# ================================
# Entry Point (called by scheduler)
# ================================
async def dm_monitor_run():
    """Top-level entry point called by APScheduler every N minutes."""
    from routes.metrics import DM_MONITOR_RUNS, DM_MONITOR_MESSAGES, DM_MONITOR_DURATION

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] DM monitor cycle starting")

    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping cycle")
            DM_MONITOR_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s)")

        for account in accounts:
            account_stats = await _process_account(run_id, account)
            for key in stats:
                stats[key] += account_stats.get(key, 0)

        duration = time.time() - start
        status = "success" if stats["errors"] == 0 else "partial"

        _log_batch_summary(run_id, stats, duration)
        DM_MONITOR_RUNS.labels(status=status).inc()
        DM_MONITOR_DURATION.observe(duration)

        for action in ("replied", "escalated", "skipped", "error"):
            count = stats.get(action if action != "error" else "errors", 0)
            if count > 0:
                DM_MONITOR_MESSAGES.labels(action=action).inc(count)

        logger.info(f"[{run_id}] DM monitor cycle complete ({duration:.1f}s): {stats}")

    except Exception as e:
        duration = time.time() - start
        logger.error(f"[{run_id}] DM monitor cycle failed ({duration:.1f}s): {e}")
        DM_MONITOR_RUNS.labels(status="error").inc()
        DM_MONITOR_DURATION.observe(duration)

        SupabaseService.log_decision(
            event_type="dm_monitor_cycle_failed",
            action="error",
            resource_type="dm_monitor",
            resource_id=run_id,
            user_id="system",
            details={"run_id": run_id, "error": str(e), "duration_seconds": round(duration, 2)},
        )


# ================================
# Per-Account Processing
# ================================
async def _process_account(run_id: str, account: dict) -> dict:
    """Fetch and process unprocessed inbound DMs for a single business account."""
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    messages = SupabaseService.get_unprocessed_dms(
        business_account_id=account_id,
        limit=DM_MONITOR_MAX_MESSAGES_PER_RUN,
        hours_back=DM_MONITOR_HOURS_BACK,
    )

    if not messages:
        logger.debug(f"[{run_id}] @{account_username}: no unprocessed inbound DMs")
        return stats

    # Redis dedup fast-path
    unprocessed = [
        m for m in messages
        if not _is_dm_processed(m.get("instagram_message_id", ""), account_id)
    ]

    if not unprocessed:
        logger.debug(
            f"[{run_id}] @{account_username}: all {len(messages)} DMs already in dedup cache"
        )
        return stats

    logger.info(f"[{run_id}] @{account_username}: processing {len(unprocessed)} inbound DM(s)")

    semaphore = asyncio.Semaphore(DM_MONITOR_MAX_CONCURRENT_ANALYSES)
    tasks = [
        _process_message_safe(run_id, msg, account, semaphore)
        for msg in unprocessed
    ]
    results = await asyncio.gather(*tasks)

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
# Per-Message Processing (Error-Isolated)
# ================================
async def _process_message_safe(
    run_id: str, msg: dict, account: dict, semaphore: asyncio.Semaphore
) -> dict:
    """Wraps _process_message in try/except. NEVER fails the batch."""
    async with semaphore:
        try:
            return await _process_message(run_id, msg, account)
        except Exception as e:
            msg_id = msg.get("id", "unknown")
            logger.error(f"[{run_id}] DM {msg_id} failed: {e}")
            _log_message_error(run_id, msg, account, e)
            return {"action": "error", "message_id": msg_id, "error": str(e)}


async def _process_message(run_id: str, msg: dict, account: dict) -> dict:
    """Single DM pipeline: context → analyze → route → execute → mark → log."""
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")
    message_text = msg.get("message_text", "")
    customer_ig_id = msg.get("customer_instagram_id", "")
    sender_username = msg.get("customer_username", "") or f"user_{customer_ig_id[-6:]}" if customer_ig_id else "unknown"

    # Fetch prior conversation history for LLM context
    dm_history = SupabaseService.get_dm_history(customer_ig_id, account.get("id", ""))

    analysis = await asyncio.to_thread(
        _analyze_message,
        message_text=message_text,
        message_type="dm",
        sender_username=sender_username,
        account_context=account,
        post_context=None,
        dm_history=dm_history,
        customer_lifetime_value=0.0,
    )

    if analysis.get("needs_human"):
        return _handle_escalation(run_id, msg, account, analysis)

    suggested_reply = analysis.get("suggested_reply", "")
    confidence = analysis.get("confidence", 0)

    if (
        suggested_reply
        and confidence >= DM_MONITOR_CONFIDENCE_THRESHOLD
        and DM_MONITOR_AUTO_REPLY_ENABLED
    ):
        return _handle_auto_reply(run_id, msg, account, analysis, customer_ig_id)

    return _handle_skip(run_id, msg, account, analysis)


# ================================
# Action Handlers
# ================================
def _handle_escalation(run_id: str, msg: dict, account: dict, analysis: dict) -> dict:
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")

    SupabaseService.mark_dm_processed(msg_id, was_replied=False)
    _mark_dm_dedup(instagram_message_id, account.get("id", ""))

    SupabaseService.log_decision(
        event_type="dm_monitor_escalation",
        action="escalated",
        resource_type="dm",
        resource_id=msg_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "message_text": msg.get("message_text", "")[:200],
            "sender": msg.get("customer_username", ""),
            "category": analysis.get("category"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority"),
            "confidence": analysis.get("confidence"),
            "escalation_reason": analysis.get("escalation_reason", "needs_human flagged"),
        },
    )

    logger.info(
        f"[{run_id}] Escalated DM {msg_id} "
        f"(reason: {analysis.get('escalation_reason', 'needs_human')})"
    )
    return {"action": "escalated", "message_id": msg_id}


def _handle_auto_reply(
    run_id: str, msg: dict, account: dict, analysis: dict, customer_ig_id: str
) -> dict:
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")
    suggested_reply = analysis.get("suggested_reply", "")

    # conversation_id for the backend proxy = customer's IG PSID (same as webhook pattern)
    result = _reply_to_dm(
        conversation_id=customer_ig_id,
        recipient_id=customer_ig_id,
        message_text=suggested_reply,
        business_account_id=account.get("id", ""),
    )

    was_replied = result.get("success", False)

    SupabaseService.mark_dm_processed(
        msg_id,
        response_text=suggested_reply if was_replied else None,
        was_replied=was_replied,
    )
    _mark_dm_dedup(instagram_message_id, account.get("id", ""))

    action = "auto_replied" if was_replied else "reply_failed"
    SupabaseService.log_decision(
        event_type="dm_monitor_message_processed",
        action=action,
        resource_type="dm",
        resource_id=msg_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "message_text": msg.get("message_text", "")[:200],
            "sender": msg.get("customer_username", ""),
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
        logger.info(f"[{run_id}] Auto-replied to DM {msg_id}")
    else:
        logger.warning(f"[{run_id}] Reply failed for DM {msg_id}: {result.get('error')}")

    return {"action": "replied" if was_replied else "reply_failed", "message_id": msg_id}


def _handle_skip(run_id: str, msg: dict, account: dict, analysis: dict) -> dict:
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")

    SupabaseService.mark_dm_processed(msg_id, was_replied=False)
    _mark_dm_dedup(instagram_message_id, account.get("id", ""))

    SupabaseService.log_decision(
        event_type="dm_monitor_message_processed",
        action="skipped",
        resource_type="dm",
        resource_id=msg_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "message_text": msg.get("message_text", "")[:200],
            "sender": msg.get("customer_username", ""),
            "category": analysis.get("category"),
            "sentiment": analysis.get("sentiment"),
            "priority": analysis.get("priority"),
            "confidence": analysis.get("confidence"),
            "skip_reason": _get_skip_reason(analysis),
        },
    )

    logger.debug(f"[{run_id}] Skipped DM {msg_id} ({_get_skip_reason(analysis)})")
    return {"action": "skipped", "message_id": msg_id}


# ================================
# Helpers
# ================================
def _get_skip_reason(analysis: dict) -> str:
    if not analysis.get("suggested_reply"):
        return "no_reply_suggested"
    confidence = analysis.get("confidence", 0)
    if confidence < DM_MONITOR_CONFIDENCE_THRESHOLD:
        return f"low_confidence ({confidence:.2f} < {DM_MONITOR_CONFIDENCE_THRESHOLD})"
    if not DM_MONITOR_AUTO_REPLY_ENABLED:
        return "auto_reply_disabled"
    return "general_skip"


def _log_message_error(run_id: str, msg: dict, account: dict, error: Exception):
    """Mark processed to prevent infinite retry, then log error."""
    msg_id = msg.get("id", "")
    SupabaseService.mark_dm_processed(msg_id, was_replied=False)
    _mark_dm_dedup(msg.get("instagram_message_id", ""), account.get("id", ""))

    SupabaseService.log_decision(
        event_type="dm_monitor_message_error",
        action="error",
        resource_type="dm",
        resource_id=msg_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "message_text": msg.get("message_text", "")[:200],
            "sender": msg.get("customer_username", ""),
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def _log_batch_summary(run_id: str, stats: dict, duration: float):
    SupabaseService.log_decision(
        event_type="dm_monitor_cycle_complete",
        action="batch_processed",
        resource_type="dm_monitor",
        resource_id=run_id,
        user_id="system",
        details={
            "run_id": run_id,
            "duration_seconds": round(duration, 2),
            **stats,
        },
    )
