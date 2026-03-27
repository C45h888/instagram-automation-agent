"""
DM Tools — @tool-decorated wrappers around DMService.
================================================
Each tool is defined here ONCE: the description lives here, the function
signature lives here, the implementation lives in DMService.
supabase_tools.py imports from here — no Pydantic schemas, no Field descriptions.
"""

from langchain_core.tools import tool

from ._dms import DMService


@tool("Fetch DM conversation history between a sender and business account. "
      "Returns messages with direction (inbound/outbound), timestamps, and message_type. "
      "Ordered newest-first.")
def get_dm_history(business_account_id: str, sender_id: str, limit: int = 5) -> list:
    """Fetch DM conversation history for a sender.

    Args:
        business_account_id: UUID of the Instagram business account
        sender_id: Instagram numeric ID of the DM sender (customer_instagram_id)
        limit: Number of recent messages to fetch (1-20, default 5)
    """
    return DMService.get_dm_history(sender_id, business_account_id, limit)


@tool("Fetch DM conversation metadata: within_window (24h reply window status), "
      "window_expires_at, conversation_status, message_count, last_message_at. "
      "Use to verify if the 24-hour messaging window is still open.")
def get_dm_conversation_context(business_account_id: str, sender_id: str) -> dict:
    """Fetch conversation-level metadata for a sender.

    Args:
        business_account_id: UUID of the Instagram business account
        sender_id: Instagram numeric ID of the DM sender (customer_instagram_id)
    """
    return DMService.get_dm_conversation_context(sender_id, business_account_id)
