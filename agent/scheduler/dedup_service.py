"""
Deduplication Service
======================
Redis-backed fast deduplication for the engagement monitor.
Prevents processing the same comment twice across scheduler cycles.

Primary dedup: Supabase `processed_by_automation = false` filter in query.
Secondary dedup: Redis set as fast-path cache (avoids re-processing comments
that were handled in the current cycle but not yet committed to Supabase).

Keys are scoped per business account:
  engagement_monitor:processed_ids:<account_id>

This prevents cross-account collision if two accounts ever share an
instagram_comment_id (theoretically possible across unrelated IG accounts).

Graceful fallback: If Redis is unavailable, relies solely on the Supabase
query filter — slightly slower but functionally correct.
"""

from config import logger
from services.supabase_service import _redis, _redis_available


class DedupService:
    """Redis-backed deduplication for engagement monitor comment processing."""

    KEY_PREFIX = "engagement_monitor:processed_ids"
    TTL_SECONDS = 86400  # 24 hours

    @staticmethod
    def _key(account_id: str) -> str:
        return f"{DedupService.KEY_PREFIX}:{account_id}"

    @staticmethod
    def is_processed(comment_id: str, account_id: str) -> bool:
        """Check if a comment ID has been recently processed (Redis fast path).

        Returns False if Redis is unavailable — the Supabase WHERE clause
        (processed_by_automation = false) serves as the authoritative filter.
        """
        if not _redis_available or not comment_id or not account_id:
            return False
        try:
            return bool(_redis.sismember(DedupService._key(account_id), comment_id))
        except Exception:
            return False

    @staticmethod
    def mark_processed(comment_id: str, account_id: str):
        """Add comment ID to the per-account Redis dedup set with TTL.

        Silently fails if Redis is unavailable — the Supabase
        `mark_comment_processed` call is the authoritative record.
        """
        if not _redis_available or not comment_id or not account_id:
            return
        try:
            key = DedupService._key(account_id)
            _redis.sadd(key, comment_id)
            # Refresh TTL on the set (keeps it alive while monitor is active)
            _redis.expire(key, DedupService.TTL_SECONDS)
        except Exception as e:
            logger.debug(f"Redis dedup mark_processed failed (non-critical): {e}")

    @staticmethod
    def get_processed_count() -> int:
        """Return total comment IDs across all per-account dedup sets (for status endpoint)."""
        if not _redis_available:
            return 0
        try:
            total = 0
            cursor = 0
            pattern = f"{DedupService.KEY_PREFIX}:*"
            while True:
                cursor, keys = _redis.scan(cursor, match=pattern, count=100)
                for key in keys:
                    try:
                        total += _redis.scard(key) or 0
                    except Exception:
                        pass
                if cursor == 0:
                    break
            return total
        except Exception:
            return 0
