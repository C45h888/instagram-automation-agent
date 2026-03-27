"""
DM Monitor
===========
Scheduled batch pipeline that scans unprocessed inbound Instagram DMs,
analyzes them via AgentService.bind_tools() (LLM fetches context), and
auto-replies or escalates.

Fallback layer for when Instagram push webhooks (POST /webhook/dm) are not
configured or temporarily unavailable. Polls Supabase every N minutes for
inbound messages with is_from_business=false and processed_by_automation=false.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account, fetch unprocessed inbound DMs from Supabase
     (is_from_business=false, processed_by_automation=false, sent_at within 24h)
  3. Filter through Redis dedup (fast path)
  4. For each message (parallel, semaphore-limited):
     a. Build prompt using analyze_message_agent template
     b. Stream analysis via AgentService.astream_analyze() with bind_tools
        - LLM fetches DM history and conversation context via supabase tools
        - LLM applies escalation rules in prompt
     c. Accumulate response, parse JSON
     d. Apply Python _apply_hard_escalation_rules() safety override
     e. Route: escalate / auto-reply / skip
     f. Mark processed in DB + Redis
     g. Log decision to audit_log
  5. Log batch summary + update Prometheus metrics

One AgentService(scope="engagement") instance per run — shared across
all accounts and all messages.

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
from services.agent_service import AgentService
from services.prompt_service import PromptService
from tools.automation_tools import _apply_hard_escalation_rules, _enqueue_dm, _enqueue_from_job_payload


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
    """Top-level entry point called by APScheduler every N minutes.

    One AgentService(scope="engagement") instance is created per run and
    shared across all accounts and all messages.
    """
    from routes.metrics import DM_MONITOR_RUNS, DM_MONITOR_MESSAGES, DM_MONITOR_DURATION

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] DM monitor cycle starting")

    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    try:
        # One AgentService instance per run — shared across all accounts
        agent = AgentService(scope="engagement")

        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping cycle")
            DM_MONITOR_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s)")

        for account in accounts:
            account_stats = await _process_account(run_id, account, agent)
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
async def _process_account(run_id: str, account: dict, agent: AgentService) -> dict:
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
        _process_message_safe(run_id, msg, account, agent, semaphore)
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
    run_id: str, msg: dict, account: dict, agent: AgentService, semaphore: asyncio.Semaphore
) -> dict:
    """Wraps _process_message in try/except. NEVER fails the batch."""
    async with semaphore:
        try:
            return await _process_message(run_id, msg, account, agent)
        except Exception as e:
            msg_id = msg.get("id", "unknown")
            logger.error(f"[{run_id}] DM {msg_id} failed: {e}")
            _log_message_error(run_id, msg, account, e)
            return {"action": "error", "message_id": msg_id, "error": str(e)}


async def _process_message(run_id: str, msg: dict, account: dict, agent: AgentService) -> dict:
    """Single DM pipeline: build prompt -> AgentService.astream_analyze() -> apply hard rules -> route.

    Context is fetched by the LLM via bind_tools() — no Python-side pre-fetch needed
    (get_dm_history and get_dm_conversation_context are in ENGAGEMENT_SCOPE_TOOLS).
    """
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")
    message_text = msg.get("message_text", "")
    customer_ig_id = msg.get("customer_instagram_id", "")
    sender_username = msg.get("customer_username", "") or (f"user_{customer_ig_id[-6:]}" if customer_ig_id else "unknown")
    account_id = account.get("id", "")

    # Build prompt — no context pre-injected; LLM fetches it via bind_tools
    # customer_ig_id is passed as media_id so the LLM can call get_dm_history(customer_instagram_id)
    prompt = _build_agent_prompt(
        message_text=message_text,
        message_type="dm",
        sender_username=sender_username,
        account_id=account_id,
        media_id=customer_ig_id,
    )

    # Stream analysis via AgentService — LLM calls supabase tools as needed
    accumulated = ""
    async for chunk in agent.astream_analyze(prompt):
        accumulated += chunk

    # Parse JSON response
    result = AgentService._parse_json_response(accumulated)

    # Python safety override — applies VIP, urgent keywords, complaints
    result = _apply_hard_escalation_rules(result, message_text, 0.0)

    if result.get("needs_human"):
        return _handle_escalation(run_id, msg, account, result)

    suggested_reply = result.get("suggested_reply", "")
    confidence = result.get("confidence", 0)

    if (
        suggested_reply
        and confidence >= DM_MONITOR_CONFIDENCE_THRESHOLD
        and DM_MONITOR_AUTO_REPLY_ENABLED
    ):
        return _handle_auto_reply(run_id, msg, account, result, customer_ig_id)

    return _handle_skip(run_id, msg, account, result)


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
    """Execute reply: LLM confirmed via reply_to_dm_tool, Python enqueues here.

    LLM's JSON contains reply_executed=true and reply_job_payload when it called
    the reply_to_dm tool. Python uses the job_payload to enqueue via OutboundQueue.

    If LLM did not call the tool (reply_job_payload is null) but set suggested_reply,
    Python falls back to enqueueing directly from the suggested_reply text.
    """
    msg_id = msg.get("id", "")
    instagram_message_id = msg.get("instagram_message_id", "")
    suggested_reply = analysis.get("suggested_reply", "")

    # LLM confirmed reply via reply_to_dm_tool — use its validated job payload
    reply_job_payload = analysis.get("reply_job_payload")

    if reply_job_payload:
        # LLM called reply_to_dm_tool and it validated — use its job payload
        result = _enqueue_from_job_payload(reply_job_payload)
        # Override suggested_reply with what LLM confirmed via tool call
        suggested_reply = reply_job_payload.get("payload", {}).get("message_text", suggested_reply)
        llm_tool_used = True
    else:
        # Fallback: LLM didn't call the tool but set suggested_reply in JSON
        # Python enqueues directly from the suggested_reply text
        result = _enqueue_dm(
            conversation_id=customer_ig_id,
            recipient_id=customer_ig_id,
            message_text=suggested_reply,
            business_account_id=account.get("id", ""),
        )
        llm_tool_used = False

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
            "llm_tool_used": llm_tool_used,  # Did LLM call reply_to_dm_tool?
            "execution_id": result.get("execution_id"),
            "error": result.get("error") if not was_replied else None,
        },
    )

    if was_replied:
        logger.info(f"[{run_id}] Auto-replied to DM {msg_id} (llm_tool={llm_tool_used})")
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
def _build_agent_prompt(
    message_text: str,
    message_type: str,
    sender_username: str,
    account_id: str,
    media_id: str,
) -> str:
    """Build the analyze_message_agent prompt for a DM.

    Context is NOT pre-injected here — the LLM fetches it via bind_tools()
    (get_dm_history, get_dm_conversation_context, get_account_info).
    media_id is the customer_instagram_id so the LLM can call get_dm_history.
    """
    return PromptService.get("analyze_message_agent").format(
        message_text=message_text,
        message_type=message_type,
        sender_username=sender_username,
        account_id=account_id,
        media_id=media_id,
    )


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
