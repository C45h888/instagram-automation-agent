"""
Queue Worker Service
====================
Background asyncio worker that executes jobs from the outbound queue.

Three concurrent loops started via asyncio.create_task() in agent.py lifespan:
  _high_priority_loop   — polls QUEUE_HIGH every 0.5s (comment/DM replies)
  _normal_priority_loop — polls QUEUE_NORMAL every 0.5s (posts, DMs, UGC)
  _scheduled_retry_loop — drains delayed retries + Supabase fallback every 30s

Graceful shutdown: stops accepting, waits up to 15s for in-flight jobs.
"""

import asyncio
import time
from datetime import datetime, timezone

import httpx

from config import logger, BACKEND_API_URL, backend_headers, BACKEND_TIMEOUT_SECONDS
from services.outbound_queue import OutboundQueue, RETRY_DELAYS

# Polling + shutdown constants
POLL_INTERVAL = 0.5               # seconds between queue polls (both lanes)
SCHEDULED_DRAIN_INTERVAL = 30     # seconds between drain_scheduled() calls
GRACEFUL_SHUTDOWN_TIMEOUT = 15    # seconds to wait for in-flight jobs on SIGTERM

# Rate-limit retry floor: 5 min minimum delay on HTTP 429
RATE_LIMIT_DELAY_FLOOR = 300


