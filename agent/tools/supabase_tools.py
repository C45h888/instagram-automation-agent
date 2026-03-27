"""
Supabase Tools — Aggregated LangChain tool wrappers
===============================================
Pure aggregator: imports @tool-decorated functions from domain service modules
and converts them to StructuredTool instances for AgentService binding.

NO Pydantic schemas written here — they live in the @tool-decorated functions
in services/supabase_service/ alongside the implementations.

The @tool decorator bridges the gap:
  - Description = @tool("...") parameter
  - Schema = function type annotations
  - Function = implementation in domain service class
  One source of truth. No drift possible.

Structure:
  @tool-decorated function (description + type hints + implementation)
      ↓
  _as_structured_tool() helper (converts to StructuredTool if needed)
      ↓
  SUPABASE_TOOLS list (passed to llm.bind_tools())
"""

from langchain_core.tools import StructuredTool

from services.supabase_service._engagement_tools import (
    get_post_context,
    get_account_info,
    get_recent_comments,
    get_post_performance,
)
from services.supabase_service._dm_tools import (
    get_dm_history,
    get_dm_conversation_context,
)
from services.supabase_service._ops_tools import log_decision


def _as_structured_tool(tool_func) -> StructuredTool:
    """Convert a @tool-decorated function to StructuredTool.

    @tool-decorated functions are Tool instances and can be passed directly
    to llm.bind_tools(). StructuredTool.from_function() wraps them explicitly
    so all tools in SUPABASE_TOOLS are consistently StructuredTool instances.
    """
    return StructuredTool.from_function(tool_func)


# ================================
# Tool Registry
# ================================
# All 7 tools from the original supabase_tools.py, now @tool-decorated.
# Maps directly to what AgentService binds in scoped tool sets.
# ================================
SUPABASE_TOOLS = [
    _as_structured_tool(get_post_context),
    _as_structured_tool(get_account_info),
    _as_structured_tool(get_recent_comments),
    _as_structured_tool(get_dm_history),
    _as_structured_tool(get_dm_conversation_context),
    _as_structured_tool(get_post_performance),
    _as_structured_tool(log_decision),
]
