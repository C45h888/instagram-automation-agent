Here's the plan for implementing the @tool decorator bridging pattern.

Plan: @tool Decorator on SupabaseService Domain Classes
The Core Problem We're Solving

TODAY: Two contracts, maintained by hand in two places
─────────────────────────────────────────────────────
supabase_tools.py          SupabaseService methods
     │                         │
args_schema (Pydantic)     function signature
     │                         │
     └── enforced by hand ──────┘
          (easy to drift)

AFTER: One contract, one place, enforced automatically
─────────────────────────────────────────────────────
Domain service methods decorated with @tool
     │
     │  schema inferred from type annotations
     │  description from decorator parameter
     │  function = schema = tool
     │
supabase_tools.py imports & aggregates only
Architecture After Fix

services/supabase_service/
    _engagement.py           → EngagementTools (@tool-decorated methods)
    _dms.py                  → DMTools (@tool-decorated methods)
    _ops.py                  → OpsTools (@tool-decorated methods)
    _attribution.py           → AttributionTools (@tool-decorated methods)
    _content.py               → ContentTools (@tool-decorated methods)
    
tools/
    supabase_tools.py        → aggregates all tools into SUPABASE_TOOLS list
                               (no schema classes, no Field descriptions)
Step-by-Step Implementation
Step 1 — Create the tool modules alongside domain services

For each domain service, create a matching _X_tools.py file in services/supabase_service/. These files:

Import the domain service class
Define @tool-decorated wrappers around the service methods
Keep field descriptions as single source of truth

# services/supabase_service/_engagement_tools.py
"""Engagement Tools — @tool-decorated wrappers around EngagementService."""

from langchain_core.tools import tool
from services.supabase_service._engagement import EngagementService


@tool("Fetch post details: caption, likes, comments, engagement_rate, media_type. "
      "Use when evaluating a comment reply or post.")
def get_post_context(post_id: str) -> dict:
    """Fetch post context from instagram_media.

    Args:
        post_id: Instagram media ID to fetch context for
    """
    return EngagementService.get_post_context(post_id)


@tool("Fetch business account info: username, name, account_type, followers_count, "
          "biography, category. Use to understand brand voice and context.")
def get_account_info(business_account_id: str) -> dict:
    """Fetch account info from instagram_business_accounts.

    Args:
        business_account_id: UUID of the Instagram business account
    """
    return EngagementService.get_account_info(business_account_id)


@tool("Fetch recent comments for pattern analysis. Returns text, sentiment, category, priority.")
def get_recent_comments(business_account_id: str, limit: int = 10) -> list:
    """Fetch recent comments for a business account.

    Args:
        business_account_id: UUID of the Instagram business account
        limit: Number of recent comments to fetch (1-50, default 10)
    """
    return EngagementService.get_recent_comments(business_account_id, limit)
Step 2 — Update supabase_tools.py to import from tool modules

supabase_tools.py becomes a pure aggregator — no schemas, no Pydantic classes, no descriptions:


"""Aggregated Supabase tools for AgentService binding."""

from langchain_core.tools import StructuredTool

# Import @tool-decorated functions
from services.supabase_service._engagement_tools import (
    get_post_context,
    get_account_info,
    get_recent_comments,
)
from services.supabase_service._dm_tools import (
    get_dm_history,
    get_dm_conversation_context,
)
from services.supabase_service._content_tools import (
    get_post_performance,      # lives in _content.py alongside post methods
)
from services.supabase_service._ops_tools import (
    log_decision,
)


def _as_structured_tool(tool_func) -> StructuredTool:
    """Convert a @tool-decorated function to StructuredTool.
    
    @tool returns a Tool directly; StructuredTool.from_function
    wraps it. This handles both cases.
    """
    from langchain_core.tools import StructuredTool
    if isinstance(tool_func, StructuredTool):
        return tool_func
    return StructuredTool.from_function(tool_func)


# Map tool names to their @tool-decorated functions
TOOL_MAP = {
    "get_post_context": get_post_context,
    "get_account_info": get_account_info,
    "get_recent_comments": get_recent_comments,
    "get_dm_history": get_dm_history,
    "get_dm_conversation_context": get_dm_conversation_context,
    "get_post_performance": get_post_performance,
    "log_decision": log_decision,
}

