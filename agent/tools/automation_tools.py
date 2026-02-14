"""
LangChain Automation Tools - Customer Service
==============================================
Tools for analyzing Instagram messages and executing replies.
Replaces N8N customer service workflow logic.

Tools:
  - analyze_message: Classify message, determine sentiment/priority, generate reply
  - reply_to_comment: Execute comment reply via backend proxy
  - reply_to_dm: Execute DM reply via backend proxy
"""

import asyncio
import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    logger,
    BACKEND_REPLY_COMMENT_ENDPOINT,
    BACKEND_REPLY_DM_ENDPOINT,
    BACKEND_TIMEOUT_SECONDS,
    ESCALATION_CATEGORIES,
    URGENT_KEYWORDS,
    VIP_LIFETIME_VALUE_THRESHOLD,
    MAX_COMMENT_REPLY_LENGTH,
    backend_headers,
)


# ================================
# Input Schemas
# ================================
class AnalyzeMessageInput(BaseModel):
    message_text: str = Field(description="The message text to analyze")
    message_type: str = Field(description="'comment' or 'dm'")
    sender_username: str = Field(description="Sender's username")
    account_context: dict = Field(default_factory=dict, description="Brand account info")
    post_context: Optional[dict] = Field(default=None, description="Post context if comment")
    dm_history: Optional[list] = Field(default=None, description="Recent DM history")
    customer_lifetime_value: float = Field(default=0.0, description="Customer LTV")


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
# Singleton Agent Service (lazy import to avoid circular)
# ================================
_agent_service = None


def _get_agent_service():
    """Lazy import to avoid circular dependency."""
    global _agent_service
    if _agent_service is None:
        from services.agent_service import AgentService
        _agent_service = AgentService()
    return _agent_service


# ================================
# analyze_message Implementation
# ================================
def _analyze_message(
    message_text: str,
    message_type: str,
    sender_username: str,
    account_context: dict,
    post_context: Optional[dict] = None,
    dm_history: Optional[list] = None,
    customer_lifetime_value: float = 0.0,
) -> dict:
    """Analyze incoming Instagram message - classification, sentiment, reply generation.

    Flow:
    1. Build prompt with context
    2. Invoke LLM for analysis
    3. Apply hard escalation rules
    4. Return structured result
    """
    from services.prompt_service import PromptService

    # Format DM history for context
    dm_history_summary = "No prior messages"
    if dm_history:
        lines = []
        for msg in dm_history[:5]:
            direction = msg.get("direction", "?")
            text = msg.get("message_text", "")[:80]
            lines.append(f"[{direction}] {text}")
        dm_history_summary = "\n".join(lines)

    # Build prompt
    prompt = PromptService.get("analyze_message").format(
        message_text=message_text[:500],
        message_type=message_type,
        sender_username=sender_username,
        account_username=account_context.get("username", "unknown"),
        account_type=account_context.get("account_type", "business"),
        post_caption=(post_context.get("caption", "N/A")[:200] if post_context else "N/A"),
        post_engagement=(post_context.get("engagement_rate", 0) if post_context else 0),
        dm_history_summary=dm_history_summary,
        customer_value=customer_lifetime_value,
    )

    # Use agent service for LLM call
    agent = _get_agent_service()

    # Run async call in sync context
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an async context, use run_coroutine_threadsafe
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(agent.analyze_async(prompt), loop)
        result = future.result(timeout=30)
    except RuntimeError:
        # No running loop, create a new one
        result = asyncio.run(agent.analyze_async(prompt))

    # Apply hard escalation rules on top of LLM decision
    result = _apply_hard_escalation_rules(result, message_text, customer_lifetime_value)

    return result


def _apply_hard_escalation_rules(result: dict, message_text: str, customer_value: float) -> dict:
    """Override LLM decision with hard rules for VIP, urgent, complaints."""
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
        result["escalation_reason"] = result.get("escalation_reason") or f"Negative {category} requires human"

    # Rule 4: Long complex message -> escalate
    if len(message_text) > 300 and "?" in message_text:
        result["needs_human"] = True
        result["escalation_reason"] = result.get("escalation_reason") or "Complex multi-part question"

    return result


