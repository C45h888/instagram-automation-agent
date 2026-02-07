"""
UGC Collection Routes
======================
HTTP endpoints for monitoring and controlling the UGC discovery scheduler.

Endpoints:
  GET  /ugc-collection/status  - Scheduler status, last/next run, stats (public)
  POST /ugc-collection/trigger - Manually trigger a cycle (auth required)
  POST /ugc-collection/pause   - Pause the scheduler (auth required)
  POST /ugc-collection/resume  - Resume the scheduler (auth required)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import logger
from scheduler.scheduler_service import SchedulerService
from scheduler.ugc_dedup_service import UgcDedupService

ugc_collection_router = APIRouter(
    prefix="/ugc-collection",
    tags=["ugc-collection"],
)


@ugc_collection_router.get("/status")
async def get_ugc_collection_status():
    """Return scheduler status, last/next run time, and dedup stats.

    Public endpoint (no auth required) — read-only.
    """
    status = SchedulerService.get_status()
    return {
        "running": status.get("running", False),
        "ugc_collection": status.get("ugc_collection", {}),
        "dedup_cache_size": UgcDedupService.get_processed_count(),
    }


@ugc_collection_router.post("/trigger")
async def trigger_ugc_collection(request: Request):
    """Manually trigger a UGC discovery cycle."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual UGC discovery trigger requested")

    try:
        success = await SchedulerService.trigger_now(job_prefix="ugc_collection")
        if success:
            return {
                "triggered": True,
                "message": "UGC discovery cycle completed",
                "request_id": request_id,
            }
        return JSONResponse(
            status_code=500,
            content={
                "triggered": False,
                "message": "Trigger failed — check logs",
                "request_id": request_id,
            },
        )
    except Exception as e:
        logger.error(f"[{request_id}] UGC discovery trigger error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "triggered": False,
                "message": f"Trigger error: {str(e)}",
                "request_id": request_id,
            },
        )


@ugc_collection_router.post("/pause")
async def pause_ugc_collection(request: Request):
    """Pause the UGC collection scheduler."""
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.pause(job_prefix="ugc_collection")

    if success:
        logger.info(f"[{request_id}] UGC collection paused")
        return {"paused": True, "request_id": request_id}
    return JSONResponse(
        status_code=500,
        content={
            "paused": False,
            "message": "Failed to pause — scheduler may not be running",
            "request_id": request_id,
        },
    )


@ugc_collection_router.post("/resume")
async def resume_ugc_collection(request: Request):
    """Resume the UGC collection scheduler."""
    request_id = getattr(request.state, "request_id", "unknown")
    success = SchedulerService.resume(job_prefix="ugc_collection")

    if success:
        logger.info(f"[{request_id}] UGC collection resumed")
        return {"resumed": True, "request_id": request_id}
    return JSONResponse(
        status_code=500,
        content={
            "resumed": False,
            "message": "Failed to resume — scheduler may not be running",
            "request_id": request_id,
        },
    )
