"""
Ops Tools — @tool-decorated wrappers around OpsService.
==================================================
Each tool is defined here ONCE: the description lives here, the function
signature lives here, the implementation lives in OpsService.
supabase_tools.py imports from here — no Pydantic schemas, no Field descriptions.

Note on log_decision:
  - SupabaseService.log_decision returns bool (success/failure)
  - The @tool wrapper enriches the return to include the audit row details
    so the LLM knows what was logged and can reference it later
"""

from langchain_core.tools import tool

from ._ops import OpsService


@tool("Log an agent decision to the audit_log table. Returns success status and "
      "the audit log row ID which can be used to look up this decision later. "
      "Always log decisions for traceability before taking action.")
def log_decision(
    event_type: str,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: str,
    details: dict,
    ip_address: str = "",
) -> dict:
    """Log an agent decision to the audit_log table.

    Args:
        event_type: Type of event (e.g. 'comment_reply_approval', 'dm_reply_approval',
                     'post_approval', 'oversight_chat_query')
        action: Decision taken ('approved', 'rejected', 'modified', 'escalated')
        resource_type: Type of resource ('comment', 'dm', 'post')
        resource_id: ID of the resource being evaluated
        user_id: UUID of the business account (user)
        details: Additional context about the decision (free-form dict)
        ip_address: IP address of the requesting client (optional)
    """
    success = OpsService.log_decision(
        event_type=event_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        details=details,
        ip_address=ip_address,
    )
    # Enrich return so LLM knows what was logged
    return {
        "success": success,
        "event_type": event_type,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "logged_at": details.get("timestamp", ""),
    }
