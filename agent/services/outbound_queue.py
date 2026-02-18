"""
Outbound Queue Service
======================
Redis-first durable queue for all outbound Instagram actions.
Supabase outbound_queue_jobs table is the fallback when Redis is unavailable
and the permanent store for DLQ entries.

Redis key schema:
  outbound:queue:high       LIST  — HIGH priority (reply_comment, reply_dm)
  outbound:queue:normal     LIST  — NORMAL priority (publish_post, send_permission_dm, repost_ugc, sync_ugc)
  outbound:queue:scheduled  ZSET  — delayed retries (score = unix timestamp of next_retry_at)
  outbound:dlq              ZSET  — permanently failed (score = failed_at unix timestamp)
  outbound:lock:{job_id}    STRING — execution mutex (SET NX EX 120)
"""

import json
import time
from datetime import datetime, timezone, timedelta

from config import logger

QUEUE_HIGH = "outbound:queue:high"
QUEUE_NORMAL = "outbound:queue:normal"
QUEUE_SCHEDULED = "outbound:queue:scheduled"
QUEUE_DLQ = "outbound:dlq"

RETRY_DELAYS = [60, 120, 240, 480, 960]   # seconds per retry (index = retry_count - 1)
SUPABASE_DRAIN_BATCH = 50                  # max rows per Supabase fallback drain


def _get_redis():
    """Re-import _redis/_redis_available at call time to pick up reconnect state."""
    from services.supabase_service import _redis, _redis_available
    return _redis, _redis_available


def _priority_to_key(priority: str) -> str:
    return QUEUE_HIGH if priority == "high" else QUEUE_NORMAL


