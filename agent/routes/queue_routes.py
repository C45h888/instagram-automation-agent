"""
Outbound Queue Routes
=====================
Exposes queue status, DLQ inspection, and DLQ retry endpoints.

Routes:
  GET  /queue/status    — Public. Queue depth + worker status.
  GET  /queue/dlq       — Auth required. Dead-letter jobs.
  POST /queue/retry-dlq — Auth required. Re-enqueue DLQ jobs.
"""

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger("oversight-agent")

queue_router = APIRouter(prefix="/queue", tags=["queue"])


@queue_router.get("/status")
async def queue_status():
    """Public endpoint — queue depth and worker running status."""
    try:
        from services.outbound_queue import OutboundQueue
        from fastapi import Request
        stats = OutboundQueue.get_stats()
        return {"status": "ok", "queue": stats}
    except Exception as e:
        logger.error(f"queue_status error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


@queue_router.get("/dlq")
async def get_dlq(limit: int = Query(default=50, ge=1, le=200)):
    """Auth required — list dead-letter jobs (up to `limit`)."""
    try:
        from services.supabase_service import SupabaseService
        jobs = SupabaseService.get_outbound_dlq(limit=limit)
        return {"status": "ok", "count": len(jobs), "jobs": jobs}
    except Exception as e:
        logger.error(f"get_dlq error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


@queue_router.post("/retry-dlq")
async def retry_dlq(limit: int = Query(default=50, ge=1, le=200)):
    """Auth required — reset DLQ jobs to pending and re-enqueue them.

    Resets retry_count=0, status='pending', clears last_error,
    then pushes each job back to the Redis priority queue.
    """
    try:
        from services.supabase_service import SupabaseService
        from services.outbound_queue import OutboundQueue

        jobs = SupabaseService.get_outbound_dlq(limit=limit)
        re_enqueued = 0
        failed = 0

        for job in jobs:
            job_id = str(job.get("job_id", ""))
            # Reset status to pending in Supabase first
            reset_ok = SupabaseService.update_outbound_job_status(
                job_id,
                "pending",
                extra_fields={"retry_count": 0, "last_error": None, "next_retry_at": None},
            )
            if not reset_ok:
                failed += 1
                continue

            # Re-enqueue into Redis (or Supabase fallback)
            # Build a minimal job dict from Supabase row
            queue_job = {
                "job_id": job_id,
                "action_type": job.get("action_type", ""),
                "priority": job.get("priority", "normal"),
                "endpoint": job.get("endpoint", ""),
                "payload": job.get("payload", {}),
                "business_account_id": str(job.get("business_account_id", "") or ""),
                "idempotency_key": job.get("idempotency_key", ""),
                "source": job.get("source", "dlq_retry"),
                "created_at": job.get("created_at", ""),
                "retry_count": 0,
                "max_retries": job.get("max_retries", 5),
            }
            result = OutboundQueue.enqueue(queue_job)
            if result.get("success"):
                re_enqueued += 1
            else:
                failed += 1

        return {
            "status": "ok",
            "re_enqueued": re_enqueued,
            "failed": failed,
            "total": len(jobs),
        }
    except Exception as e:
        logger.error(f"retry_dlq error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})
