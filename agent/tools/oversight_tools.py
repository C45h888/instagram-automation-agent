"""
Oversight Brain Tools
=====================
Read-only explainability tools for the Oversight Brain.
Kept separate from supabase_tools.py (which serves approval/webhook workflows).

These query audit_log and scheduler run data to explain agent decisions.
"""

from typing import Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


# ================================
# Input Schemas
# ================================
class AuditLogQueryInput(BaseModel):
    resource_id: Optional[str] = Field(None, description="Filter by resource UUID (comment_id, post_id, etc.)")
    event_type: Optional[str] = Field(None, description="Filter by event type (e.g. 'webhook_comment_processed')")
    date_from: Optional[str] = Field(None, description="ISO date string e.g. '2026-02-01'")
    business_account_id: Optional[str] = Field(None, description="Filter by business account UUID (matches user_id in audit_log)")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")


class RunSummaryInput(BaseModel):
    run_id: str = Field(description="Run UUID from scheduler execution (found in audit_log details.run_id)")


# ================================
# Implementations
# ================================
def _get_audit_log_entries(
    resource_id: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[str] = None,
    business_account_id: Optional[str] = None,
    limit: int = 10,
) -> list:
    """Query audit_log for decision history."""
    from services.supabase_service import _execute_query, _cache_get, _cache_set
    from config import supabase

    # Build cache key from all filter params
    cache_key = f"oversight:audit:{resource_id}:{event_type}:{date_from}:{business_account_id}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

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
        query = query.eq("user_id", business_account_id)

    result = _execute_query(
        query.order("created_at", desc=True).limit(limit),
        table="audit_log",
        operation="select",
    )
    result_data = result.data or []
    _cache_set(cache_key, result_data, ttl=45)
    return result_data


def _get_run_summary(run_id: str) -> dict:
    """Get summary statistics for a scheduler run by run_id."""
    from services.supabase_service import _execute_query, _cache_get, _cache_set
    from config import supabase

    # Build cache key
    cache_key = f"oversight:run:{run_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = _execute_query(
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
    _cache_set(cache_key, summary, ttl=45)
    return summary


# ================================
# Tool Definitions
# ================================
get_audit_log_entries_tool = StructuredTool.from_function(
    func=_get_audit_log_entries,
    name="get_audit_log_entries",
    description=(
        "Query audit_log for decision history. Use to explain why the agent took an action. "
        "Filter by resource_id, event_type, or date. Returns chronological list of decisions."
    ),
    args_schema=AuditLogQueryInput,
)

get_run_summary_tool = StructuredTool.from_function(
    func=_get_run_summary,
    name="get_run_summary",
    description=(
        "Get statistics for a scheduler run (engagement_monitor, content_scheduler, etc.) by run_id. "
        "Shows total_entries, event_type counts, action counts, start/end timestamps."
    ),
    args_schema=RunSummaryInput,
)


OVERSIGHT_TOOLS = [
    get_audit_log_entries_tool,
    get_run_summary_tool,
]
