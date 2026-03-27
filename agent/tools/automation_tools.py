"""
LangChain Automation Tools - Customer Service
==============================================
Execution tools for Instagram automation.
These are Python-side only — NOT routed through AgentService.bind_tools().

reply_to_comment / reply_to_dm: Execute replies via OutboundQueue.
_apply_hard_escalation_rules: Python safety overrides applied after AgentService returns.

analyze_message REMOVED — replaced by AgentService.astream_analyze() + analyze_message_agent prompt.
LLM fetches context via bind_tools() (supabase tools), generates analysis, Python applies hard rules.
"""

import uuid as _uuid
from datetime import datetime, timezone
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from config import (
    ESCALATION_CATEGORIES,
    URGENT_KEYWORDS,
    VIP_LIFETIME_VALUE_THRESHOLD,
    MAX_COMMENT_REPLY_LENGTH,
    MAX_DM_REPLY_LENGTH,
)


# ================================
# Input Schemas
# ================================
class ReplyToCommentInput(BaseModel):
    comment_id: str = Field(description="Instagram comment ID")
    reply_text: str = Field(description="Reply text (max 2200 chars)")
    business_account_id: str = Field(description="Business account UUID")
    post_id: str = Field(description="Instagram media ID")


class ReplyToDMInput(BaseModel):
    conversation_id: str = Field(description="Instagram conversation ID")
    recipient_id: str = Field(description="Recipient's Instagram ID")
    message_text: str = Field(description="DM text (max 150 chars)")
    business_account_id: str = Field(description="Business account UUID")


# ================================
# Python safety overrides — applied AFTER AgentService.astream_analyze() returns
# ================================
def _apply_hard_escalation_rules(result: dict, message_text: str, customer_value: float) -> dict:
    """Override LLM decision with hard rules for VIP, urgent, complaints.

    This is a defense-in-depth layer. The LLM applies escalation logic via the
    analyze_message_agent prompt first. Python overrides as a safety net for:
    - VIP customers (LTV threshold) — always escalate regardless of LLM output
    - Urgent keywords (even if LLM missed them)
    - Complaint + negative sentiment combinations LLM may miss
    - Complex multi-part questions LLM may underestimate
    """
    lower_text = message_text.lower()

    # Rule 1: Urgent keywords -> priority = urgent
    urgent_found = [kw for kw in URGENT_KEYWORDS if kw in lower_text]
    if urgent_found:
        result["priority"] = "urgent"
        result["keywords_matched"] = result.get("keywords_matched", []) + urgent_found

    # Rule 2: VIP customer -> always escalate
    if customer_value > VIP_LIFETIME_VALUE_THRESHOLD:
        result["needs_human"] = True
        result["escalation_reason"] = f"VIP customer (${customer_value:.0f} lifetime value)"
        if result.get("priority") != "urgent":
            result["priority"] = "high"

    # Rule 3: Complaint + negative sentiment -> escalate
    category = result.get("category", "general")
    sentiment = result.get("sentiment", "neutral")
    if category in ESCALATION_CATEGORIES and sentiment == "negative":
        result["needs_human"] = True
        result["escalation_reason"] = (
            result.get("escalation_reason") or f"Negative {category} requires human"
        )

    # Rule 4: Long complex message -> escalate
    if len(message_text) > 300 and "?" in message_text:
        result["needs_human"] = True
        result["escalation_reason"] = (
            result.get("escalation_reason") or "Complex multi-part question"
        )

    return result


# ================================
# reply_to_comment Implementation (queue-first)
# ================================
def _reply_to_comment(
    comment_id: str,
    reply_text: str,
    business_account_id: str,
    post_id: str,
) -> dict:
    """Enqueue comment reply job. Returns immediately with queued=True.

    The worker executes the actual HTTP call with 5-retry backoff.
    Callers check result.get("success") — unchanged contract.
    """
    from services.outbound_queue import OutboundQueue

    if len(reply_text) > MAX_COMMENT_REPLY_LENGTH:
        return {
            "success": False,
            "error": "reply_too_long",
            "message": f"Reply exceeds {MAX_COMMENT_REPLY_LENGTH} chars ({len(reply_text)})",
        }

    job = {
        "job_id": str(_uuid.uuid4()),
        "action_type": "reply_comment",
        "priority": "high",
        "endpoint": "/api/instagram/reply-comment",
        "payload": {
            "comment_id": comment_id,
            "reply_text": reply_text,
            "business_account_id": business_account_id,
            "post_id": post_id,
        },
        "business_account_id": business_account_id,
        "idempotency_key": f"comment:{comment_id}",
        "source": "automation_tools",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
        "last_error": None,
    }
    return OutboundQueue.enqueue(job)


# ================================
# reply_to_dm Implementation (queue-first)
# ================================
def _reply_to_dm(
    conversation_id: str,
    recipient_id: str,
    message_text: str,
    business_account_id: str,
) -> dict:
    """Enqueue DM reply job. Returns immediately with queued=True.

    Callers check result.get("success") — unchanged contract.
    """
    from services.outbound_queue import OutboundQueue

    if len(message_text) > MAX_DM_REPLY_LENGTH:
        return {
            "success": False,
            "error": "message_too_long",
            "message": f"DM exceeds {MAX_DM_REPLY_LENGTH} chars ({len(message_text)})",
        }

    job = {
        "job_id": str(_uuid.uuid4()),
        "action_type": "reply_dm",
        "priority": "high",
        "endpoint": "/api/instagram/reply-dm",
        "payload": {
            "conversation_id": conversation_id,
            "recipient_id": recipient_id,
            "message_text": message_text,
            "business_account_id": business_account_id,
        },
        "business_account_id": business_account_id,
        "idempotency_key": f"dm:reply:{recipient_id}:{business_account_id}",
        "source": "automation_tools",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
        "last_error": None,
    }
    return OutboundQueue.enqueue(job)


# ================================
# Tool Definitions — execution tools only
# analyze_message_tool REMOVED (recursion loop). Use AgentService.bind_tools() path.
# ================================
reply_to_comment_tool = StructuredTool.from_function(
    func=_reply_to_comment,
    name="reply_to_comment",
    description="Send a reply to an Instagram comment via backend proxy. Max 2200 chars. Queue-first — returns immediately.",
    args_schema=ReplyToCommentInput,
)

reply_to_dm_tool = StructuredTool.from_function(
    func=_reply_to_dm,
    name="reply_to_dm",
    description="Send a DM reply via backend proxy. Max 150 chars. Queue-first — returns immediately.",
    args_schema=ReplyToDMInput,
)


# ================================
# Tool Registry
# ================================
# NOTE: AUTOMATION_TOOLS is kept for backward compat with tools/__init__.py imports.
# analyze_message_tool is NOT included — it caused a recursion loop when used via bind_tools().
# _reply_to_comment and _reply_to_dm are Python-executed only, not via bind_tools().
# Both are safe to import from here as standalone Python functions.
# ================================
AUTOMATION_TOOLS = [
    reply_to_comment_tool,
    reply_to_dm_tool,
]
