"""
Content Scheduler Routes
=========================
HTTP endpoints for monitoring and controlling the content scheduler.

Endpoints:
  GET  /content-scheduler/status  - Scheduler status, next run times (public)
  POST /content-scheduler/trigger - Manually trigger a cycle (auth required)
  POST /content-scheduler/pause   - Pause all content scheduler jobs (auth required)
  POST /content-scheduler/resume  - Resume all content scheduler jobs (auth required)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import logger
from scheduler.scheduler_service import SchedulerService

content_scheduler_router = APIRouter(
    prefix="/content-scheduler",
    tags=["content-scheduler"],
)


@content_scheduler_router.get("/status")
async def get_scheduler_status():
    """Return content scheduler status and next run times.

    Public endpoint (no auth required) — read-only.
    """
    status = SchedulerService.get_status()
    return {
        "running": status.get("running", False),
        "content_scheduler": status.get("content_scheduler", {}),
    }


@content_scheduler_router.post("/trigger")
async def trigger_scheduler(request: Request):
    """Manually trigger a content scheduler cycle.

    Bypasses the schedule and runs immediately.
    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual content scheduler trigger requested")

    success = await SchedulerService.trigger_now(job_prefix="content_scheduler")

    if success:
        return {"triggered": True, "message": "Content scheduler cycle completed", "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"triggered": False, "message": "Trigger failed — check logs", "request_id": request_id},
        )


@content_scheduler_router.post("/pause")
async def pause_scheduler(request: Request):
    """Pause all content scheduler jobs.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.pause(job_prefix="content_scheduler")

    if success:
        logger.info(f"[{request_id}] Content scheduler paused")
        return {"paused": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"paused": False, "message": "Failed to pause — scheduler may not be running", "request_id": request_id},
        )


@content_scheduler_router.post("/resume")
async def resume_scheduler(request: Request):
    """Resume all content scheduler jobs.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.resume(job_prefix="content_scheduler")

    if success:
        logger.info(f"[{request_id}] Content scheduler resumed")
        return {"resumed": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={"resumed": False, "message": "Failed to resume — scheduler may not be running", "request_id": request_id},
        )
