"""
Engagement Service
=================
Post context, account info, comments, and account discovery.
Used by: engagement monitor, content scheduler, webhooks, LangChain tools.

All methods: @staticmethod
All queries route through: execute() from _infra
Caching via: post_context_cache, account_info_cache, cache_get, cache_set from _infra
"""

from datetime import datetime, timezone, timedelta
from pybreaker import CircuitBreakerError

from services.ids import InstagramId, SupabaseUUID, verify_id_space
from ._infra import (
    execute,
    cache_get,
    cache_set,
    post_context_cache,
    account_info_cache,
    db_breaker,
    supabase,
    logger,
)


class EngagementService:
    """Post context, account info, comments, and account discovery."""

    # ─────────────────────────────────────────
    # READ: Post Context
    # ─────────────────────────────────────────
    @staticmethod
    def get_post_context(post_id: InstagramId) -> dict:
        """Fetch post caption and engagement metrics from instagram_media.

        Caching: L1 (30s TTL) → L2 Redis (30s TTL) → Supabase
        engagement_rate is COMPUTED: (likes + comments) / reach

        Args:
            post_id: InstagramId — Meta/Instagram media ID (e.g. "17841475450533073_1234567890").
                     NOT a Supabase UUID. Use get_post_context_by_uuid() for UUID lookups.
        """
        post_id = verify_id_space(post_id, InstagramId)
        if not supabase or not post_id:
            return {}

        cache_key = f"post_ctx:{post_id}"

        if cache_key in post_context_cache:
            CACHE_HITS.labels(key_type="post_context_l1").inc()
            return post_context_cache[cache_key]

        cached = cache_get(cache_key)
        if cached:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="post_context_l2").inc()
            post_context_cache[cache_key] = cached
            cache_set(cache_key, cached, ttl=30)   # refresh L2 TTL so it doesn't serve stale data
            return cached

        from metrics import CACHE_MISSES
        CACHE_MISSES.labels(key_type="post_context").inc()

        try:
            result = execute(
                supabase.table("instagram_media")
                .select("caption, like_count, comments_count, media_type, shares_count, reach")
                .eq("instagram_media_id", post_id)
                .limit(1),
                table="instagram_media",
                operation="select",
            )

            if not result.data:
                return {}

            data = result.data[0]
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            reach = data.get("reach", 0) or 0
            data["engagement_rate"] = round((likes + comments) / reach, 4) if reach > 0 else 0.0

            post_context_cache[cache_key] = data
            cache_set(cache_key, data, ttl=30)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping post context fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch post context for {post_id}: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Account Info
    # ─────────────────────────────────────────
    @staticmethod
    def get_account_info(business_account_id: str) -> dict:
        """Fetch account info from instagram_business_accounts.

        Caching: L1 (60s TTL) → L2 Redis (60s TTL) → Supabase
        """
        if not supabase or not business_account_id:
            return {}

        cache_key = f"account:{business_account_id}"

        if cache_key in account_info_cache:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="account_info_l1").inc()
            return account_info_cache[cache_key]

        cached = cache_get(cache_key)
        if cached:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="account_info_l2").inc()
            account_info_cache[cache_key] = cached
            return cached

        from metrics import CACHE_MISSES
        CACHE_MISSES.labels(key_type="account_info").inc()

        try:
            result = execute(
                supabase.table("instagram_business_accounts")
                .select("username, name, account_type, followers_count, biography, category")
                .eq("id", business_account_id)
                .limit(1),
                table="instagram_business_accounts",
                operation="select",
            )

            if not result.data:
                return {}

            data = result.data[0]
            account_info_cache[cache_key] = data
            cache_set(cache_key, data, ttl=60)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping account info fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch account info for {business_account_id}: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Resolve IG Business ID → Supabase UUID
    # ─────────────────────────────────────────
    @staticmethod
    def get_account_uuid_by_instagram_id(instagram_business_id: str) -> str | None:
        """Resolve Instagram numeric Business ID → Supabase UUID.

        Used by webhook handlers: Meta sends entry.id as the IG numeric ID
        but all backend proxy calls require the Supabase UUID.
        """
        if not supabase or not instagram_business_id:
            return None
        try:
            result = execute(
                supabase.table("instagram_business_accounts")
                .select("id")
                .eq("instagram_business_id", instagram_business_id)
                .limit(1),
                table="instagram_business_accounts",
                operation="select",
            )
            data = result.data
            return data[0]["id"] if data else None
        except Exception as e:
            logger.warning(f"Failed to resolve IG ID {instagram_business_id} → UUID: {e}")
            return None

    # ─────────────────────────────────────────
    # READ: Recent Comments
    # ─────────────────────────────────────────
    @staticmethod
    def get_recent_comments(business_account_id: str, limit: int = 10) -> list:
        """Fetch recent comments for pattern context."""
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("instagram_comments")
                .select("text, sentiment, category, priority, author_username, created_at")
                .eq("business_account_id", business_account_id)
                .order("created_at", desc=True)
                .limit(limit),
                table="instagram_comments",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping recent comments fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch recent comments: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Recent Post Performance
    # ─────────────────────────────────────────
    @staticmethod
    def get_recent_post_performance(business_account_id: str, limit: int = 10) -> dict:
        """Fetch recent posts to calculate average engagement for benchmarking."""
        if not supabase or not business_account_id:
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

        try:
            result = execute(
                supabase.table("instagram_media")
                .select("like_count, comments_count, shares_count, reach")
                .eq("business_account_id", business_account_id)
                .order("published_at", desc=True)
                .limit(limit),
                table="instagram_media",
                operation="select",
            )

            if not result.data:
                return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

            posts = result.data
            avg_likes = sum(p.get("like_count", 0) or 0 for p in posts) / len(posts)
            avg_comments = sum(p.get("comments_count", 0) or 0 for p in posts) / len(posts)

            engagement_rates = []
            for p in posts:
                likes = p.get("like_count", 0) or 0
                comments = p.get("comments_count", 0) or 0
                reach = p.get("reach", 0) or 0
                rate = (likes + comments) / reach if reach > 0 else 0.0
                engagement_rates.append(rate)

            avg_engagement = sum(engagement_rates) / len(engagement_rates) if engagement_rates else 0

            return {
                "avg_likes": round(avg_likes, 1),
                "avg_comments": round(avg_comments, 1),
                "avg_engagement_rate": round(avg_engagement, 4),
                "sample_size": len(posts),
            }

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping post performance fetch")
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}
        except Exception as e:
            logger.warning(f"Failed to fetch post performance: {e}")
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

    # ─────────────────────────────────────────
    # READ: Active Business Accounts
    # ─────────────────────────────────────────
    @staticmethod
    def get_active_business_accounts() -> list:
        """Fetch all active connected business accounts.

        Used by all schedulers to iterate over accounts.
        Filters: is_connected=True, connection_status='active'
        """
        if not supabase:
            return []

        try:
            result = execute(
                supabase.table("instagram_business_accounts")
                .select("id, username, name, instagram_business_id, account_type, followers_count")
                .eq("is_connected", True)
                .eq("connection_status", "active"),
                table="instagram_business_accounts",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping active accounts fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch active business accounts: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Unprocessed Comments
    # ─────────────────────────────────────────
    @staticmethod
    def get_unprocessed_comments(
        business_account_id: str, limit: int = 50, hours_back: int = 24
    ) -> list:
        """Fetch comments not yet processed by the engagement monitor.

        Filters: processed_by_automation=False, parent_comment_id IS NULL,
        created_at > now - hours_back. Returns oldest-first (FIFO).
        """
        if not supabase or not business_account_id:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

        try:
            result = execute(
                supabase.table("instagram_comments")
                .select(
                    "id, instagram_comment_id, text, author_username, "
                    "author_instagram_id, media_id, sentiment, category, "
                    "priority, like_count, created_at"
                )
                .eq("business_account_id", business_account_id)
                .eq("processed_by_automation", False)
                .is_("parent_comment_id", "null")
                .gte("created_at", cutoff)
                .order("created_at", desc=False)
                .limit(limit),
                table="instagram_comments",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping unprocessed comments fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch unprocessed comments for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # WRITE: Mark Comment Processed
    # ─────────────────────────────────────────
    @staticmethod
    def mark_comment_processed(
        comment_id: str, response_text: str = None, was_replied: bool = False
    ) -> bool:
        """Update instagram_comments to mark as processed by automation."""
        if not supabase or not comment_id:
            return False

        update_data = {"processed_by_automation": True}
        if was_replied and response_text:
            update_data["automated_response_sent"] = True
            update_data["response_text"] = response_text
            update_data["response_sent_at"] = datetime.now(timezone.utc).isoformat()

        try:
            execute(
                supabase.table("instagram_comments")
                .update(update_data)
                .eq("id", comment_id),
                table="instagram_comments",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to mark comment processed")
            return False
        except Exception as e:
            logger.error(f"Failed to mark comment {comment_id} as processed: {e}")
            return False

    # ─────────────────────────────────────────
    # READ: Post Context by UUID
    # ─────────────────────────────────────────
    @staticmethod
    def get_post_context_by_uuid(media_uuid: SupabaseUUID) -> dict:
        """Fetch post context using Supabase UUID (not Instagram media ID).

        Queries by instagram_media.id (UUID), unlike get_post_context which
        queries by instagram_media_id. Shared cache with get_post_context.

        Args:
            media_uuid: SupabaseUUID — Supabase primary key UUID.
                        NOT a Meta/Instagram media ID. Use get_post_context() for IG media IDs.
        """
        media_uuid = verify_id_space(media_uuid, SupabaseUUID)
        if not supabase or not media_uuid:
            return {}

        cache_key = f"post_ctx_uuid:{media_uuid}"

        if cache_key in post_context_cache:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="post_context_uuid_l1").inc()
            return post_context_cache[cache_key]

        cached = cache_get(cache_key)
        if cached:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="post_context_uuid_l2").inc()
            post_context_cache[cache_key] = cached
            cache_set(cache_key, cached, ttl=30)   # refresh L2 TTL so it doesn't serve stale data
            return cached

        from metrics import CACHE_MISSES
        CACHE_MISSES.labels(key_type="post_context_uuid").inc()

        try:
            result = execute(
                supabase.table("instagram_media")
                .select(
                    "instagram_media_id, caption, like_count, comments_count, "
                    "media_type, shares_count, reach"
                )
                .eq("id", media_uuid)
                .limit(1),
                table="instagram_media",
                operation="select",
            )

            if not result.data:
                return {}

            data = result.data[0]
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            reach = data.get("reach", 0) or 0
            data["engagement_rate"] = round((likes + comments) / reach, 4) if reach > 0 else 0.0

            post_context_cache[cache_key] = data
            cache_set(cache_key, data, ttl=30)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping post context (UUID) fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch post context for UUID {media_uuid}: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Recent Media IDs (Live Fetch Fallback)
    # ─────────────────────────────────────────
    @staticmethod
    def get_recent_media_ids(business_account_id: str, limit: int = 10) -> list:
        """Fetch recent media with both Supabase UUID and Instagram media ID."""
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("instagram_media")
                .select("id, instagram_media_id")
                .eq("business_account_id", business_account_id)
                .order("published_at", desc=True)
                .limit(limit),
                table="instagram_media",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping get_recent_media_ids")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch recent media ids for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # WRITE: Save Live Comments (Live Fetch Write-Through)
    # ─────────────────────────────────────────
    @staticmethod
    def save_live_comments(comments: list, business_account_id: str, media_id: str) -> int:
        """Upsert live comments from /post-comments backend proxy into instagram_comments.

        Args:
            comments: list from /post-comments response data[]
            media_id: Supabase UUID FK to instagram_media.id (NOT instagram_media_id)
        Returns count upserted.
        """
        if not supabase or not comments:
            return 0

        records = [
            {
                "instagram_comment_id": c["id"],
                "text": c.get("text", ""),
                "author_username": c.get("username", ""),
                "author_instagram_id": None,
                "media_id": media_id,
                "business_account_id": business_account_id,
                "created_at": c.get("timestamp"),
                "like_count": c.get("like_count", 0) or 0,
            }
            for c in comments if c.get("id")
        ]
        if not records:
            return 0

        try:
            result = execute(
                supabase.table("instagram_comments")
                .upsert(records, on_conflict="instagram_comment_id"),
                table="instagram_comments",
                operation="upsert",
            )
            return len(result.data or [])

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save live comments")
            return 0
        except Exception as e:
            logger.error(f"Failed to save live comments: {e}")
            return 0

    # ─────────────────────────────────────────
    # WRITE: Upsert Webhook Comment (Real-Time Path A)
    # ─────────────────────────────────────────
    @staticmethod
    def upsert_webhook_comment(
        instagram_comment_id: str,
        media_instagram_id: str,
        business_account_id: str,
        text: str,
        author_username: str,
        author_instagram_id: str,
        created_at: str,
        automated_response_sent: bool = False,
        response_text: str | None = None,
    ) -> bool:
        """Write a real-time webhook comment into instagram_comments.

        Sets processed_by_automation=True so the engagement monitor's
        get_unprocessed_comments() never picks up this event on the next cycle.
        Resolves media_instagram_id → Supabase UUID before insert.
        """
        if not supabase or not instagram_comment_id:
            return False

        try:
            media_result = execute(
                supabase.table("instagram_media")
                .select("id")
                .eq("instagram_media_id", media_instagram_id)
                .limit(1),
                table="instagram_media",
                operation="select",
            )
            media_uuid = media_result.data[0]["id"] if media_result.data else None

            record: dict = {
                "instagram_comment_id": instagram_comment_id,
                "text": (text or "")[:2000],
                "author_username": author_username or "",
                "author_instagram_id": author_instagram_id or None,
                "media_id": media_uuid,
                "business_account_id": business_account_id,
                "created_at": created_at,
                "processed_by_automation": True,
                "automated_response_sent": automated_response_sent,
            }
            if response_text:
                record["response_text"] = response_text[:2200]

            execute(
                supabase.table("instagram_comments")
                .upsert(record, on_conflict="instagram_comment_id"),
                table="instagram_comments",
                operation="upsert",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to upsert webhook comment")
            return False
        except Exception as e:
            logger.error(f"Failed to upsert webhook comment {instagram_comment_id}: {e}")
            return False
