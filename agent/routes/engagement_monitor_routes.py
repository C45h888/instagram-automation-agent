"""
Engagement Monitor Routes
==========================
HTTP endpoints for monitoring and controlling the engagement monitor scheduler.

Endpoints:
  GET  /engagement-monitor/status  - Scheduler status, last/next run, stats (public)
  POST /engagement-monitor/trigger - Manually trigger a cycle (auth required)
  POST /engagement-monitor/pause   - Pause the scheduler (auth required)
  POST /engagement-monitor/resume  - Resume the scheduler (auth required)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import logger
from scheduler.scheduler_service import SchedulerService
from scheduler.dedup_service import DedupService

engagement_monitor_router = APIRouter(
    prefix="/engagement-monitor",
    tags=["engagement-monitor"],
)


@engagement_monitor_router.get("/status")
async def get_monitor_status():
    """Return scheduler status, last/next run time, and dedup stats.

    Public endpoint (no auth required) — read-only.
    """
    status = SchedulerService.get_status()
    status["dedup_cache_size"] = DedupService.get_processed_count()
    return status


@engagement_monitor_router.post("/trigger")
async def trigger_monitor(request: Request):
    """Manually trigger an engagement monitor cycle.

    Bypasses the schedule and runs immediately.
    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual engagement monitor trigger requested")

    success = await SchedulerService.trigger_now()

    if success:
        return {"triggered": True, "message": "Engagement monitor cycle completed", "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"triggered": False, "message": "Trigger failed — check logs", "request_id": request_id},
        )


@engagement_monitor_router.post("/pause")
async def pause_monitor(request: Request):
    """Pause the engagement monitor scheduler.

    The scheduler stops running cycles until resumed.
    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.pause()

    if success:
        logger.info(f"[{request_id}] Engagement monitor paused")
        return {"paused": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"paused": False, "message": "Failed to pause — scheduler may not be running", "request_id": request_id},
        )


@engagement_monitor_router.post("/resume")
async def resume_monitor(request: Request):
    """Resume the engagement monitor scheduler.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.resume()

    if success:
        logger.info(f"[{request_id}] Engagement monitor resumed")
        return {"resumed": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"resumed": False, "message": "Failed to resume — scheduler may not be running", "request_id": request_id},
        )
