"""
Content Service
===============
Assets, scheduled posts, and the content scheduler lifecycle.
Used by: content scheduler pipelines.

All methods: @staticmethod
"""

from datetime import datetime, timezone, timedelta
from pybreaker import CircuitBreakerError

from ._infra import execute, db_breaker, supabase, logger


class ContentService:
    """Assets, scheduled posts, and post-publishing lifecycle."""

    # ─────────────────────────────────────────
    # READ: Eligible Assets
    # ─────────────────────────────────────────
    @staticmethod
    def get_eligible_assets(business_account_id: str, limit: int = 50) -> list:
        """Fetch assets eligible for posting (not posted in last 7 days).

        Returns never-posted first, then oldest-posted.
        """
        if not supabase or not business_account_id:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        try:
            never_posted = execute(
                supabase.table("instagram_assets")
                .select(
                    "id, storage_path, title, description, tags, media_type, "
                    "last_posted, post_count, avg_engagement, created_at"
                )
                .eq("business_account_id", business_account_id)
                .eq("is_active", True)
                .is_("last_posted", "null")
                .limit(limit),
                table="instagram_assets",
                operation="select",
            )

            old_posted = execute(
                supabase.table("instagram_assets")
                .select(
                    "id, storage_path, title, description, tags, media_type, "
                    "last_posted, post_count, avg_engagement, created_at"
                )
                .eq("business_account_id", business_account_id)
                .eq("is_active", True)
                .lt("last_posted", cutoff)
                .order("last_posted", desc=False)
                .limit(limit),
                table="instagram_assets",
                operation="select",
            )

            results = (never_posted.data or []) + (old_posted.data or [])
            return results[:limit]

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping eligible assets fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch eligible assets for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Recent Post Tags
    # ─────────────────────────────────────────
    @staticmethod
    def get_recent_post_tags(business_account_id: str, limit: int = 3) -> list:
        """Fetch hashtags from recent published posts for diversity scoring."""
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("scheduled_posts")
                .select("generated_hashtags")
                .eq("business_account_id", business_account_id)
                .eq("status", "published")
                .order("created_at", desc=True)
                .limit(limit),
                table="scheduled_posts",
                operation="select",
            )

            tags_list = []
            for row in (result.data or []):
                hashtags = row.get("generated_hashtags")
                if hashtags and isinstance(hashtags, list):
                    tags_list.append(hashtags)
            return tags_list

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping recent post tags fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch recent post tags: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: Posts Today Count
    # ─────────────────────────────────────────
    @staticmethod
    def get_posts_today_count(business_account_id: str) -> int:
        """Count posts created today for daily cap enforcement.

        Includes approved + publishing + published: the full pipeline.
        'approved'  = scheduled by content scheduler, not yet picked up
        'publishing'= picked up by queue worker, transition in progress
        'published' = confirmed live on Instagram

        'publishing' is counted to prevent race conditions where the scheduler
        counts 0 (approved post not yet picked up) and schedules a second post
        before the first transitions to 'published'.
        """
        if not supabase or not business_account_id:
            return 0

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        try:
            result = execute(
                supabase.table("scheduled_posts")
                .select("id", count="exact")
                .eq("business_account_id", business_account_id)
                .in_("status", ["approved", "publishing", "published"])
                .gte("created_at", today_start),
                table="scheduled_posts",
                operation="select",
            )
            return result.count or 0

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping posts today count")
            return 0
        except Exception as e:
            logger.warning(f"Failed to get posts today count: {e}")
            return 0

    # ─────────────────────────────────────────
    # WRITE: Create Scheduled Post
    # ─────────────────────────────────────────
    @staticmethod
    def create_scheduled_post(
        business_account_id: str,
        run_id: str,
        asset: dict,
        asset_url: str,
        selection_score: float,
        selection_factors: dict,
        caption_data: dict,
        evaluation_data: dict,
    ) -> dict:
        """Insert a new scheduled post with caption and evaluation results."""
        if not supabase:
            return {}

        from services.validation import PostSelectionFactors, AgentModifications

        if selection_factors:
            try:
                PostSelectionFactors(**selection_factors)
            except Exception as e:
                logger.warning(f"Invalid selection_factors, writing anyway: {e}")

        mods = evaluation_data.get("modifications")
        if mods and isinstance(mods, dict):
            try:
                AgentModifications(**mods)
            except Exception as e:
                logger.warning(f"Invalid agent_modifications, writing anyway: {e}")

        row = {
            "business_account_id": business_account_id,
            "run_id": run_id,
            "asset_id": asset.get("id"),
            "asset_storage_path": asset.get("storage_path", ""),
            "asset_url": asset_url,
            "selection_score": selection_score,
            "selection_factors": selection_factors,
            "generated_caption": caption_data.get("full_caption", ""),
            "caption_hook": caption_data.get("hook", ""),
            "caption_body": caption_data.get("body", ""),
            "caption_cta": caption_data.get("cta", ""),
            "generated_hashtags": caption_data.get("hashtags", []),
            "agent_approved": evaluation_data.get("approved", False),
            "agent_quality_score": evaluation_data.get("quality_score", 0),
            "agent_reasoning": evaluation_data.get("reasoning", ""),
            "agent_modifications": evaluation_data.get("modifications"),
            "status": "approved" if evaluation_data.get("approved") else "rejected",
        }

        try:
            result = execute(
                supabase.table("scheduled_posts").insert(row),
                table="scheduled_posts",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create scheduled post")
            return {}
        except Exception as e:
            logger.error(f"Failed to create scheduled post: {e}")
            return {}

    # ─────────────────────────────────────────
    # WRITE: Update Scheduled Post Status
    # ─────────────────────────────────────────
    @staticmethod
    def update_scheduled_post_status(
        post_id: str, status: str, extra_fields: dict = None
    ) -> bool:
        """Update scheduled post status with optional extra fields.

        State transitions: approved → publishing → published | failed
        """
        if not supabase or not post_id:
            return False

        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_fields:
            update_data.update(extra_fields)

        try:
            execute(
                supabase.table("scheduled_posts")
                .update(update_data)
                .eq("id", post_id),
                table="scheduled_posts",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update scheduled post status")
            return False
        except Exception as e:
            logger.error(f"Failed to update scheduled post {post_id}: {e}")
            return False

    # ─────────────────────────────────────────
    # WRITE: Update Asset After Post
    # ─────────────────────────────────────────
    @staticmethod
    def update_asset_after_post(asset_id: str) -> bool:
        """Increment post_count and set last_posted after successful publish.

        Read-modify-write: fetches current post_count before incrementing.
        """
        if not supabase or not asset_id:
            return False

        try:
            current = execute(
                supabase.table("instagram_assets")
                .select("post_count")
                .eq("id", asset_id)
                .limit(1),
                table="instagram_assets",
                operation="select",
            )

            current_count = 0
            if current.data:
                current_count = current.data[0].get("post_count", 0) or 0

            execute(
                supabase.table("instagram_assets")
                .update({
                    "last_posted": datetime.now(timezone.utc).isoformat(),
                    "post_count": current_count + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", asset_id),
                table="instagram_assets",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update asset after post")
            return False
        except Exception as e:
            logger.error(f"Failed to update asset {asset_id} after post: {e}")
            return False
