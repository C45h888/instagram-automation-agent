import time
from datetime import datetime, timezone
from config import supabase, logger


class SupabaseService:
    """Handles all Supabase reads (context fetching) and writes (audit logging)."""

    @staticmethod
    def get_post_context(post_id: str) -> dict:
        """Fetch post caption and engagement metrics from instagram_media."""
        if not supabase or not post_id:
            return {}
        try:
            result = supabase.table("instagram_media") \
                .select("caption, like_count, comments_count, media_type, engagement_rate") \
                .eq("instagram_media_id", post_id) \
                .limit(1) \
                .execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.warning(f"Failed to fetch post context for {post_id}: {e}")
            return {}

    @staticmethod
    def get_account_info(business_account_id: str) -> dict:
        """Fetch account info from instagram_business_accounts."""
        if not supabase or not business_account_id:
            return {}
        try:
            result = supabase.table("instagram_business_accounts") \
                .select("instagram_business_username, name, username, followers_count") \
                .eq("id", business_account_id) \
                .limit(1) \
                .execute()
            return result.data[0] if result.data else {}
        except Exception as e:
            logger.warning(f"Failed to fetch account info for {business_account_id}: {e}")
            return {}

    @staticmethod
    def get_recent_comments(business_account_id: str, limit: int = 10) -> list:
        """Fetch recent comments for pattern context."""
        if not supabase or not business_account_id:
            return []
        try:
            result = supabase.table("instagram_comments") \
                .select("comment_text, status, created_at") \
                .eq("business_account_id", business_account_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to fetch recent comments: {e}")
            return []

    @staticmethod
    def get_dm_history(sender_id: str, business_account_id: str, limit: int = 5) -> list:
        """Fetch DM conversation history for a sender."""
        if not supabase or not sender_id:
            return []
        try:
            result = supabase.table("instagram_dms") \
                .select("message_text, direction, status, created_at") \
                .eq("business_account_id", business_account_id) \
                .eq("recipient_id", sender_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to fetch DM history for {sender_id}: {e}")
            return []

    @staticmethod
    def get_recent_post_performance(business_account_id: str, limit: int = 10) -> dict:
        """Fetch recent posts to calculate average engagement for benchmarking."""
        if not supabase or not business_account_id:
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}
        try:
            result = supabase.table("instagram_media") \
                .select("like_count, comments_count, engagement_rate") \
                .eq("business_account_id", business_account_id) \
                .order("published_at", desc=True) \
                .limit(limit) \
                .execute()

            if not result.data:
                return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

            posts = result.data
            avg_likes = sum(p.get("like_count", 0) or 0 for p in posts) / len(posts)
            avg_comments = sum(p.get("comments_count", 0) or 0 for p in posts) / len(posts)
            avg_engagement = sum(p.get("engagement_rate", 0) or 0 for p in posts) / len(posts)

            return {
                "avg_likes": round(avg_likes, 1),
                "avg_comments": round(avg_comments, 1),
                "avg_engagement_rate": round(avg_engagement, 4),
                "sample_size": len(posts)
            }
        except Exception as e:
            logger.warning(f"Failed to fetch post performance: {e}")
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

    @staticmethod
    def log_decision(
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        details: dict,
        ip_address: str = ""
    ) -> bool:
        """Log agent decision to audit_log table."""
        if not supabase:
            logger.warning("Supabase not connected - skipping audit log")
            return False
        try:
            supabase.table("audit_log").insert({
                "event": event_type,
                "user_id": user_id or None,
                "ip_address": ip_address or None,
                "data": {
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    **details
                }
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to log decision to audit_log: {e}")
            return False
