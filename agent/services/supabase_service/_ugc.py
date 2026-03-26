"""
UGC Service
===========
UGC discovery, content storage, and permission requests.
Used by: UGC discovery scheduler.

Note: update_ugc_permission_status and get_ugc_stats are DEAD CODE — removed.
"""

from pybreaker import CircuitBreakerError

from ._infra import execute, db_breaker, supabase, logger


class UGCService:
    """UGC discovery, content storage, and permissions."""

    # ─────────────────────────────────────────
    # READ: Monitored Hashtags
    # ─────────────────────────────────────────
    @staticmethod
    def get_monitored_hashtags(business_account_id: str) -> list:
        """Fetch active monitored hashtags for UGC discovery."""
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("ugc_monitored_hashtags")
                .select("id, hashtag")
                .eq("business_account_id", business_account_id)
                .eq("is_active", True),
                table="ugc_monitored_hashtags",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping monitored hashtags fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch monitored hashtags for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Existing UGC IDs (DB-level dedup)
    # ─────────────────────────────────────────
    @staticmethod
    def get_existing_ugc_ids(business_account_id: str) -> set:
        """Fetch visitor_post_ids already in ugc_content for this account.

        Used as authoritative dedup when Redis is unavailable.
        """
        if not supabase or not business_account_id:
            return set()

        try:
            result = execute(
                supabase.table("ugc_content")
                .select("visitor_post_id")
                .eq("business_account_id", business_account_id),
                table="ugc_content",
                operation="select",
            )
            return {row["visitor_post_id"] for row in (result.data or [])}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping existing UGC IDs fetch")
            return set()
        except Exception as e:
            logger.warning(f"Failed to fetch existing UGC IDs: {e}")
            return set()

    # ─────────────────────────────────────────
    # WRITE: Create/Update UGC Content
    # ─────────────────────────────────────────
    @staticmethod
    def create_or_update_ugc(data: dict) -> dict:
        """Upsert a discovered UGC post into ugc_content.

        Expected data keys: business_account_id, visitor_post_id, author_id,
        author_username, message, media_type, media_url, permalink_url,
        like_count, comment_count, created_time, source, quality_score,
        quality_tier, run_id
        Returns full row including id (UUID needed for permissions FK).
        """
        if not supabase:
            return {}

        try:
            result = execute(
                supabase.table("ugc_content")
                .upsert(data, on_conflict="business_account_id,visitor_post_id"),
                table="ugc_content",
                operation="upsert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create/update ugc_content")
            return {}
        except Exception as e:
            logger.error(f"Failed to create/update ugc_content: {e}")
            return {}

    # ─────────────────────────────────────────
    # WRITE: Create UGC Permission Request
    # ─────────────────────────────────────────
    @staticmethod
    def create_ugc_permission(data: dict) -> dict:
        """Insert a UGC permission request into ugc_permissions.

        Expected data keys: ugc_content_id, business_account_id,
        request_message, status (pending/granted/denied/expired), run_id
        """
        if not supabase:
            return {}

        try:
            result = execute(
                supabase.table("ugc_permissions").insert(data),
                table="ugc_permissions",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create ugc_permission")
            return {}
        except Exception as e:
            logger.error(f"Failed to create ugc_permission: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Granted UGC Permissions (Auto-Repost)
    # ─────────────────────────────────────────
    @staticmethod
    def get_granted_ugc_permissions(business_account_id: str) -> list:
        """Fetch ugc_permissions with status='granted' not yet reposted.

        Backend /repost-ugc sets status='reposted' after publish,
        so filtering on 'granted' naturally excludes already-reposted records.
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("ugc_permissions")
                .select("id, ugc_content_id")
                .eq("business_account_id", business_account_id)
                .eq("status", "granted"),
                table="ugc_permissions",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping get_granted_ugc_permissions")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch granted UGC permissions: {e}")
            return []
