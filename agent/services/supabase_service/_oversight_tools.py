"""
Oversight Tools — @tool-decorated wrappers for the Oversight Brain.
================================================================
These are read-only explainability tools that query audit_log.
Kept separate from the main Supabase tools (which serve approval/webhook workflows).

Each tool is defined here ONCE: the description lives here, the function
signature lives here, the implementation lives in this file (direct _execute_query calls).
tools/oversight_tools.py imports from here — no Pydantic schemas, no Field descriptions.

Caching: L1 in-process TTLCache (45s) + L2 Redis (45s).
"""

from typing import Optional
from langchain_core.tools import tool

from ._infra import execute, cache_get, cache_set, supabase

# L1 in-process cache for operational entries — scoped to this module only
_AUTO_CONTEXT_CACHE: dict = {}   # simple dict with manual TTL tracking
_AUTO_CONTEXT_CACHE_TTL: int = 45


def _auto_context_get(key: str) -> Optional[dict | list]:
    """L1 cache check with manual TTL."""
    import time
    entry = _AUTO_CONTEXT_CACHE.get(key)
    if entry is None:
        return None
    if time.time() > entry["_expires_at"]:
        _AUTO_CONTEXT_CACHE.pop(key, None)
        return None
    return entry["data"]


def _auto_context_set(key: str, data):
    """L1 cache write with manual TTL."""
    import time
    _AUTO_CONTEXT_CACHE[key] = {"data": data, "_expires_at": time.time() + _AUTO_CONTEXT_CACHE_TTL}


@tool("Query audit_log for decision history. Use to explain why the agent took an action. "
      "Filter by resource_id, event_type, date range, or business account. "
      "Returns chronological list of audit entries with event_type, action, resource details.")
def get_audit_log_entries(
    resource_id: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[str] = None,
    business_account_id: Optional[str] = None,
    limit: int = 10,
) -> list:
    """Query audit_log for decision history.

    Args:
        resource_id: Filter by resource UUID (comment_id, post_id, etc.)
        event_type: Filter by event type (e.g. 'webhook_comment_processed')
        date_from: ISO date string lower bound (e.g. '2026-02-01')
        business_account_id: Filter by business account UUID
        limit: Max results to return (1-50, default 10)
    """
    # Build cache key from all filter params
    cache_key = f"oversight:audit:{resource_id}:{event_type}:{date_from}:{business_account_id}:{limit}"

    # L2 Redis check
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Build query
    query = supabase.table("audit_log").select(
        "id,event_type,action,resource_type,resource_id,details,created_at"
    )
    if resource_id:
        query = query.eq("resource_id", resource_id)
    if event_type:
        query = query.eq("event_type", event_type)
    if date_from:
        query = query.gte("created_at", date_from)
    if business_account_id:
        # Filter by business_account_id stored in details JSON, NOT user_id column
        query = query.filter("details->>business_account_id", "eq", business_account_id)

    result = execute(
        query.order("created_at", desc=True).limit(limit),
        table="audit_log",
        operation="select",
    )
    result_data = result.data or []
    cache_set(cache_key, result_data, ttl=45)
    return result_data


@tool("Get statistics for a scheduler run by run_id. "
      "Shows total_entries, event_type counts, action counts, started_at, finished_at. "
      "Use to understand the scope of an engagement_monitor or content_scheduler run.")
def get_run_summary(run_id: str) -> dict:
    """Get summary statistics for a scheduler run by run_id.

    Args:
        run_id: Run UUID from scheduler execution (found in audit_log details.run_id)
    """
    cache_key = f"oversight:run:{run_id}"

    # L2 Redis check
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    result = execute(
        supabase.table("audit_log")
            .select("event_type,action,created_at")
            .filter("details->>run_id", "eq", run_id)
            .order("created_at", desc=False),
        table="audit_log",
        operation="select",
    )
    entries = result.data or []

    if not entries:
        return {"error": "run_not_found", "run_id": run_id}

    event_counts: dict = {}
    action_counts: dict = {}
    for e in entries:
        event_counts[e["event_type"]] = event_counts.get(e["event_type"], 0) + 1
        action_counts[e["action"]] = action_counts.get(e["action"], 0) + 1

    summary = {
        "run_id": run_id,
        "total_entries": len(entries),
        "event_types": event_counts,
        "actions": action_counts,
        "started_at": entries[0]["created_at"],
        "finished_at": entries[-1]["created_at"],
    }
    cache_set(cache_key, summary, ttl=45)
    return summary


@tool("Fetch recent operational audit_log entries for auto-context injection. "
      "Excludes oversight_chat_query entries. Returns the most recent decisions "
      "for a business account across all event types.")
def get_operational_entries(business_account_id: str, limit: int = 12) -> list:
    """Fetch recent operational audit_log entries for a business account.

    Single-query replacement for the 17-type loop in _fetch_auto_context.
    Not exposed as a LangChain tool — internal use only (injected by OversightBrain).

    Args:
        business_account_id: UUID of the business account
        limit: Number of recent entries (default 12)
    """
    cache_key = f"oversight:operational:{business_account_id}:{limit}"

    # L1 check
    cached_l1 = _auto_context_get(cache_key)
    if cached_l1 is not None:
        return cached_l1

    # L2 Redis check
    cached_l2 = cache_get(cache_key)
    if cached_l2 is not None:
        _auto_context_set(cache_key, cached_l2)
        return cached_l2

    # Single query — DB does the exclusion, no Python-side type looping
    result = execute(
        supabase.table("audit_log")
            .select("id,event_type,action,resource_type,resource_id,details,created_at")
            .filter("details->>business_account_id", "eq", business_account_id)
            .neq("event_type", "oversight_chat_query")
            .order("created_at", desc=True)
            .limit(limit),
        table="audit_log",
        operation="select",
    )
    entries = result.data or []

    _auto_context_set(cache_key, entries)
    cache_set(cache_key, entries, ttl=45)
    return entries
