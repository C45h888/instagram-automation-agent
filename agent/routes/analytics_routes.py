"""
Analytics Reports Routes
=========================
HTTP endpoints for monitoring and controlling the analytics reports scheduler.

Endpoints:
  GET  /analytics-reports/status          - Scheduler status (public)
  POST /analytics-reports/trigger-daily   - Trigger daily report (auth required)
  POST /analytics-reports/trigger-weekly  - Trigger weekly report (auth required)
  POST /analytics-reports/pause           - Pause analytics jobs (auth required)
  POST /analytics-reports/resume          - Resume analytics jobs (auth required)
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import logger
from scheduler.scheduler_service import SchedulerService

analytics_router = APIRouter(
    prefix="/analytics-reports",
    tags=["analytics-reports"],
)


@analytics_router.get("/status")
async def get_analytics_status():
    """Return analytics reports scheduler status.

    Public endpoint (no auth required) — read-only.
    """
    status = SchedulerService.get_status()
    return {
        "running": status.get("running", False),
        "analytics_daily": status.get("analytics_daily", {}),
        "analytics_weekly": status.get("analytics_weekly", {}),
    }


@analytics_router.post("/trigger-daily")
async def trigger_daily_report(request: Request):
    """Manually trigger a daily analytics report.

    Bypasses the schedule and runs immediately.
    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual daily analytics report trigger requested")

    success = await SchedulerService.trigger_now(job_prefix="analytics_daily")

    if success:
        return {
            "triggered": True,
            "report_type": "daily",
            "message": "Daily analytics report cycle completed",
            "request_id": request_id,
        }
    else:
        return JSONResponse(
            status_code=500,
            content={
                "triggered": False,
                "message": "Trigger failed — check logs",
                "request_id": request_id,
            },
        )


@analytics_router.post("/trigger-weekly")
async def trigger_weekly_report(request: Request):
    """Manually trigger a weekly analytics report.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Manual weekly analytics report trigger requested")

    success = await SchedulerService.trigger_now(job_prefix="analytics_weekly")

    if success:
        return {
            "triggered": True,
            "report_type": "weekly",
            "message": "Weekly analytics report cycle completed",
            "request_id": request_id,
        }
    else:
        return JSONResponse(
            status_code=500,
            content={
                "triggered": False,
                "message": "Trigger failed — check logs",
                "request_id": request_id,
            },
        )


@analytics_router.post("/pause")
async def pause_analytics(request: Request):
    """Pause all analytics report jobs.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")

    daily_ok = SchedulerService.pause(job_prefix="analytics_daily")
    weekly_ok = SchedulerService.pause(job_prefix="analytics_weekly")

    if daily_ok or weekly_ok:
        logger.info(f"[{request_id}] Analytics reports paused")
        return {"paused": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={
                "paused": False,
                "message": "Failed to pause — scheduler may not be running",
                "request_id": request_id,
            },
        )


@analytics_router.post("/resume")
async def resume_analytics(request: Request):
    """Resume all analytics report jobs.

    Auth required (X-API-Key).
    """
    request_id = getattr(request.state, "request_id", "unknown")

    daily_ok = SchedulerService.resume(job_prefix="analytics_daily")
    weekly_ok = SchedulerService.resume(job_prefix="analytics_weekly")

    if daily_ok or weekly_ok:
        logger.info(f"[{request_id}] Analytics reports resumed")
        return {"resumed": True, "request_id": request_id}
    else:
        return JSONResponse(
            status_code=500,
            content={
                "resumed": False,
                "message": "Failed to resume — scheduler may not be running",
                "request_id": request_id,
            },
        )
