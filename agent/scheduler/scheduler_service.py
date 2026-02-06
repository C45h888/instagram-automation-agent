"""
Scheduler Service
==================
APScheduler wrapper for the engagement monitor and future scheduled jobs.

Features:
  - AsyncIOScheduler for non-blocking execution
  - max_instances=1 prevents overlapping runs
  - coalesce=True merges missed runs into one
  - misfire_grace_time prevents stale runs
  - Graceful shutdown (no blocking on container restart)
  - Runtime pause/resume/status via class methods
"""

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    logger,
    ENGAGEMENT_MONITOR_ENABLED,
    ENGAGEMENT_MONITOR_INTERVAL_MINUTES,
)
from scheduler.engagement_monitor import engagement_monitor_run


class SchedulerService:
    """Manages APScheduler lifecycle for the agent."""

    _scheduler: AsyncIOScheduler = None
    _last_run_stats: dict = {}
    _last_run_time: datetime = None
    _total_runs: int = 0

    @classmethod
    def init(cls):
        """Initialize and start the scheduler.

        Called during FastAPI lifespan startup.
        Jobs only added if their respective env var is enabled.
        """
        cls._scheduler = AsyncIOScheduler(
            job_defaults={
                "coalesce": True,        # Merge missed runs into one
                "max_instances": 1,      # Prevent overlapping runs
                "misfire_grace_time": 60,  # Skip if >60s late
            }
        )

        if ENGAGEMENT_MONITOR_ENABLED:
            cls._scheduler.add_job(
                cls._run_with_tracking,
                "interval",
                minutes=ENGAGEMENT_MONITOR_INTERVAL_MINUTES,
                id="engagement_monitor",
                name="Engagement Monitor",
            )
            logger.info(
                f"Engagement Monitor scheduled (every {ENGAGEMENT_MONITOR_INTERVAL_MINUTES} min)"
            )
        else:
            logger.info("Engagement Monitor disabled (ENGAGEMENT_MONITOR_ENABLED=false)")

        cls._scheduler.start()
        logger.info("Scheduler started")

    @classmethod
    async def _run_with_tracking(cls):
        """Wrapper that tracks last run time and stats."""
        cls._last_run_time = datetime.now(timezone.utc)
        cls._total_runs += 1
        await engagement_monitor_run()

    @classmethod
    def shutdown(cls):
        """Stop the scheduler gracefully.

        wait=False ensures we don't block on container shutdown.
        Called during FastAPI lifespan shutdown.
        """
        if cls._scheduler:
            cls._scheduler.shutdown(wait=False)
            cls._scheduler = None
            logger.info("Scheduler shut down")

    @classmethod
    def get_status(cls) -> dict:
        """Return scheduler status for the /engagement-monitor/status endpoint."""
        if not cls._scheduler:
            return {"running": False, "message": "Scheduler not initialized"}

        job = cls._scheduler.get_job("engagement_monitor")
        next_run = None
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

        return {
            "running": cls._scheduler.running,
            "engagement_monitor": {
                "enabled": ENGAGEMENT_MONITOR_ENABLED,
                "paused": job.next_run_time is None if job else True,
                "interval_minutes": ENGAGEMENT_MONITOR_INTERVAL_MINUTES,
                "next_run": next_run,
                "last_run": cls._last_run_time.isoformat() if cls._last_run_time else None,
                "total_runs": cls._total_runs,
            },
        }

    @classmethod
    def pause(cls) -> bool:
        """Pause the engagement monitor job. Returns True if successful."""
        if not cls._scheduler:
            return False
        try:
            cls._scheduler.pause_job("engagement_monitor")
            logger.info("Engagement Monitor paused")
            return True
        except Exception as e:
            logger.error(f"Failed to pause engagement monitor: {e}")
            return False

    @classmethod
    def resume(cls) -> bool:
        """Resume the engagement monitor job. Returns True if successful."""
        if not cls._scheduler:
            return False
        try:
            cls._scheduler.resume_job("engagement_monitor")
            logger.info("Engagement Monitor resumed")
            return True
        except Exception as e:
            logger.error(f"Failed to resume engagement monitor: {e}")
            return False

    @classmethod
    async def trigger_now(cls) -> bool:
        """Manually trigger an engagement monitor run (bypasses schedule).

        Runs immediately in the background.
        """
        try:
            await engagement_monitor_run()
            return True
        except Exception as e:
            logger.error(f"Manual trigger failed: {e}")
            return False
