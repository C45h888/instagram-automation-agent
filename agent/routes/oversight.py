"""
Oversight Brain Routes
======================
Chat-based explainability endpoints for the agent dashboard.

Endpoints:
  GET  /oversight/status  - Health check (public, no auth required)
  POST /oversight/chat    - Ask Oversight Brain (auth + rate limited to 20/min per-user)
"""

import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import limiter, OVERSIGHT_RATE_LIMIT, OVERSIGHT_STREAM_ENABLED
from services.oversight_brain import chat as oversight_chat, astream_chat as oversight_stream_chat
from routes.metrics import OVERSIGHT_CHAT_QUERIES, REQUEST_COUNT, REQUEST_LATENCY
from config import logger

oversight_router = APIRouter(prefix="/oversight")


# ================================
# Per-user Rate Limiting
# ================================
def _oversight_rate_key(request: Request) -> str:
    """Per-user rate limit key: X-User-ID header -> fallback to IP."""
    user_id = request.headers.get("X-User-ID", "")
    if user_id:
        return f"oversight_user:{user_id}"
    return request.client.host if request.client else "unknown"


# ================================
# Request Model
# ================================
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=2000, description="Question about an agent decision")
    business_account_id: str = Field(..., min_length=1, description="Business account UUID for scoping")
    stream: bool = Field(default=False, description="If true, return SSE stream")
    chat_history: Optional[list] = Field(default=None, description="Prior turns [{role, content}]")
    user_id: str = Field(default="dashboard-user", description="User ID for audit log")


# ================================
# Routes
# ================================
@oversight_router.get("/status")
async def get_status():
    """Public health check for Oversight Brain. No auth required."""
    return {"status": "operational", "endpoint": "/oversight/chat"}


@oversight_router.post("/chat")
@limiter.limit(OVERSIGHT_RATE_LIMIT, key_func=_oversight_rate_key)
async def chat_endpoint(request_body: ChatRequest, request: Request):
    """Ask the Oversight Brain to explain an agent decision.

    Supports both blocking JSON and SSE streaming responses.
    Set stream=true for token-by-token streaming.
    Rate limited to 20/min per user (X-User-ID header).
    Responses cached 5 minutes for identical questions without chat_history.

    Example request (blocking):
        {"question": "Why was comment abc123 escalated?", "business_account_id": "uuid-here", "user_id": "dashboard"}

    Example request (streaming):
        {"question": "Why was comment abc123 escalated?", "business_account_id": "uuid-here", "stream": true, "user_id": "dashboard"}

    Example response:
        {
            "answer": "Comment abc123 was escalated because...",
            "sources": [{"type": "audit_log", "id": "...", "excerpt": "..."}],
            "tools_used": ["get_audit_log_entries"],
            "latency_ms": 1234,
            "request_id": "uuid"
        }
    """
    endpoint = "/oversight/chat"
    request_id = getattr(request.state, "request_id", "unknown")
    start = time.time()

    logger.info(f"[{request_id}] Oversight chat: {request_body.question[:80]} (stream={request_body.stream})")
    REQUEST_COUNT.labels(endpoint=endpoint, status="started").inc()
    OVERSIGHT_CHAT_QUERIES.labels(status="started").inc()

    # Streaming path
    if request_body.stream and OVERSIGHT_STREAM_ENABLED:
        OVERSIGHT_CHAT_QUERIES.labels(status="stream_started").inc()
        return StreamingResponse(
            oversight_stream_chat(
                question=request_body.question,
                business_account_id=request_body.business_account_id,
                chat_history=request_body.chat_history,
                user_id=request_body.user_id,
                request_id=request_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Request-ID": request_id,
            },
        )

    # Blocking path (existing)
    result = await oversight_chat(
        question=request_body.question,
        business_account_id=request_body.business_account_id,
        chat_history=request_body.chat_history,
        user_id=request_body.user_id,
        request_id=request_id,
    )

    status = "error" if "error" in result else "success"
    REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start)
    OVERSIGHT_CHAT_QUERIES.labels(status=status).inc()

    return result
