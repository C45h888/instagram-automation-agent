"""
Oversight Brain Routes
======================
Chat-based explainability endpoints for the agent dashboard.

Endpoints:
  GET  /oversight/status  - Health check (public, no auth required)
  POST /oversight/chat    - Ask Oversight Brain (auth + rate limited to 10/min)
"""

import time
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from config import limiter, OVERSIGHT_RATE_LIMIT
from services.oversight_brain import chat as oversight_chat
from routes.metrics import OVERSIGHT_CHAT_QUERIES, REQUEST_COUNT, REQUEST_LATENCY
from config import logger

oversight_router = APIRouter(prefix="/oversight")


# ================================
# Request Model
# ================================
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=500, description="Question about an agent decision")
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
@limiter.limit(OVERSIGHT_RATE_LIMIT)
async def chat_endpoint(request_body: ChatRequest, request: Request):
    """Ask the Oversight Brain to explain an agent decision.

    Requires X-API-Key header.
    Rate limited to 10/min per IP (Oversight LLM calls are expensive).
    Responses cached 5 minutes for identical questions without chat_history.

    Example request:
        {"question": "Why was comment abc123 escalated?", "user_id": "dashboard"}

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

    logger.info(f"[{request_id}] Oversight chat: {request_body.question[:80]}")
    REQUEST_COUNT.labels(endpoint=endpoint, status="started").inc()
    OVERSIGHT_CHAT_QUERIES.labels(status="started").inc()

    result = await oversight_chat(
        question=request_body.question,
        chat_history=request_body.chat_history,
        user_id=request_body.user_id,
        request_id=request_id,
    )

    status = "error" if "error" in result else "success"
    REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(time.time() - start)
    OVERSIGHT_CHAT_QUERIES.labels(status=status).inc()

    return result
