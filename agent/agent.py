"""
LangChain Oversight Brain Agent
================================
Central approval and automation authority for Instagram workflows.
Receives proposed actions (comment replies, DM replies, posts),
analyzes them using NVIDIA Nemotron 4 8B via Ollama,
and returns approve/reject/modify decisions.

Also runs the engagement monitor, content scheduler, and weekly attribution
learning for proactive automation.

Endpoints:
  GET  /health                       - Health check (Ollama + Supabase status)
  GET  /metrics                      - Prometheus metrics
  POST /approve/comment-reply        - Approve/reject comment reply
  POST /approve/dm-reply             - Approve/reject DM reply (with escalation)
  POST /approve/post                 - Approve/reject post caption
  GET  /engagement-monitor/status    - Engagement monitor status
  POST /engagement-monitor/trigger   - Manual trigger
  POST /engagement-monitor/pause     - Pause engagement monitor
  POST /engagement-monitor/resume    - Resume engagement monitor
  GET  /content-scheduler/status     - Content scheduler status
  POST /content-scheduler/trigger    - Manual trigger
  POST /content-scheduler/pause      - Pause content scheduler
  POST /content-scheduler/resume     - Resume content scheduler
  POST /webhook/order-created        - Sales attribution webhook
  GET  /sales-attribution/status     - Weekly learning status
  POST /sales-attribution/trigger    - Manual trigger learning
  POST /sales-attribution/pause      - Pause weekly learning
  POST /sales-attribution/resume     - Resume weekly learning
  GET  /ugc-collection/status        - UGC collection status
  POST /ugc-collection/trigger       - Manual trigger UGC discovery
  POST /ugc-collection/pause         - Pause UGC collection
  POST /ugc-collection/resume        - Resume UGC collection
"""

import os
import uuid as uuid_mod
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import logger, OLLAMA_HOST, OLLAMA_MODEL, ENGAGEMENT_MONITOR_ENABLED, CONTENT_SCHEDULER_ENABLED, SALES_ATTRIBUTION_ENABLED, WEEKLY_LEARNING_ENABLED, UGC_COLLECTION_ENABLED
from middleware import api_key_middleware
from services.prompt_service import PromptService
from scheduler.scheduler_service import SchedulerService

# Import route routers
from routes import (
    health_router,
    approve_comment_router,
    approve_dm_router,
    approve_post_router,
    metrics_router,
    webhook_comment_router,
    webhook_dm_router,
    log_outcome_router,
    engagement_monitor_router,
    content_scheduler_router,
    webhook_order_router,
    attribution_router,
    ugc_collection_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("=" * 60)
    logger.info("Oversight Brain Agent starting up")
    logger.info(f"  Ollama Host: {OLLAMA_HOST}")
    logger.info(f"  Model: {OLLAMA_MODEL}")
    logger.info(f"  Rate Limit: 60/min global, 30/min on /approve/*, 10/min on /webhook/*")
    logger.info(f"  Approval Endpoints: /approve/comment-reply, /approve/dm-reply, /approve/post")
    logger.info(f"  Webhook Endpoints: /webhook/comment, /webhook/dm, /webhook/order-created, /log-outcome")
    logger.info(f"  Scheduler: /engagement-monitor/*, /content-scheduler/*, /sales-attribution/*")
    logger.info(f"  Utility: /health, /metrics")
    logger.info("=" * 60)
    # Load prompts from DB (falls back to static defaults)
    PromptService.load()
    # Start schedulers (engagement monitor + content scheduler)
    SchedulerService.init()
    logger.info(f"  Engagement Monitor: {'enabled' if ENGAGEMENT_MONITOR_ENABLED else 'disabled'}")
    logger.info(f"  Content Scheduler: {'enabled' if CONTENT_SCHEDULER_ENABLED else 'disabled'}")
    logger.info(f"  Sales Attribution: {'enabled' if SALES_ATTRIBUTION_ENABLED else 'disabled'}")
    logger.info(f"  Weekly Learning: {'enabled' if WEEKLY_LEARNING_ENABLED else 'disabled'}")
    logger.info(f"  UGC Collection: {'enabled' if UGC_COLLECTION_ENABLED else 'disabled'}")
    yield
    # Shutdown cleanup
    SchedulerService.shutdown()


app = FastAPI(
    title="Oversight Brain Agent",
    description="Central approval authority for Instagram automation workflows",
    version="2.0.0",
    lifespan=lifespan,
)

# --- Rate limiting (Redis-backed for distributed state) ---
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = os.getenv("REDIS_PORT", "6379")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=f"redis://{redis_host}:{redis_port}",
    default_limits=["60/minute"],
)
app.state.limiter = limiter

# --- Middleware: Request ID tracing ---
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Generate unique request ID for tracing through logs and audit."""
    request_id = str(uuid_mod.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# --- Middleware: API key auth ---
app.middleware("http")(api_key_middleware)

# --- Register routers ---
app.include_router(health_router)
app.include_router(approve_comment_router)
app.include_router(approve_dm_router)
app.include_router(approve_post_router)
app.include_router(metrics_router)
app.include_router(webhook_comment_router)
app.include_router(webhook_dm_router)
app.include_router(log_outcome_router)
app.include_router(engagement_monitor_router)
app.include_router(content_scheduler_router)
app.include_router(webhook_order_router)
app.include_router(attribution_router)
app.include_router(ugc_collection_router)


# ================================
# Global Error Handlers
# ================================
def _get_request_id(request: Request) -> str:
    """Get request ID from state or generate new one."""
    return getattr(request.state, "request_id", str(uuid_mod.uuid4()))


@app.exception_handler(RequestValidationError)
async def validation_exception(request: Request, exc: RequestValidationError):
    """Override FastAPI's default 422 to return 400 for N8N backward compatibility."""
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=400,
        content={
            "error": "validation_error",
            "message": f"Invalid request payload: {exc.errors()}",
            "request_id": request_id,
        }
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded):
    request_id = _get_request_id(request)
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "message": "Too many requests. Please slow down.",
            "request_id": request_id,
        }
    )


@app.exception_handler(Exception)
async def catch_all_exception(request: Request, exc: Exception):
    """Catch-all handler — every unhandled exception returns structured JSON."""
    request_id = _get_request_id(request)
    logger.error(f"Unhandled exception [request_id={request_id}]: {type(exc).__name__}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "error_type": type(exc).__name__,
            "message": "An unexpected error occurred. Check agent logs.",
            "request_id": request_id,
        }
    )


# Dev server fallback
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("FLASK_PORT", 3002))
    uvicorn.run(app, host="0.0.0.0", port=port)