# ================================
# reply_to_comment Implementation (with resilience)
# ================================
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_reply_comment(payload: dict) -> dict:
    """Backend call with retry logic."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_REPLY_COMMENT_ENDPOINT,
            json=payload,
            headers=backend_headers()
        )
        response.raise_for_status()
        return response.json()


def _reply_to_comment(
    comment_id: str,
    reply_text: str,
    business_account_id: str,
    post_id: str,
) -> dict:
    """Execute comment reply via backend proxy with timeout and retry."""
    # Validate reply length against Instagram's limit
    if len(reply_text) > MAX_COMMENT_REPLY_LENGTH:
        return {
            "success": False,
            "error": "reply_too_long",
            "message": f"Reply exceeds {MAX_COMMENT_REPLY_LENGTH} chars ({len(reply_text)})"
        }

    payload = {
        "comment_id": comment_id,
        "reply_text": reply_text,
        "business_account_id": business_account_id,
        "post_id": post_id,
    }

    try:
        ig_response = _call_backend_reply_comment(payload)
        return {
            "success": True,
            "execution_id": ig_response.get("id", "unknown"),
            "instagram_response": ig_response,
        }
    except httpx.TimeoutException:
        logger.error(f"Backend timeout for comment {comment_id}")
        return {"success": False, "error": "timeout", "message": "Backend timed out"}
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error: {e.response.status_code}")
        return {"success": False, "error": "backend_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(f"Reply failed: {e}")
        return {"success": False, "error": str(type(e).__name__), "message": str(e)}


# ================================
# reply_to_dm Implementation (with resilience)
# ================================
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_reply_dm(payload: dict) -> dict:
    """Backend call with retry logic."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_REPLY_DM_ENDPOINT,
            json=payload,
            headers=backend_headers()
        )
        response.raise_for_status()
        return response.json()


def _reply_to_dm(
    conversation_id: str,
    recipient_id: str,
    message_text: str,
    business_account_id: str,
) -> dict:
    """Execute DM reply via backend proxy with timeout and retry."""
    # Validate message length
    if len(message_text) > 150:
        return {
            "success": False,
            "error": "message_too_long",
            "message": f"DM exceeds 150 chars ({len(message_text)})"
        }

    payload = {
        "conversation_id": conversation_id,
        "recipient_id": recipient_id,
        "message_text": message_text,
        "business_account_id": business_account_id,
    }

    try:
        ig_response = _call_backend_reply_dm(payload)
        return {
            "success": True,
            "execution_id": ig_response.get("id", "unknown"),
            "instagram_response": ig_response,
        }
    except httpx.TimeoutException:
        logger.error(f"Backend timeout for DM to {recipient_id}")
        return {"success": False, "error": "timeout", "message": "Backend timed out"}
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error: {e.response.status_code}")
        return {"success": False, "error": "backend_error", "status_code": e.response.status_code}
    except Exception as e:
        logger.error(f"DM failed: {e}")
        return {"success": False, "error": str(type(e).__name__), "message": str(e)}


# ================================
# Tool Definitions
# ================================
analyze_message_tool = StructuredTool.from_function(
    func=_analyze_message,
    name="analyze_message",
    description="Analyze an Instagram message (comment or DM). Returns category, sentiment, priority, suggested reply. Use before deciding to reply or escalate.",
    args_schema=AnalyzeMessageInput,
)

reply_to_comment_tool = StructuredTool.from_function(
    func=_reply_to_comment,
    name="reply_to_comment",
    description="Send a reply to an Instagram comment via backend proxy. Max 2200 chars. Use after analyze_message confirms auto-reply.",
    args_schema=ReplyToCommentInput,
)

reply_to_dm_tool = StructuredTool.from_function(
    func=_reply_to_dm,
    name="reply_to_dm",
    description="Send a DM reply via backend proxy. Max 150 chars. Use after analyze_message confirms auto-reply and 24h window is valid.",
    args_schema=ReplyToDMInput,
)


# ================================
# Tool Registry
# ================================
AUTOMATION_TOOLS = [
    analyze_message_tool,
    reply_to_comment_tool,
    reply_to_dm_tool,
]
