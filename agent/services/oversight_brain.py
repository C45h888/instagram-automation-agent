"""
Oversight Brain Service
=======================
Thin wrapper around AgentService for explainability queries.

Pattern: build prompt → AgentService.analyze_async() → log → return
No new LLM instance. No custom tool execution. Uses the single LLM entry point.

Caching: L1 TTLCache + L2 Redis (same pattern as supabase_service.py).
Conversation-aware: skips cache when chat_history is provided.
"""

import asyncio
import hashlib
import time
import uuid as uuid_mod
from typing import Optional

from cachetools import TTLCache

from config import logger
from services.supabase_service import SupabaseService, _cache_get, _cache_set
from services.prompt_service import PromptService
from metrics import SSE_DISCONNECTS, SSE_HEARTBEATS_SENT, SSE_ACTIVE_STREAMS


# L1 in-memory cache (mirrors supabase_service.py pattern)
_question_cache: TTLCache = TTLCache(maxsize=100, ttl=300)  # 5-minute TTL

# Lazy singleton AgentService — mirrors _get_agent_service() in automation_tools.py
_agent_service = None


def _get_agent():
    global _agent_service
    if _agent_service is None:
        from services.agent_service import AgentService  # lazy import: avoids circular
        _agent_service = AgentService()
    return _agent_service


def _cache_key(question: str, business_account_id: str = "") -> str:
    """Stable cache key for a question (history-less queries only)."""
    raw = f"{business_account_id}:{question.lower().strip()}"
    return f"oversight:{hashlib.md5(raw.encode()).hexdigest()}"


async def _fetch_auto_context(business_account_id: str, limit: int = 12) -> str:
    """Fetch recent operational audit_log decisions for a business account as context.

    Returns formatted string of recent operational decisions for prompt injection.
    Deliberately excludes oversight_chat_query entries — those are the agent's own
    prior chat replies, which are already supplied via the chat_history parameter
    in the request body (sourced from oversight_chat_sessions.messages).
    Including them here would duplicate context and pollute operational signal.
    """
    from tools.oversight_tools import _get_audit_log_entries

    # Whitelist of operational event types — what the agent actually DID.
    # oversight_chat_query is intentionally absent: chat history arrives via
    # the chat_history request param, not from the audit_log.
    OPERATIONAL_EVENT_TYPES = [
        "engagement_monitor_comment_processed",
        "engagement_monitor_escalation",
        "engagement_monitor_cycle_complete",
        "content_scheduler_post_evaluated",
        "content_scheduler_post_published",
        "content_scheduler_post_publish_failed",
        "content_scheduler_cycle_complete",
        "sales_attribution_processed",
        "sales_attribution_hard_rule",
        "ugc_discovery_post_processed",
        "ugc_discovery_cycle_complete",
        "dm_monitor_message_processed",
        "dm_monitor_escalation",
        "dm_monitor_cycle_complete",
        "analytics_report_generated",
        "analytics_report_cycle_complete",
        "weekly_learning_weights_updated",
    ]

    all_entries = []
    for event_type in OPERATIONAL_EVENT_TYPES:
        entries = _get_audit_log_entries(
            business_account_id=business_account_id,
            event_type=event_type,
            limit=limit,
        )
        all_entries.extend(entries)

    if not all_entries:
        return "(No recent agent decisions found for this account)"

    # Sort by recency and cap at limit
    all_entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    all_entries = all_entries[:limit]

    lines = []
    for e in all_entries:
        lines.append(
            f"- [{e.get('created_at', '?')}] {e.get('event_type', '?')}: "
            f"action={e.get('action', '?')}, resource={e.get('resource_id', 'N/A')}"
        )
    return "RECENT AGENT DECISIONS (auto-injected):\n" + "\n".join(lines)


