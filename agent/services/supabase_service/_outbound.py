"""
Outbound Queue Persistence
==========================
Supabase-level job persistence for the outbound queue.
Used by: OutboundQueue (Redis-first), QueueWorker (fallback/drain).

This module handles the Supabase fallback layer — Redis is the primary
queue, Supabase is the durable fallback and DLQ store.
"""

from datetime import datetime, timezone
from pybreaker import CircuitBreakerError

from ._infra import execute, db_breaker, supabase, logger, is_valid_uuid


class OutboundQueueSupabase:
    """Supabase-level persistence for outbound queue jobs."""

    # ─────────────────────────────────────────
    # WRITE: Create Outbound Job (Redis fallback)
    # ─────────────────────────────────────────
    @staticmethod
    def create_outbound_job(job: dict) -> dict:
        """Insert a job into outbound_queue_jobs when Redis is unavailable.

        Returns the inserted row dict, or {} on failure.
        """
        if not supabase:
            return {}

        row = {
            "job_id": job.get("job_id"),
            "action_type": job.get("action_type"),
            "priority": job.get("priority", "normal"),
            "endpoint": job.get("endpoint"),
            "payload": job.get("payload", {}),
            "business_account_id": (
                job.get("business_account_id")
                if is_valid_uuid(job.get("business_account_id", ""))
                else None
            ),
            "idempotency_key": job.get("idempotency_key"),
            "source": job.get("source", "unknown"),
            "status": "pending",
            "retry_count": job.get("retry_count", 0),
            "max_retries": job.get("max_retries", 5),
            "created_at": job.get("created_at", datetime.now(timezone.utc).isoformat()),
        }

        try:
            result = execute(
                supabase.table("outbound_queue_jobs").insert(row),
                table="outbound_queue_jobs",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create outbound job in Supabase")
            return {}
        except Exception as e:
            logger.error(f"Failed to create outbound_queue_jobs row: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Get Pending Outbound Jobs (fallback drain)
    # ─────────────────────────────────────────
    @staticmethod
    def get_pending_outbound_jobs(limit: int = 50) -> list:
        """Fetch pending Supabase fallback jobs (Redis was unavailable at enqueue).

        Ordered by created_at ASC (FIFO). Used by drain_supabase_fallback().
        """
        if not supabase:
            return []

        try:
            result = execute(
                supabase.table("outbound_queue_jobs")
                .select("*")
                .eq("status", "pending")
                .is_("next_retry_at", "null")
                .order("created_at", desc=False)
                .limit(limit),
                table="outbound_queue_jobs",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping pending outbound jobs fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch pending outbound jobs: {e}")
            return []

    # ─────────────────────────────────────────
    # WRITE: Update Outbound Job Status
    # ─────────────────────────────────────────
    @staticmethod
    def update_outbound_job_status(
        job_id: str, status: str, extra_fields: dict = None
    ) -> bool:
        """Update outbound_queue_jobs status for a given job_id."""
        if not supabase or not job_id:
            return False

        update_data = {"status": status}
        if extra_fields:
            update_data.update(extra_fields)

        try:
            execute(
                supabase.table("outbound_queue_jobs")
                .update(update_data)
                .eq("job_id", job_id),
                table="outbound_queue_jobs",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update outbound job status")
            return False
        except Exception as e:
            logger.error(f"Failed to update outbound job {job_id}: {e}")
            return False

    # ─────────────────────────────────────────
    # READ: Get DLQ Jobs
    # ─────────────────────────────────────────
    @staticmethod
    def get_outbound_dlq(
        limit: int = 50, error_category: str = None, business_account_id: str = None
    ) -> list:
        """Fetch DLQ jobs from outbound_queue_jobs.

        Optional filters: error_category, business_account_id.
        Used by /queue/dlq endpoint.
        """
        if not supabase:
            return []

        try:
            query = (
                supabase.table("outbound_queue_jobs")
                .select("*")
                .eq("status", "dlq")
                .order("created_at", desc=True)
                .limit(limit)
            )
            if error_category:
                query = query.eq("error_category", error_category)
            if business_account_id:
                query = query.eq("business_account_id", business_account_id)

            result = execute(query, table="outbound_queue_jobs", operation="select")
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DLQ fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch DLQ jobs: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Get Outbound Job by Idempotency Key
    # ─────────────────────────────────────────
    @staticmethod
    def get_outbound_job_by_idempotency_key(idempotency_key: str) -> dict:
        """Fetch most recent active job matching this idempotency_key.

        Used by OutboundQueue.enqueue() to deduplicate before pushing.
        Excludes completed and dlq statuses.
        """
        if not supabase or not idempotency_key:
            return {}

        try:
            result = execute(
                supabase.table("outbound_queue_jobs")
                .select("job_id, status, action_type, created_at")
                .eq("idempotency_key", idempotency_key)
                .not_.in_("status", ["completed", "dlq"])
                .order("created_at", desc=True)
                .limit(1),
                table="outbound_queue_jobs",
                operation="select",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping idempotency key check")
            return {}
        except Exception as e:
            logger.warning(f"Failed to check idempotency key {idempotency_key}: {e}")
            return {}
