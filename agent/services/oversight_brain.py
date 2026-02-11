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
    """Fetch recent audit_log decisions for a business account as context.

    Returns formatted string of recent decisions for prompt injection.
    Uses the existing oversight tool function directly (not via LLM).
    """
    from config import logger
    from tools.oversight_tools import _get_audit_log_entries

    entries = _get_audit_log_entries(
        business_account_id=business_account_id,
        limit=limit,
    )

    if not entries:
        return "(No recent agent decisions found for this account)"

    lines = []
    for e in entries:
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
):
    """Streaming version of chat(). Yields SSE events.

    Auto-injects recent audit_log decisions as context.
    Streams tokens via SSE: data: {"token": "..."}\n\n
    Final event: data: {"done": true, "latency_ms": ..., "request_id": ...}\n\n
    """
    import json as json_mod
    start = time.time()

    # Build conversation history text
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    # Auto-inject recent decisions as context
    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT, OVERSIGHT_LLM_TIMEOUT_SECONDS
    auto_context = await _fetch_auto_context(
        business_account_id,
        limit=OVERSIGHT_AUTO_CONTEXT_LIMIT,
    )

    prompt = PromptService.get("oversight_brain").format(
        input=f"{auto_context}\n\n{question}",
        chat_history=history_text or "(No prior conversation)",
    )

    # Stream with timeout
    accumulated = ""
    try:
        agent = _get_agent()
        async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
            async for chunk in agent.astream_analyze(prompt):
                accumulated += chunk
                yield f"data: {json_mod.dumps({'token': chunk})}\n\n"
    except TimeoutError:
        logger.warning(f"[{request_id}] Oversight stream timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
        yield f"data: {json_mod.dumps({'error': 'timeout'})}\n\n"

    latency_ms = int((time.time() - start) * 1000)

    # Final event
    yield f"data: {json_mod.dumps({'done': True, 'latency_ms': latency_ms, 'request_id': request_id})}\n\n"

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
        },
    )

    logger.info(f"[{request_id}] Oversight Brain streamed in {latency_ms}ms")
