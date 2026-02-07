"""
Sales Attribution Routes
=========================
HTTP endpoints for monitoring and controlling the weekly attribution learning.

Endpoints:
  GET  /sales-attribution/status  - Scheduler status, next run time (public)
  POST /sales-attribution/trigger - Manually trigger a learning cycle (auth required)
  POST /sales-attribution/pause   - Pause weekly learning job (auth required)
  POST /sales-attribution/resume  - Resume weekly learning job (auth required)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import logger
from scheduler.scheduler_service import SchedulerService

attribution_router = APIRouter(
    prefix="/sales-attribution",
    tags=["sales-attribution"],
)


@attribution_router.get("/status")
async def get_attribution_status():
    """Return weekly learning scheduler status.

    Public endpoint (no auth required) — read-only.
    """
    status = SchedulerService.get_status()
    return {
        "running": status.get("running", False),
        "weekly_learning": status.get("weekly_learning", {}),
    }


@attribution_router.post("/trigger")
async def trigger_learning(request: Request):
    """Manually trigger a weekly learning cycle.

    Bypasses the schedule and runs immediately.
    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual weekly learning trigger requested")

    success = await SchedulerService.trigger_now(job_prefix="weekly_learning")

    if success:
        return {"triggered": True, "message": "Weekly learning cycle completed", "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"triggered": False, "message": "Trigger failed — check logs", "request_id": request_id},
        )


@attribution_router.post("/pause")
async def pause_learning(request: Request):
    """Pause weekly learning job.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.pause(job_prefix="weekly_learning")

    if success:
        logger.info(f"[{request_id}] Weekly learning paused")
        return {"paused": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"paused": False, "message": "Failed to pause — scheduler may not be running", "request_id": request_id},
        )


@attribution_router.post("/resume")
async def resume_learning(request: Request):
    """Resume weekly learning job.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.resume(job_prefix="weekly_learning")

    if success:
        logger.info(f"[{request_id}] Weekly learning resumed")
        return {"resumed": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"resumed": False, "message": "Failed to resume — scheduler may not be running", "request_id": request_id},
        )
