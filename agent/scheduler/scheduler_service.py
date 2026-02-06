"""
Scheduler Service
==================
APScheduler wrapper for the engagement monitor and content scheduler.

Features:
  - AsyncIOScheduler for non-blocking execution
  - max_instances=1 prevents overlapping runs
  - coalesce=True merges missed runs into one
  - misfire_grace_time prevents stale runs
  - Graceful shutdown (no blocking on container restart)
  - Runtime pause/resume/status/trigger via class methods
  - Generic job tracking (supports multiple job types)
"""

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    logger,
    ENGAGEMENT_MONITOR_ENABLED,
    ENGAGEMENT_MONITOR_INTERVAL_MINUTES,
    CONTENT_SCHEDULER_ENABLED,
    CONTENT_SCHEDULER_TIMES,
)
from scheduler.engagement_monitor import engagement_monitor_run
from scheduler.content_scheduler import content_scheduler_run


class SchedulerService:
    """Manages APScheduler lifecycle for the agent."""

    _scheduler: AsyncIOScheduler = None
    _job_stats: dict = {}  # {job_prefix: {"last_run_time": datetime, "total_runs": int}}

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

        # --- Engagement Monitor (interval-based) ---
        if ENGAGEMENT_MONITOR_ENABLED:
            cls._scheduler.add_job(
                cls._make_tracked_runner("engagement_monitor", engagement_monitor_run),
                "interval",
                minutes=ENGAGEMENT_MONITOR_INTERVAL_MINUTES,
                id="engagement_monitor",
                name="Engagement Monitor",
            )
            cls._job_stats["engagement_monitor"] = {"last_run_time": None, "total_runs": 0}
            logger.info(
                f"Engagement Monitor scheduled (every {ENGAGEMENT_MONITOR_INTERVAL_MINUTES} min)"
            )
        else:
            logger.info("Engagement Monitor disabled (ENGAGEMENT_MONITOR_ENABLED=false)")

        # --- Content Scheduler (cron-based, multiple times) ---
        if CONTENT_SCHEDULER_ENABLED:
            for time_str in CONTENT_SCHEDULER_TIMES:
                time_str = time_str.strip()
                try:
                    hour, minute = map(int, time_str.split(":"))
                except ValueError:
                    logger.warning(f"Invalid CONTENT_SCHEDULER_TIMES entry: '{time_str}' — skipping")
                    continue

                job_id = f"content_scheduler_{hour:02d}{minute:02d}"
                cls._scheduler.add_job(
                    cls._make_tracked_runner("content_scheduler", content_scheduler_run),
                    "cron",
                    hour=hour,
                    minute=minute,
                    id=job_id,
                    name=f"Content Scheduler ({time_str})",
                )

            cls._job_stats["content_scheduler"] = {"last_run_time": None, "total_runs": 0}
            logger.info(
                f"Content Scheduler scheduled at {', '.join(t.strip() for t in CONTENT_SCHEDULER_TIMES)}"
            )
        else:
            logger.info("Content Scheduler disabled (CONTENT_SCHEDULER_ENABLED=false)")

        cls._scheduler.start()
        logger.info("Scheduler started")

    @classmethod
    def _make_tracked_runner(cls, job_prefix: str, func):
        """Create a wrapper that tracks last run time and total runs."""
        async def runner():
            stats = cls._job_stats.get(job_prefix, {"last_run_time": None, "total_runs": 0})
            stats["last_run_time"] = datetime.now(timezone.utc)
            stats["total_runs"] += 1
            cls._job_stats[job_prefix] = stats
            await func()
        return runner

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
        """Return scheduler status for all registered jobs."""
        if not cls._scheduler:
            return {"running": False, "message": "Scheduler not initialized"}

        result = {"running": cls._scheduler.running}

        # Engagement monitor
        result["engagement_monitor"] = cls._get_job_status(
            "engagement_monitor",
            ENGAGEMENT_MONITOR_ENABLED,
            {"interval_minutes": ENGAGEMENT_MONITOR_INTERVAL_MINUTES},
        )

        # Content scheduler (multiple cron jobs)
        cs_jobs = [
            j for j in cls._scheduler.get_jobs()
            if j.id.startswith("content_scheduler_")
        ]
        next_runs = [
            j.next_run_time.isoformat()
            for j in cs_jobs
            if j.next_run_time
        ]
        cs_stats = cls._job_stats.get("content_scheduler", {"last_run_time": None, "total_runs": 0})
        all_paused = all(j.next_run_time is None for j in cs_jobs) if cs_jobs else True

        result["content_scheduler"] = {
            "enabled": CONTENT_SCHEDULER_ENABLED,
            "paused": all_paused,
            "scheduled_times": [t.strip() for t in CONTENT_SCHEDULER_TIMES],
            "next_runs": sorted(next_runs),
            "last_run": cs_stats["last_run_time"].isoformat() if cs_stats["last_run_time"] else None,
            "total_runs": cs_stats["total_runs"],
        }

        return result

    @classmethod
    def _get_job_status(cls, job_id: str, enabled: bool, extra: dict = None) -> dict:
        """Get status for a single job by ID."""
        job = cls._scheduler.get_job(job_id) if cls._scheduler else None
        stats = cls._job_stats.get(job_id, {"last_run_time": None, "total_runs": 0})

        status = {
            "enabled": enabled,
            "paused": job.next_run_time is None if job else True,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
            "last_run": stats["last_run_time"].isoformat() if stats["last_run_time"] else None,
            "total_runs": stats["total_runs"],
        }
        if extra:
            status.update(extra)
        return status

    @classmethod
    def pause(cls, job_prefix: str = "engagement_monitor") -> bool:
        """Pause job(s) by prefix. Returns True if successful."""
        if not cls._scheduler:
            return False
        try:
            jobs = [j for j in cls._scheduler.get_jobs() if j.id.startswith(job_prefix)]
            if not jobs:
                logger.warning(f"No jobs found with prefix '{job_prefix}'")
                return False
            for job in jobs:
                cls._scheduler.pause_job(job.id)
            logger.info(f"Paused {len(jobs)} job(s) with prefix '{job_prefix}'")
            return True
        except Exception as e:
            logger.error(f"Failed to pause jobs '{job_prefix}': {e}")
            return False

    @classmethod
    def resume(cls, job_prefix: str = "engagement_monitor") -> bool:
        """Resume job(s) by prefix. Returns True if successful."""
        if not cls._scheduler:
            return False
        try:
            jobs = [j for j in cls._scheduler.get_jobs() if j.id.startswith(job_prefix)]
            if not jobs:
                logger.warning(f"No jobs found with prefix '{job_prefix}'")
                return False
            for job in jobs:
                cls._scheduler.resume_job(job.id)
            logger.info(f"Resumed {len(jobs)} job(s) with prefix '{job_prefix}'")
            return True
        except Exception as e:
            logger.error(f"Failed to resume jobs '{job_prefix}': {e}")
            return False

    @classmethod
    async def trigger_now(cls, job_prefix: str = "engagement_monitor") -> bool:
        """Manually trigger a run (bypasses schedule).

        Runs immediately in the current context.
        """
        runners = {
            "engagement_monitor": engagement_monitor_run,
            "content_scheduler": content_scheduler_run,
        }
        func = runners.get(job_prefix)
        if not func:
            logger.error(f"Unknown job prefix for manual trigger: '{job_prefix}'")
            return False
        try:
            await func()
            return True
        except Exception as e:
            logger.error(f"Manual trigger failed for '{job_prefix}': {e}")
            return False
