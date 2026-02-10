"""
API Key Middleware
==================
Enforces X-API-Key authentication on all routes except explicitly public ones.
FastAPI/Starlette middleware replaces the old Flask before_request hook.
"""

import os
from fastapi import Request
from fastapi.responses import JSONResponse

# Paths that skip authentication (opt-in allowlist)
# Note: Webhook endpoints use HMAC-SHA256 signature verification instead of API key
PUBLIC_PATHS = {
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/webhook/comment",            # Verified via X-Hub-Signature-256
    "/webhook/dm",                 # Verified via X-Hub-Signature-256
    "/engagement-monitor/status",  # Read-only scheduler status
    "/content-scheduler/status",   # Read-only scheduler status
    "/webhook/order-created",      # Verified via X-Hub-Signature-256
    "/sales-attribution/status",   # Read-only scheduler status
    "/ugc-collection/status",      # Read-only scheduler status
    "/analytics-reports/status",   # Read-only scheduler status
    "/oversight/status",           # Read-only Oversight Brain health check
}


async def api_key_middleware(request: Request, call_next):
    """Check X-API-Key on protected routes."""
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    api_key = os.getenv("AGENT_API_KEY", "")

    # If no key configured, skip auth (dev mode)
    if not api_key:
        return await call_next(request)

    provided = request.headers.get("X-API-Key", "")
    if provided != api_key:
        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "message": "Invalid or missing X-API-Key header"
            }
        )

    return await call_next(request)