class QueueWorker:
    """Manages background asyncio loops for processing outbound job queues."""

    def __init__(self):
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._in_flight: set[str] = set()  # job_ids currently being executed

    # ----------------------------------------
    # Lifecycle
    # ----------------------------------------

    def start(self) -> None:
        """Start background consumer loops. Called in agent.py lifespan."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._high_priority_loop(), name="queue-high"),
            asyncio.create_task(self._normal_priority_loop(), name="queue-normal"),
            asyncio.create_task(self._scheduled_retry_loop(), name="queue-retry"),
        ]
        logger.info("QueueWorker started: 3 background loops (high, normal, retry)")

    async def stop(self) -> None:
        """Graceful shutdown: drain in-flight, then cancel loops."""
        logger.info(f"QueueWorker stopping... in-flight={len(self._in_flight)}")
        self._running = False

        # Wait for in-flight jobs to complete (or timeout)
        deadline = time.monotonic() + GRACEFUL_SHUTDOWN_TIMEOUT
        while self._in_flight and time.monotonic() < deadline:
            await asyncio.sleep(0.25)

        if self._in_flight:
            logger.warning(f"QueueWorker shutdown timeout — {len(self._in_flight)} jobs still in-flight: {self._in_flight}")

        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("QueueWorker stopped")

    # ----------------------------------------
    # Consumer Loops
    # ----------------------------------------

    async def _high_priority_loop(self) -> None:
        """Continuously drain the HIGH priority queue (reply_comment, reply_dm)."""
        while self._running:
            try:
                job = await asyncio.to_thread(OutboundQueue.dequeue, "high")
                if job:
                    # Fire and forget — error isolation inside _execute_job
                    asyncio.create_task(self._execute_job(job))
                else:
                    await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"HIGH queue loop unexpected error: {e}")
                await asyncio.sleep(1)

    async def _normal_priority_loop(self) -> None:
        """Continuously drain the NORMAL priority queue."""
        # Stagger 0.1s from high loop to avoid thundering herd on Redis
        await asyncio.sleep(0.1)
        while self._running:
            try:
                job = await asyncio.to_thread(OutboundQueue.dequeue, "normal")
                if job:
                    asyncio.create_task(self._execute_job(job))
                else:
                    await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"NORMAL queue loop unexpected error: {e}")
                await asyncio.sleep(1)

    async def _scheduled_retry_loop(self) -> None:
        """Periodically move due scheduled retries + drain Supabase fallback into Redis."""
        while self._running:
            try:
                moved = await asyncio.to_thread(OutboundQueue.drain_scheduled)
                drained = await asyncio.to_thread(OutboundQueue.drain_supabase_fallback)
                if moved or drained:
                    logger.debug(f"Retry loop: moved={moved} drained={drained}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled retry loop error: {e}")
            await asyncio.sleep(SCHEDULED_DRAIN_INTERVAL)

    # ----------------------------------------
    # Job Execution
    # ----------------------------------------

    async def _execute_job(self, job: dict) -> None:
        """Full execution pipeline for a single job. Never raises."""
        from services.supabase_service import SupabaseService
        from routes.metrics import OUTBOUND_QUEUE_EXECUTE, OUTBOUND_QUEUE_LATENCY

        job_id = job.get("job_id", "unknown")
        action_type = job.get("action_type", "unknown")
        enqueued_at = job.get("created_at", "")
        start_time = time.monotonic()

        self._in_flight.add(job_id)

        try:
            # 1. Acquire execution mutex (prevents double-execution on failover)
            lock_acquired = await asyncio.to_thread(OutboundQueue.acquire_execution_lock, job_id)
            if not lock_acquired:
                logger.info(f"Job {job_id} skipped — already being executed by another worker")
                OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="skipped").inc()
                return

            # 2. Idempotency guard for publish_post
            is_safe = await self._is_safe_to_execute(job)
            if not is_safe:
                logger.info(f"Job {job_id} skipped — idempotency guard (publish_post already published)")
                OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="skipped").inc()
                await asyncio.to_thread(OutboundQueue.release_execution_lock, job_id)
                return

            # 3. Mark processing in Supabase (best-effort)
            await asyncio.to_thread(
                SupabaseService.update_outbound_job_status,
                job_id, "processing"
            )

            # 4. Execute HTTP call
            response = await self._call_backend(job)
            await self._on_success(job, response, time.monotonic() - start_time)

        except httpx.HTTPStatusError as e:
            # Parse structured error metadata from backend response body
            try:
                body = e.response.json()
            except Exception:
                body = {}

            retryable = body.get("retryable", True)   # Default safe: retry if backend doesn't say
            error_category = body.get("error_category", "unknown")
            retry_after_seconds = body.get("retry_after_seconds", None)
            error_msg = body.get("error") or f"http_{e.response.status_code}: {e.response.text[:200]}"

            logger.warning(
                f"Job {job_id} backend HTTP error: {error_msg} "
                f"category={error_category} retryable={retryable}"
            )
            await self._on_failure(
                job,
                error_msg,
                retryable=retryable,
                error_category=error_category,
                retry_after_seconds=retry_after_seconds,
            )

        except httpx.TimeoutException:
            logger.warning(f"Job {job_id} backend timeout")
            await self._on_failure(
                job,
                "backend_timeout",
                retryable=True,
                error_category="transient",
                retry_after_seconds=30,
            )

        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            logger.error(f"Job {job_id} unexpected execution error: {error}")
            await self._on_failure(
                job,
                error,
                retryable=True,
                error_category="unknown",
            )

        finally:
            self._in_flight.discard(job_id)

    async def _is_safe_to_execute(self, job: dict) -> bool:
        """Check that executing this job won't cause duplicate side-effects.

        Only applies to publish_post: verifies scheduled_posts.status == 'publishing'.
        All other action types return True unconditionally.
        """
        if job.get("action_type") != "publish_post":
            return True

        scheduled_post_id = job.get("payload", {}).get("scheduled_post_id")
        if not scheduled_post_id:
            return True   # No ID to check — allow execution

        from config import supabase

        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("scheduled_posts")
                .select("status")
                .eq("id", scheduled_post_id)
                .single()
                .execute()
            )
            status = result.data.get("status") if result.data else None
            # Only safe to execute if still in 'publishing' state
            return status == "publishing"
        except Exception as e:
            logger.warning(f"_is_safe_to_execute check failed for post {scheduled_post_id}: {e} — allowing execution")
            return True   # Fail open — attempt execution

    async def _call_backend(self, job: dict) -> dict:
        """Async HTTP POST to the backend endpoint. Raises on failure."""
        endpoint = job.get("endpoint", "")
        payload = job.get("payload", {})
        url = f"{BACKEND_API_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=BACKEND_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload, headers=backend_headers())
            response.raise_for_status()
            return response.json()

    async def _on_success(self, job: dict, response: dict, elapsed: float) -> None:
        """Handle successful job execution: update status, settle state, log."""
        from services.supabase_service import SupabaseService
        from routes.metrics import OUTBOUND_QUEUE_EXECUTE, OUTBOUND_QUEUE_LATENCY

        job_id = job.get("job_id", "unknown")
        action_type = job.get("action_type", "unknown")

        # Update Supabase job record
        await asyncio.to_thread(
            SupabaseService.update_outbound_job_status,
            job_id, "completed",
            {"completed_at": datetime.now(timezone.utc).isoformat()}
        )

        # Action-specific state settlement
        if action_type == "publish_post":
            await self._settle_publish_post_success(job, response)

        # Release execution lock
        await asyncio.to_thread(OutboundQueue.release_execution_lock, job_id)

        # Metrics
        OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="success").inc()
        OUTBOUND_QUEUE_LATENCY.labels(action_type=action_type).observe(elapsed)

        # Audit log
        await asyncio.to_thread(
            SupabaseService.log_decision,
            event_type="outbound_job_completed",
            action="execute",
            resource_type="outbound_queue_job",
            resource_id=job_id,
            user_id=job.get("business_account_id", ""),
            details={
                "action_type": action_type,
                "source": job.get("source", ""),
                "retry_count": job.get("retry_count", 0),
                "latency_ms": round(elapsed * 1000),
                "endpoint": job.get("endpoint", ""),
            },
        )

        logger.info(f"Job completed: job={job_id} action={action_type} latency={elapsed:.2f}s")

    async def _settle_publish_post_success(self, job: dict, response: dict) -> None:
        """Update scheduled_posts → 'published' + set instagram_media_id."""
        from services.supabase_service import SupabaseService

        scheduled_post_id = job.get("payload", {}).get("scheduled_post_id")
        if not scheduled_post_id:
            return

        instagram_media_id = response.get("id")
        await asyncio.to_thread(
            SupabaseService.update_scheduled_post_status,
            scheduled_post_id,
            "published",
            {
                "instagram_media_id": instagram_media_id,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info(f"publish_post settled: post={scheduled_post_id} media_id={instagram_media_id}")

    async def _on_failure(
        self,
        job: dict,
        error: str,
        retryable: bool = True,
        error_category: str = "unknown",
        retry_after_seconds: int | None = None,
    ) -> None:
        """Handle failed job execution: retry or DLQ.

        retryable=False  → immediate DLQ, no retry budget consumed
        error_category   → 'rate_limit', 'transient', 'auth_failure', 'permanent', 'unknown'
        retry_after_seconds → explicit delay from backend (overrides RETRY_DELAYS when set)
        """
        from services.supabase_service import SupabaseService
        from routes.metrics import OUTBOUND_QUEUE_EXECUTE, OUTBOUND_QUEUE_RETRIES, OUTBOUND_QUEUE_DLQ

        job_id = job.get("job_id", "unknown")
        action_type = job.get("action_type", "unknown")

        # Copy job and update error state
        job = dict(job)
        job["retry_count"] = job.get("retry_count", 0) + 1
        job["last_error"] = error

        retry_count = job["retry_count"]
        max_retries = job.get("max_retries", 5)

        # Non-retryable: auth failure, permanent bad params, policy block, etc.
        # Go straight to DLQ — retrying wastes budget and won't fix the root cause.
        if not retryable:
            logger.warning(
                f"[Worker] Job {job_id} non-retryable "
                f"({error_category}): {error}"
            )
            await asyncio.to_thread(OutboundQueue.move_to_dlq, job, reason=f"non_retryable:{error_category}:{error}")
            await asyncio.to_thread(OutboundQueue.release_execution_lock, job_id)

            if action_type == "publish_post":
                await self._settle_publish_post_failure(job, error)

            OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="error").inc()
            OUTBOUND_QUEUE_DLQ.labels(action_type=action_type).inc()

            await asyncio.to_thread(
                SupabaseService.log_decision,
                event_type="outbound_job_dlq",
                action="dlq",
                resource_type="outbound_queue_job",
                resource_id=job_id,
                user_id=job.get("business_account_id", ""),
                details={
                    "action_type": action_type,
                    "source": job.get("source", ""),
                    "total_retries": retry_count,
                    "final_error": error,
                    "error_category": error_category,
                    "non_retryable": True,
                },
            )
            self._in_flight.discard(job_id)
            return

        if retry_count <= max_retries:
            # Determine retry delay:
            # 1. Use explicit backend hint if provided
            # 2. For rate_limit without hint: max(backoff_table, RATE_LIMIT_DELAY_FLOOR)
            # 3. For everything else: standard backoff table
            if retry_after_seconds is not None:
                delay = retry_after_seconds
            elif error_category == "rate_limit":
                backoff = RETRY_DELAYS[min(retry_count - 1, len(RETRY_DELAYS) - 1)]
                delay = max(backoff, RATE_LIMIT_DELAY_FLOOR)
            else:
                delay = RETRY_DELAYS[min(retry_count - 1, len(RETRY_DELAYS) - 1)]

            await asyncio.to_thread(OutboundQueue.schedule_retry, job, delay)
            await asyncio.to_thread(OutboundQueue.release_execution_lock, job_id)

            OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="error").inc()
            OUTBOUND_QUEUE_RETRIES.labels(action_type=action_type).inc()

            logger.warning(
                f"[Worker] Retry {retry_count}/{max_retries} for job {job_id} "
                f"in {delay}s (category={error_category})"
            )

        else:
            # Max retries exhausted — move to DLQ
            reason = f"max_retries_exceeded:{error_category}:{error}"
            await asyncio.to_thread(OutboundQueue.move_to_dlq, job, reason)
            await asyncio.to_thread(OutboundQueue.release_execution_lock, job_id)

            if action_type == "publish_post":
                await self._settle_publish_post_failure(job, error)

            OUTBOUND_QUEUE_EXECUTE.labels(action_type=action_type, status="error").inc()
            OUTBOUND_QUEUE_DLQ.labels(action_type=action_type).inc()

            await asyncio.to_thread(
                SupabaseService.log_decision,
                event_type="outbound_job_dlq",
                action="dlq",
                resource_type="outbound_queue_job",
                resource_id=job_id,
                user_id=job.get("business_account_id", ""),
                details={
                    "action_type": action_type,
                    "source": job.get("source", ""),
                    "total_retries": retry_count,
                    "final_error": error,
                    "error_category": error_category,
                },
            )

        self._in_flight.discard(job_id)

    async def _settle_publish_post_failure(self, job: dict, error: str) -> None:
        """Update scheduled_posts → 'failed' when publish_post exhausts retries."""
        from services.supabase_service import SupabaseService

        scheduled_post_id = job.get("payload", {}).get("scheduled_post_id")
        if not scheduled_post_id:
            return

        await asyncio.to_thread(
            SupabaseService.update_scheduled_post_status,
            scheduled_post_id,
            "failed",
            {"publish_error": f"Queue DLQ after {job.get('retry_count')} retries: {error}"},
        )
        logger.error(f"publish_post settled as failed: post={scheduled_post_id} error={error}")