class OutboundQueue:
    """Static-method queue interface. No instance state."""

    RETRY_DELAYS = RETRY_DELAYS

    @staticmethod
    def enqueue(job: dict) -> dict:
        """Enqueue a job durably.

        Flow:
          1. Idempotency check — skip if active job with same key exists
          2. Try Redis LPUSH (fast path)
          3. Fallback to Supabase outbound_queue_jobs (when Redis down)
          4. On total failure — return success=False so caller can decide

        Returns:
            {"success": True, "queued": True, "job_id": str, "backend": "redis"|"supabase"}
            {"success": True, "queued": False, "job_id": str, "deduplicated": True}  — already active
            {"success": False, "queued": False, "error": str}  — both backends failed
        """
        from services.supabase_service import SupabaseService
        from routes.metrics import OUTBOUND_QUEUE_ENQUEUED

        job_id = job.get("job_id", "")
        idempotency_key = job.get("idempotency_key", "")
        priority = job.get("priority", "normal")

        # 1. Idempotency check (Supabase lookup — fast, uses index)
        if idempotency_key:
            existing = SupabaseService.get_outbound_job_by_idempotency_key(idempotency_key)
            if existing:
                logger.debug(f"Outbound job deduplicated: key={idempotency_key} existing={existing.get('job_id')}")
                OUTBOUND_QUEUE_ENQUEUED.labels(
                    action_type=job.get("action_type", "unknown"),
                    backend="deduplicated",
                ).inc()
                return {
                    "success": True,
                    "queued": False,
                    "job_id": existing.get("job_id", job_id),
                    "deduplicated": True,
                }

        job_json = json.dumps(job, default=str)
        queue_key = _priority_to_key(priority)

        # 2. Try Redis
        r, r_available = _get_redis()
        if r_available and r:
            try:
                r.lpush(queue_key, job_json)
                logger.info(f"Enqueued [{priority}] {job.get('action_type')} job={job_id} → Redis")
                OUTBOUND_QUEUE_ENQUEUED.labels(
                    action_type=job.get("action_type", "unknown"),
                    backend="redis",
                ).inc()
                return {"success": True, "queued": True, "job_id": job_id, "backend": "redis"}
            except Exception as e:
                logger.warning(f"Redis enqueue failed for job {job_id}: {e} — falling back to Supabase")

        # 3. Supabase fallback
        try:
            result = SupabaseService.create_outbound_job(job)
            if result:
                logger.info(f"Enqueued [{priority}] {job.get('action_type')} job={job_id} → Supabase fallback")
                OUTBOUND_QUEUE_ENQUEUED.labels(
                    action_type=job.get("action_type", "unknown"),
                    backend="supabase",
                ).inc()
                return {"success": True, "queued": True, "job_id": job_id, "backend": "supabase"}
        except Exception as e:
            logger.error(f"Supabase enqueue fallback also failed for job {job_id}: {e}")

        # 4. Total failure
        logger.error(f"CRITICAL: Both Redis and Supabase enqueue failed for job {job_id} action={job.get('action_type')}")
        return {"success": False, "queued": False, "error": "both_backends_failed"}

    @staticmethod
    def dequeue(priority: str = "high") -> dict | None:
        """Non-blocking pop from the named priority queue.

        Returns decoded job dict or None on empty / Redis unavailable.
        Falls back to Supabase get_pending_outbound_jobs when Redis is down.
        """
        from services.supabase_service import SupabaseService

        queue_key = _priority_to_key(priority)
        r, r_available = _get_redis()

        if r_available and r:
            try:
                data = r.rpop(queue_key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.warning(f"Redis dequeue failed ({queue_key}): {e}")

        # Supabase fallback: fetch one pending job matching priority
        try:
            rows = SupabaseService.get_pending_outbound_jobs(limit=1)
            for row in rows:
                if row.get("priority") == priority:
                    # Mark as processing so it won't be picked up again
                    SupabaseService.update_outbound_job_status(row["job_id"], "processing")
                    # Convert Supabase row → job dict shape
                    job = {
                        "job_id": row["job_id"],
                        "action_type": row["action_type"],
                        "priority": row["priority"],
                        "endpoint": row["endpoint"],
                        "payload": row["payload"],
                        "business_account_id": row.get("business_account_id"),
                        "idempotency_key": row["idempotency_key"],
                        "source": row["source"],
                        "created_at": row["created_at"],
                        "retry_count": row["retry_count"],
                        "max_retries": row["max_retries"],
                        "last_error": row.get("last_error"),
                    }
                    return job
        except Exception as e:
            logger.warning(f"Supabase dequeue fallback failed: {e}")

        return None

    @staticmethod
    def schedule_retry(job: dict, delay_seconds: int) -> bool:
        """Push job to QUEUE_SCHEDULED sorted set with score = now + delay_seconds.

        Falls back to Supabase update with next_retry_at timestamp.
        """
        from services.supabase_service import SupabaseService

        next_retry_unix = time.time() + delay_seconds
        next_retry_at = datetime.fromtimestamp(next_retry_unix, tz=timezone.utc).isoformat()

        job = dict(job)  # copy so we don't mutate caller's dict
        job["next_retry_at"] = next_retry_at

        r, r_available = _get_redis()
        if r_available and r:
            try:
                r.zadd(QUEUE_SCHEDULED, {json.dumps(job, default=str): next_retry_unix})
                logger.info(
                    f"Retry scheduled: job={job.get('job_id')} action={job.get('action_type')} "
                    f"attempt={job.get('retry_count')} delay={delay_seconds}s"
                )
                return True
            except Exception as e:
                logger.warning(f"Redis retry schedule failed for {job.get('job_id')}: {e}")

        # Supabase fallback
        try:
            SupabaseService.update_outbound_job_status(
                job.get("job_id"),
                "failed",
                extra_fields={
                    "retry_count": job.get("retry_count", 0),
                    "next_retry_at": next_retry_at,
                    "last_error": job.get("last_error", ""),
                },
            )
            return True
        except Exception as e:
            logger.error(f"Supabase retry schedule fallback failed for {job.get('job_id')}: {e}")
            return False

    @staticmethod
    def drain_scheduled() -> int:
        """Move all QUEUE_SCHEDULED jobs with score <= now into their priority queues.

        Called by worker every 30s. Returns count of jobs moved.
        """
        r, r_available = _get_redis()
        if not r_available or not r:
            return 0

        now_unix = time.time()
        moved = 0

        try:
            due_items = r.zrangebyscore(QUEUE_SCHEDULED, 0, now_unix)
            if not due_items:
                return 0

            for item in due_items:
                try:
                    job = json.loads(item)
                    queue_key = _priority_to_key(job.get("priority", "normal"))
                    # Atomic: remove from scheduled, push to queue
                    pipe = r.pipeline()
                    pipe.zrem(QUEUE_SCHEDULED, item)
                    pipe.lpush(queue_key, item)
                    pipe.execute()
                    moved += 1
                    logger.debug(f"Retry job moved to queue: job={job.get('job_id')} attempt={job.get('retry_count')}")
                except Exception as e:
                    logger.error(f"Failed to move scheduled item to queue: {e}")

        except Exception as e:
            logger.warning(f"drain_scheduled failed: {e}")

        if moved:
            logger.info(f"drain_scheduled: moved {moved} jobs to priority queues")

        return moved

    @staticmethod
    def drain_supabase_fallback() -> int:
        """When Redis is available, pull pending Supabase fallback jobs into Redis.

        Sets status='processing' before pushing to prevent double-drain.
        Reverts to 'pending' if Redis push fails.
        Returns count drained.
        """
        from services.supabase_service import SupabaseService

        r, r_available = _get_redis()
        if not r_available or not r:
            return 0

        drained = 0

        try:
            rows = SupabaseService.get_pending_outbound_jobs(limit=SUPABASE_DRAIN_BATCH)
            for row in rows:
                job_id = row["job_id"]
                # Mark processing to prevent re-drain
                SupabaseService.update_outbound_job_status(job_id, "processing")

                job = {
                    "job_id": job_id,
                    "action_type": row["action_type"],
                    "priority": row["priority"],
                    "endpoint": row["endpoint"],
                    "payload": row["payload"],
                    "business_account_id": row.get("business_account_id"),
                    "idempotency_key": row["idempotency_key"],
                    "source": row["source"],
                    "created_at": row["created_at"],
                    "retry_count": row["retry_count"],
                    "max_retries": row["max_retries"],
                    "last_error": row.get("last_error"),
                }

                try:
                    queue_key = _priority_to_key(row["priority"])
                    r.lpush(queue_key, json.dumps(job, default=str))
                    drained += 1
                    logger.info(f"Drained Supabase fallback job {job_id} → Redis [{row['priority']}]")
                except Exception as e:
                    # Revert — put back to pending so it's retried next drain cycle
                    logger.error(f"Failed to push drained job {job_id} to Redis: {e} — reverting to pending")
                    SupabaseService.update_outbound_job_status(job_id, "pending")

        except Exception as e:
            logger.warning(f"drain_supabase_fallback failed: {e}")

        return drained

    @staticmethod
    def move_to_dlq(job: dict, reason: str, error_category: str = None) -> bool:
        """Push exhausted job to DLQ (Redis sorted set + Supabase permanent record).

        Returns True on success.
        error_category is persisted to the DB for clean DLQ filtering.
        """
        from services.supabase_service import SupabaseService

        job_id = job.get("job_id", "unknown")
        failed_at = time.time()

        r, r_available = _get_redis()
        if r_available and r:
            try:
                dlq_entry = dict(job)
                dlq_entry["dlq_reason"] = reason
                dlq_entry["dlq_at"] = datetime.fromtimestamp(failed_at, tz=timezone.utc).isoformat()
                if error_category:
                    dlq_entry["error_category"] = error_category
                r.zadd(QUEUE_DLQ, {json.dumps(dlq_entry, default=str): failed_at})
            except Exception as e:
                logger.warning(f"Redis DLQ write failed for {job_id}: {e}")

        # Always write to Supabase for permanence
        try:
            extra = {
                "last_error": reason,
                "retry_count": job.get("retry_count", 0),
            }
            if error_category:
                extra["error_category"] = error_category
            SupabaseService.update_outbound_job_status(
                job_id,
                "dlq",
                extra_fields=extra,
            )
        except Exception as e:
            logger.error(f"Supabase DLQ write failed for {job_id}: {e}")
            return False

        logger.error(
            f"Job moved to DLQ: job={job_id} action={job.get('action_type')} "
            f"retries={job.get('retry_count')} reason={reason}"
        )
        return True

    @staticmethod
    def acquire_execution_lock(job_id: str, ttl: int = 120) -> bool:
        """Acquire Redis mutex before executing a job.

        Prevents double-execution when a job appears in both queues during Redis failover.
        Returns True if lock acquired (safe to proceed), False if already locked.
        """
        r, r_available = _get_redis()
        if not r_available or not r:
            return True   # Redis down — allow execution (no distributed lock available)

        lock_key = f"outbound:lock:{job_id}"
        try:
            result = r.set(lock_key, "1", nx=True, ex=ttl)
            return result is True
        except Exception as e:
            logger.warning(f"Failed to acquire execution lock for {job_id}: {e}")
            return True   # Fail open — allow execution

    @staticmethod
    def release_execution_lock(job_id: str) -> None:
        """Release execution lock after job completes (success or permanent failure)."""
        r, r_available = _get_redis()
        if not r_available or not r:
            return
        try:
            r.delete(f"outbound:lock:{job_id}")
        except Exception:
            pass   # TTL will expire it anyway

    @staticmethod
    def get_stats() -> dict:
        """Return queue depth stats for /queue/status endpoint and Prometheus gauges."""
        from routes.metrics import OUTBOUND_QUEUE_DEPTH

        r, r_available = _get_redis()

        stats = {
            "redis_available": r_available,
            "high_depth": 0,
            "normal_depth": 0,
            "scheduled_depth": 0,
            "dlq_depth": 0,
        }

        if r_available and r:
            try:
                stats["high_depth"] = r.llen(QUEUE_HIGH)
                stats["normal_depth"] = r.llen(QUEUE_NORMAL)
                stats["scheduled_depth"] = r.zcard(QUEUE_SCHEDULED)
                stats["dlq_depth"] = r.zcard(QUEUE_DLQ)
            except Exception as e:
                logger.warning(f"get_stats Redis read failed: {e}")

        # Update Prometheus gauges
        OUTBOUND_QUEUE_DEPTH.labels(queue="high").set(stats["high_depth"])
        OUTBOUND_QUEUE_DEPTH.labels(queue="normal").set(stats["normal_depth"])
        OUTBOUND_QUEUE_DEPTH.labels(queue="scheduled").set(stats["scheduled_depth"])
        OUTBOUND_QUEUE_DEPTH.labels(queue="dlq").set(stats["dlq_depth"])

        return stats
