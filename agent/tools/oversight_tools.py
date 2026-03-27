"""
Oversight Brain Tools
====================
Aggregated wrapper around services/supabase_service/_oversight_tools.py.

Two categories:
  1. LangChain tools (exposed to the LLM via OversightBrain's <<TOOL_CALL>> markers):
       get_audit_log_entries_tool, get_run_summary_tool
  2. Internal helpers (used by OversightBrain directly, not exposed to LLM):
       _get_audit_log_entries, _get_run_summary, _get_operational_entries

The internal functions are re-exported from the @tool-decorated versions
in services/supabase_service/_oversight_tools.py so OversightBrain doesn't need
to change its imports.
"""

from langchain_core.tools import StructuredTool

# Internal functions — re-exported for OversightBrain (backward compat)
# These are the actual implementations; OversightBrain calls them directly
# when it encounters <<TOOL_CALL>> markers (not via llm.bind_tools).
from services.supabase_service._oversight_tools import (
    get_audit_log_entries as _get_audit_log_entries,
    get_run_summary as _get_run_summary,
    get_operational_entries as _get_operational_entries,
)

# LangChain tool wrappers — @tool-decorated functions converted to StructuredTool
# for OversightBrain's tool-calling mechanism
get_audit_log_entries_tool = StructuredTool.from_function(
    func=_get_audit_log_entries,
    name="get_audit_log_entries",
)

get_run_summary_tool = StructuredTool.from_function(
    func=_get_run_summary,
    name="get_run_summary",
)


# LangChain tool list (used by tools/__init__.py)
OVERSIGHT_TOOLS = [
    get_audit_log_entries_tool,
    get_run_summary_tool,
]
