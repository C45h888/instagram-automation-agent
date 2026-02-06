"""
Deduplication Service
======================
Redis-backed fast deduplication for the engagement monitor.
Prevents processing the same comment twice across scheduler cycles.

Primary dedup: Supabase `processed_by_automation = false` filter in query.
Secondary dedup: Redis set as fast-path cache (avoids re-processing comments
that were handled in the current cycle but not yet committed to Supabase).

Graceful fallback: If Redis is unavailable, relies solely on the Supabase
query filter — slightly slower but functionally correct.
"""

from config import logger
from services.supabase_service import _redis, _redis_available


class DedupService:
    """Redis-backed deduplication for engagement monitor comment processing."""

    REDIS_KEY = "engagement_monitor:processed_ids"
    TTL_SECONDS = 86400  # 24 hours

    @staticmethod
    def is_processed(comment_id: str) -> bool:
        """Check if a comment ID has been recently processed (Redis fast path).

        Returns False if Redis is unavailable — the Supabase WHERE clause
        (processed_by_automation = false) serves as the authoritative filter.
        """
        if not _redis_available or not comment_id:
            return False
        try:
            return bool(_redis.sismember(DedupService.REDIS_KEY, comment_id))
        except Exception:
            return False

    @staticmethod
    def mark_processed(comment_id: str):
        """Add comment ID to Redis dedup set with TTL.

        Silently fails if Redis is unavailable — the Supabase
        `mark_comment_processed` call is the authoritative record.
        """
        if not _redis_available or not comment_id:
            return
        try:
            _redis.sadd(DedupService.REDIS_KEY, comment_id)
            # Refresh TTL on the entire set (keeps it alive while monitor is active)
            _redis.expire(DedupService.REDIS_KEY, DedupService.TTL_SECONDS)
        except Exception as e:
            logger.debug(f"Redis dedup mark_processed failed (non-critical): {e}")

    @staticmethod
    def get_processed_count() -> int:
        """Return the number of comment IDs in the dedup set (for status endpoint)."""
        if not _redis_available:
            return 0
        try:
            return _redis.scard(DedupService.REDIS_KEY) or 0
        except Exception:
            return 0
