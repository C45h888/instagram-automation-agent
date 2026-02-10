"""
Oversight Brain Service
=======================
Thin wrapper around AgentService for explainability queries.

Pattern: build prompt → AgentService.analyze_async() → log → return
No new LLM instance. No custom tool execution. Uses the single LLM entry point.

Caching: L1 TTLCache + L2 Redis (same pattern as supabase_service.py).
Conversation-aware: skips cache when chat_history is provided.
"""

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


def _cache_key(question: str) -> str:
    """Stable cache key for a question (history-less queries only)."""
    return f"oversight:{hashlib.md5(question.lower().strip().encode()).hexdigest()}"


async def chat(
    question: str,
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
    cache_key = _cache_key(question)
    if not chat_history:
        if cache_key in _question_cache:
            logger.info(f"[{request_id}] Oversight Brain L1 cache hit")
            return {**_question_cache[cache_key], "request_id": request_id, "latency_ms": 0, "cached": True}

        l2 = _cache_get(cache_key)
        if l2:
            _question_cache[cache_key] = l2
            logger.info(f"[{request_id}] Oversight Brain L2 cache hit")
            return {**l2, "request_id": request_id, "latency_ms": 0, "cached": True}

    # --- Build prompt with conversation history ---
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:  # Last 5 turns only to stay within context limits
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    prompt = PromptService.get("oversight_brain").format(
        input=question,
        chat_history=history_text or "(No prior conversation)",
    )

    # --- Single LLM entry point (same as all other modules) ---
    result = await _get_agent().analyze_async(prompt)

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
            "tools_used": tools_called,
            "latency_ms": latency_ms,
            "request_id": request_id,
        },
    )

    logger.info(
        f"[{request_id}] Oversight Brain answered in {latency_ms}ms "
        f"(tools: {tools_called}, sources: {len(response['sources'])})"
    )
    return response
