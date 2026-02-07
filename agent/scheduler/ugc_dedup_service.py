"""
UGC Deduplication Service
==========================
Redis-backed fast deduplication for UGC discovery.
Prevents processing the same Instagram media ID twice across scheduler cycles.

Primary dedup: Supabase `ugc_discovered` table unique constraint on
(business_account_id, instagram_media_id).
Secondary dedup: Redis set as fast-path cache (avoids re-querying Supabase for
posts already processed in recent cycles).

Graceful fallback: If Redis is unavailable, relies solely on the Supabase
unique constraint — slightly slower but functionally correct.
"""

from config import logger
from services.supabase_service import _redis, _redis_available


class UgcDedupService:
    """Redis-backed deduplication for UGC discovery media processing."""

    REDIS_KEY = "ugc_discovery:processed_ids"
    TTL_SECONDS = 604800  # 7 days

    @staticmethod
    def is_processed(media_id: str) -> bool:
        """Check if an Instagram media ID has been recently processed (Redis fast path).

        Returns False if Redis is unavailable — the Supabase unique constraint
        and get_existing_ugc_ids() serve as the authoritative filter.
        """
        if not _redis_available or not media_id:
            return False
        try:
            return bool(_redis.sismember(UgcDedupService.REDIS_KEY, media_id))
        except Exception:
            return False

    @staticmethod
    def mark_processed(media_id: str):
        """Add media ID to Redis dedup set with TTL.

        Silently fails if Redis is unavailable — the Supabase
        unique constraint is the authoritative record.
        """
        if not _redis_available or not media_id:
            return
        try:
            _redis.sadd(UgcDedupService.REDIS_KEY, media_id)
            # Refresh TTL on the entire set (keeps it alive while discovery is active)
            _redis.expire(UgcDedupService.REDIS_KEY, UgcDedupService.TTL_SECONDS)
        except Exception as e:
            logger.debug(f"Redis UGC dedup mark_processed failed (non-critical): {e}")

    @staticmethod
    def get_processed_count() -> int:
        """Return the number of media IDs in the dedup set (for status endpoint)."""
        if not _redis_available:
            return 0
        try:
            return _redis.scard(UgcDedupService.REDIS_KEY) or 0
        except Exception:
            return 0