async def chat(
    question: str,
    business_account_id: str = "",
    chat_history: Optional[list] = None,
    user_id: str = "dashboard-user",
    request_id: str = "unknown",
) -> dict:
    """Ask the Oversight Brain a question, returns explanation with sources.

    Args:
        question: User's natural language question
        chat_history: Prior turns [{"role": "user"|"assistant", "content": "..."}]
        user_id: For audit log (which dashboard user asked)
        request_id: For request tracing

    Returns:
        {
            "answer": str,
            "sources": list,
            "tools_used": list,
            "latency_ms": int,
            "request_id": str,
        }
    """
    start = time.time()

    # --- L1 / L2 cache (skip if conversation history changes context) ---
    cache_key = _cache_key(question, business_account_id)
    if not chat_history:
        if cache_key in _question_cache:
            logger.info(f"[{request_id}] Oversight Brain L1 cache hit")
            return {**_question_cache[cache_key], "request_id": request_id, "latency_ms": 0, "cached": True}

        l2 = _cache_get(cache_key)
        if l2:
            _question_cache[cache_key] = l2
            logger.info(f"[{request_id}] Oversight Brain L2 cache hit")
            return {**l2, "request_id": request_id, "latency_ms": 0, "cached": True}

    # --- Build prompt with conversation history and auto-context ---
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:  # Last 5 turns only to stay within context limits
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    # Auto-inject recent decisions as context
    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT
    auto_context = await _fetch_auto_context(business_account_id, limit=OVERSIGHT_AUTO_CONTEXT_LIMIT)

    prompt = PromptService.get("oversight_brain").format(
        input=f"{auto_context}\n\n{question}",
        chat_history=history_text or "(No prior conversation)",
    )

    # --- Single LLM entry point with timeout protection ---
    from config import OVERSIGHT_LLM_TIMEOUT_SECONDS
    try:
        result = await asyncio.wait_for(
            _get_agent().analyze_async(prompt),
            timeout=OVERSIGHT_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(f"[{request_id}] Oversight Brain LLM timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
        result = {
            "error": "timeout",
            "message": f"LLM response timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s",
        }

    latency_ms = result.pop("_latency_ms", int((time.time() - start) * 1000))
    tools_called = result.pop("_tools_called", [])

    response = {
        "answer": result.get("answer", "I need more context from the database to answer that."),
        "sources": result.get("sources", []),
        "tools_used": tools_called,
        "latency_ms": latency_ms,
        "request_id": request_id,
    }

    # --- Store in cache (no-history questions only) ---
    if not chat_history:
        cacheable = {k: v for k, v in response.items() if k not in ("request_id", "latency_ms")}
        _question_cache[cache_key] = cacheable
        _cache_set(cache_key, cacheable, ttl=300)

    # --- Audit every query ---
    SupabaseService.log_decision(
        event_type="oversight_chat_query",
        action="error" if "error" in result else "answered",
        resource_type="oversight_query",
        resource_id=str(uuid_mod.uuid4()),
        user_id=user_id,
        details={
            "question": question[:500],
            "answer": response["answer"][:500],
            "business_account_id": business_account_id,
            "tools_used": tools_called,
            "latency_ms": latency_ms,
            "request_id": request_id,
            "streamed": False,
        },
    )

    logger.info(
        f"[{request_id}] Oversight Brain answered in {latency_ms}ms "
        f"(tools: {tools_called}, sources: {len(response['sources'])})"
    )
    return response


async def astream_chat(
    question: str,
    business_account_id: str = "",
    chat_history: Optional[list] = None,
    user_id: str = "dashboard-user",
    request_id: str = "unknown",
    request=None,  # FastAPI Request for disconnect detection
):
    """Streaming version of chat() with Phase 1 hardening.

    Features:
    - Event IDs for Last-Event-ID resume support
    - Heartbeat pings every N seconds (prevents proxy timeouts)
    - Disconnect detection (stops LLM on client disconnect)
    - Tool status events (tool_call, tool_done)
    - Proper SSE formatting (id:, event:, data: fields)

    Architecture: both the LLM call and the heartbeat loop run as background
    asyncio.Tasks that post events into a shared queue. The generator's main
    body is purely a consumer — it blocks on queue.get() and yields whatever
    arrives first (heartbeat ping or LLM token). This ensures bytes reach nginx
    during the full duration of LLM inference, preventing proxy_read_timeout (504).

    Args:
        request: FastAPI Request object for disconnect detection
    """
    import json as json_mod
    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT, OVERSIGHT_LLM_TIMEOUT_SECONDS, SSE_HEARTBEAT_INTERVAL_SECONDS

    start = time.time()
    event_id = 0
    accumulated = ""

    # Helper: format SSE event with id and event type
    def format_sse_event(payload: dict, event_type: str = "message") -> str:
        nonlocal event_id
        event_id += 1
        data = json_mod.dumps(payload)
        return f"id: {event_id}\nevent: {event_type}\ndata: {data}\nretry: 3000\n\n"

    # Helper: check if client disconnected
    async def is_disconnected() -> bool:
        if not request:
            return False
        try:
            return await request.is_disconnected()
        except Exception:
            return False

    # Build conversation history text
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    # Auto-inject recent decisions as context
    auto_context = await _fetch_auto_context(
        business_account_id,
        limit=OVERSIGHT_AUTO_CONTEXT_LIMIT,
    )

    prompt = PromptService.get("oversight_brain").format(
        input=f"{auto_context}\n\n{question}",
        chat_history=history_text or "(No prior conversation)",
    )

    # Shared queue: both background tasks write here; generator reads and yields.
    # Queue is consumed item-by-item as events arrive — heartbeats are never
    # delayed behind LLM tokens because LLM tokens don't exist in the queue yet
    # during inference. The generator sits at queue.get() and wakes immediately
    # on whichever event arrives first.
    event_queue: asyncio.Queue = asyncio.Queue()

    async def on_tool_event(event: dict):
        """Callback from agent_service for tool events."""
        await event_queue.put(("tool_event", event))

    async def run_llm():
        """Background task: run LLM inference, post tokens/errors/done to queue."""
        try:
            agent = _get_agent()
            async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
                async for chunk in agent.astream_analyze(prompt, on_event=on_tool_event):
                    await event_queue.put(("token", chunk))
        except TimeoutError:
            logger.warning(f"[{request_id}] Oversight stream timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
            await event_queue.put(("error", {"error": "timeout"}))
        except asyncio.CancelledError:
            pass  # cancelled by generator on client disconnect — expected
        except Exception as e:
            logger.error(f"[{request_id}] Oversight stream error: {e}")
            await event_queue.put(("error", {"error": "stream_failed", "message": str(e)}))
        finally:
            # Always signal end so the generator's queue.get() loop can exit
            await event_queue.put(("stream_done", None))

    async def heartbeat_loop():
        """Background task: post a ping every N seconds while LLM is running."""
        while True:
            try:
                await asyncio.sleep(SSE_HEARTBEAT_INTERVAL_SECONDS)
                await event_queue.put(("heartbeat", None))
                SSE_HEARTBEATS_SENT.labels(endpoint="oversight").inc()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[{request_id}] Heartbeat error: {e}")
                break

    SSE_ACTIVE_STREAMS.labels(endpoint="oversight").inc()

    # Start both tasks — they run concurrently and independently
    llm_task = asyncio.create_task(run_llm())
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        # Generator main loop: consume queue, yield immediately on each event.
        # Heartbeats and tokens are interleaved naturally — no event waits for another.
        while True:
            try:
                event_type, event_data = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=OVERSIGHT_LLM_TIMEOUT_SECONDS + 10,  # outer safety net
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{request_id}] Queue drain safety timeout — forcing stream end")
                break

            if await is_disconnected():
                logger.info(f"[{request_id}] Client disconnected")
                SSE_DISCONNECTS.labels(endpoint="oversight").inc()
                llm_task.cancel()
                break

            if event_type == "heartbeat":
                yield format_sse_event({"heartbeat": True}, event_type="ping")

            elif event_type == "tool_event":
                yield format_sse_event(event_data, event_type=event_data.get("event_type", "tool_status"))

            elif event_type == "token":
                accumulated += event_data
                yield format_sse_event({"token": event_data}, event_type="message")

            elif event_type == "error":
                yield format_sse_event(event_data, event_type="error")
                break

            elif event_type == "stream_done":
                break

    finally:
        # Always clean up both tasks regardless of how the loop exited
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if not llm_task.done():
            llm_task.cancel()
            try:
                await llm_task
            except asyncio.CancelledError:
                pass
        SSE_ACTIVE_STREAMS.labels(endpoint="oversight").dec()

    # Final completion event — always emitted so the frontend persistMessage() fires
    latency_ms = int((time.time() - start) * 1000)
    yield format_sse_event(
        {"done": True, "latency_ms": latency_ms},
        event_type="done"
    )

    # Audit log (fire-and-forget)
    SupabaseService.log_decision(
        event_type="oversight_chat_query",
        action="stream_answered",
        resource_type="oversight_query",
        resource_id=str(uuid_mod.uuid4()),
        user_id=user_id,
        details={
            "question": question[:500],
            "answer_preview": accumulated[:500],
            "business_account_id": business_account_id,
            "latency_ms": latency_ms,
            "request_id": request_id,
            "streamed": True,
            "events_sent": event_id,
        },
    )

    logger.info(f"[{request_id}] Oversight Brain streamed in {latency_ms}ms ({event_id} events)")
