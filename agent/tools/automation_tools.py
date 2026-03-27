"""
LangChain Automation Tools - Customer Service
==============================================
Execution tools for Instagram automation.

reply_to_comment / reply_to_dm: @tool-decorated functions — LLM calls via bind_tools()
to validate and prepare reply payloads. Python enqueues via _enqueue_comment()/_enqueue_dm()
AFTER LLM confirms in JSON. No double execution possible.

_apply_hard_escalation_rules: Python safety overrides applied after AgentService returns.
"""

import uuid as _uuid
from datetime import datetime, timezone
from langchain_core.tools import tool

from config import (
    ESCALATION_CATEGORIES,
    URGENT_KEYWORDS,
    VIP_LIFETIME_VALUE_THRESHOLD,
    MAX_COMMENT_REPLY_LENGTH,
    MAX_DM_REPLY_LENGTH,
)


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


@tool(
    name="reply_to_comment",
    description="Validate and prepare a comment reply for sending. USE THIS TOOL when you decide to auto-reply to a comment. Returns {validated: true, job_payload: {...}} on success, {validated: false, error: '...'} on failure. Python enqueues after you confirm in JSON. Max 2200 chars.",
)
def reply_to_comment(
    comment_id: str,
    reply_text: str,
    business_account_id: str,
    post_id: str,
) -> dict:
    """Validate and prepare a comment reply for sending.

    USE THIS TOOL when you decide to auto-reply to a comment.
    Returns the validated job payload — enqueueing is handled by Python.

    Args:
        comment_id: Instagram comment ID
        reply_text: The reply text you want to send (max 2200 chars)
        business_account_id: Business account UUID
        post_id: Instagram media ID

    Returns:
        {validated: true, job_payload: {...}} on success
        {validated: false, error: "reason"} on failure
    """
    if len(reply_text) > MAX_COMMENT_REPLY_LENGTH:
        return {"validated": False, "error": f"Reply exceeds {MAX_COMMENT_REPLY_LENGTH} chars ({len(reply_text)})"}
    if not comment_id:
        return {"validated": False, "error": "comment_id is required"}
    if not reply_text.strip():
        return {"validated": False, "error": "reply_text cannot be empty"}

    job_payload = {
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
        "source": "llm_reply_tool",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
        "last_error": None,
    }
    return {"validated": True, "job_payload": job_payload}


@tool(
    name="reply_to_dm",
    description="Validate and prepare a DM reply for sending. USE THIS TOOL when you decide to auto-reply to a DM. Returns {validated: true, job_payload: {...}} on success, {validated: false, error: '...'} on failure. Python enqueues after you confirm in JSON. Max 150 chars.",
)
def reply_to_dm(
    conversation_id: str,
    recipient_id: str,
    message_text: str,
    business_account_id: str,
) -> dict:
    """Validate and prepare a DM reply for sending.

    USE THIS TOOL when you decide to auto-reply to a DM.
    Returns the validated job payload — enqueueing is handled by Python.

    Args:
        conversation_id: Instagram conversation ID (PSID)
        recipient_id: Recipient's Instagram ID
        message_text: The DM text you want to send (max 150 chars)
        business_account_id: Business account UUID

    Returns:
        {validated: true, job_payload: {...}} on success
        {validated: false, error: "reason"} on failure
    """
    if len(message_text) > MAX_DM_REPLY_LENGTH:
        return {"validated": False, "error": f"DM exceeds {MAX_DM_REPLY_LENGTH} chars ({len(message_text)})"}
    if not conversation_id or not recipient_id:
        return {"validated": False, "error": "conversation_id and recipient_id are required"}
    if not message_text.strip():
        return {"validated": False, "error": "message_text cannot be empty"}

    job_payload = {
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
        "source": "llm_reply_tool",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "max_retries": 5,
        "last_error": None,
    }
    return {"validated": True, "job_payload": job_payload}


# ================================
# Python-only enqueue helpers
# Called by _handle_auto_reply() AFTER LLM confirms reply in JSON.
# DO NOT call these from a tool — use reply_to_comment/reply_to_dm instead.
# ================================
def _enqueue_comment(
    comment_id: str,
    reply_text: str,
    business_account_id: str,
    post_id: str,
) -> dict:
    """Python-only: enqueue comment reply into OutboundQueue.

    Called by _handle_auto_reply() AFTER LLM confirms reply via reply_to_comment_tool.
    Enqueues using the same idempotency key pattern as the LLM tool.
    """
    from services.outbound_queue import OutboundQueue

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


def _enqueue_dm(
    conversation_id: str,
    recipient_id: str,
    message_text: str,
    business_account_id: str,
) -> dict:
    """Python-only: enqueue DM reply into OutboundQueue.

    Called by _handle_auto_reply() AFTER LLM confirms reply via reply_to_dm_tool.
    Enqueues using the same idempotency key pattern as the LLM tool.
    """
    from services.outbound_queue import OutboundQueue

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


def _enqueue_from_job_payload(job_payload: dict) -> dict:
    """Enqueue a pre-built job payload returned by reply_to_comment/reply_to_dm tool.

    Called by _handle_auto_reply() when the LLM called the reply tool and the
    job_payload is already validated and confirmed in the LLM's JSON response.
    """
    from services.outbound_queue import OutboundQueue
    return OutboundQueue.enqueue(job_payload)


# ================================
# Tool Registry
# ================================
# reply_to_comment and reply_to_dm are @tool-decorated functions in supabase_tools.py
# (imported here from automation_tools for backward compat). They are LLM-callable tools
# that validate and return job payloads — Python enqueues via _enqueue_comment/_enqueue_dm.
# AUTOMATION_TOOLS kept for backward compat with tools/__init__.py imports.
# analyze_message_tool NOT included — caused recursion loop with bind_tools().
# ================================
AUTOMATION_TOOLS = [
    reply_to_comment,
    reply_to_dm,
]