SUPABASE_TOOLS = [TOOL_MAP[name] for name in TOOL_MAP]
This is a pure rename and re-export — no new logic.

Step 3 — Convert all domain service classes

For each domain service (_dms.py, _ops.py, _content.py), create a matching _X_tools.py file following the same pattern. The full list:

Tool Module	Source Service	Tools
_engagement_tools.py	EngagementService	get_post_context, get_account_info, get_recent_comments
_dm_tools.py	DMService	get_dm_history, get_dm_conversation_context
_ops_tools.py	OpsService	log_decision
_content_tools.py	ContentService	get_post_performance
AttributionService tools are intentionally excluded — none of its methods are used as LangChain tools. They are internal pipeline functions.

Step 4 — Audit log_decision return type

Before wiring log_decision as a tool, fix the silent failure problem identified earlier. Change the return to include the audit row ID:


# _ops_tools.py
@tool("Log an agent decision to the audit_log table. Returns the audit row ID.")
def log_decision(...) -> dict:
    """Log agent decision. Returns {"success": bool, "audit_log_id": str}"""
    success = OpsService.log_decision(...)
    # If called as a @tool, we need to return something the LLM can read
    return {"success": success, "audit_log_id": "...", "event_type": event_type}
The LLM currently receives True from this tool — it has no idea what audit row was created. This makes OversightBrain harder to use because the LLM that logged the decision doesn't know the row ID.

Step 5 — Verify AgentService tool binding still works

After the conversion, AgentService imports SUPABASE_TOOLS exactly as before. The binding is unchanged:


# agent_service.py (unchanged)
from tools.supabase_tools import SUPABASE_TOOLS

ENGAGEMENT_SCOPE_TOOLS = [
    get_post_context,        # already a @tool-decorated function, not a StructuredTool
    get_account_info,
    get_recent_comments,
    log_decision,
    analyze_message_tool,    # still from automation_tools.py
    reply_to_comment_tool,     # still from automation_tools.py
    reply_to_dm_tool,         # still from automation_tools.py
]
The key check: llm.bind_tools() accepts both StructuredTool instances and plain @tool-decorated functions. Both are valid tool call targets.

Step 6 — Migrate OVERSIGHT_TOOLS

oversight_tools.py currently bypasses SupabaseService entirely. Convert it to the same pattern:


# services/supabase_service/_oversight_tools.py
from langchain_core.tools import tool

@tool("Query audit_log for decision history. Filter by resource_id, event_type, date, or account.")
def get_audit_log_entries(
    resource_id: str | None = None,
    event_type: str | None = None,
    date_from: str | None = None,
    business_account_id: str | None = None,
    limit: int = 10,
) -> list:
    ...

@tool("Get statistics for a scheduler run by run_id. "
          "Shows total_entries, event_type counts, action counts, start/end timestamps.")
def get_run_summary(run_id: str) -> dict:
    ...
Then update tools/oversight_tools.py to import from the service and become a pure aggregator (same as supabase_tools.py).

Impact Assessment
File	Change Type	Risk
supabase_tools.py	Rewrite — remove Pydantic schemas, import from tool modules	Low — becomes simpler
tools/oversight_tools.py	Rewrite — remove Pydantic schemas, import from service	Low — becomes simpler
services/supabase_service/_engagement_tools.py	New file	None — additive
services/supabase_service/_dm_tools.py	New file	None — additive
services/supabase_service/_ops_tools.py	New file	None — additive
services/supabase_service/_content_tools.py	New file	None — additive
agent_service.py	Unchanged	Zero impact
All domain service classes	Unchanged	Zero impact
What Changes for the LLM
Before	After
Schema derived from hand-written Pydantic classes	Schema inferred from function type annotations
Description in Field(description=...) in one file	Description in @tool("...") in domain module
Schema drift possible when function signature changes	Schema and function are the same unit — cannot drift
log_decision returns True — LLM doesn't know the audit ID	log_decision returns {"success": bool, "audit_log_id": str}
