"""
Supabase Service Layer
======================
Handles all Supabase reads (context fetching) and writes (audit logging).
All queries match the REAL database schema (Supabase is source of truth).

Features:
  - Retry with exponential backoff (tenacity)
  - Circuit breaker (pybreaker) — fail fast when DB is down
  - Redis caching for frequent queries (distributed, survives restarts)
  - Graceful fallback when Redis is unavailable
"""

import os
import json
import uuid
from datetime import datetime, timezone

import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pybreaker import CircuitBreaker, CircuitBreakerError

from config import supabase, logger


# ================================
# Redis Cache (distributed)
# ================================
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

try:
    _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=2)
    _redis.ping()
    _redis_available = True
    logger.info(f"Redis connected at {REDIS_HOST}:{REDIS_PORT}")
except Exception:
    _redis = None
    _redis_available = False
    logger.warning("Redis unavailable — caching disabled, queries go direct to Supabase")


def _cache_get(key: str):
    """Get value from Redis cache. Returns None on miss or Redis failure."""
    if not _redis_available:
        return None
    try:
        cached = _redis.get(key)
        return json.loads(cached) if cached else None
    except Exception:
        return None


def _cache_set(key: str, data, ttl: int = 60):
    """Set value in Redis cache. Silently fails if Redis unavailable."""
    if not _redis_available:
        return
    try:
        _redis.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


# ================================
# Circuit Breaker + Retry
# ================================
db_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)


@db_breaker
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
def _execute_query(query):
    """Execute a Supabase query with retry + circuit breaker.

    - Tenacity retries transient failures (3 attempts, exponential backoff)
    - Circuit breaker opens after 5 consecutive failures, fails fast for 30s
    """
    return query.execute()


# ================================
# Helpers
# ================================
def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def is_redis_healthy() -> bool:
    """Check Redis connectivity for health endpoint."""
    if not _redis:
        return False
    try:
        return _redis.ping()
    except Exception:
        return False


# ================================
# Supabase Service
# ================================
class SupabaseService:
    """Handles all Supabase reads (context fetching) and writes (audit logging).

    All queries match the REAL Supabase schema:
      - instagram_media: caption, like_count, comments_count, shares_count, reach, media_type, published_at
      - instagram_business_accounts: username, name, account_type, followers_count, biography, category
      - instagram_comments: text, sentiment, category, priority, author_username, created_at
      - instagram_dm_conversations + instagram_dm_messages: two-table DM structure
      - audit_log: event_type, action, resource_type, resource_id (UUID), details (jsonb)
    """

    # --------------------------------------------------
    # READ: Post Context
    # --------------------------------------------------
    @staticmethod
    def get_post_context(post_id: str) -> dict:
        """Fetch post caption and engagement metrics from instagram_media.

        Note: engagement_rate is COMPUTED (column does not exist in DB).
        Formula: (like_count + comments_count) / reach if reach > 0
        """
        if not supabase or not post_id:
            return {}

        # Check cache first
        cache_key = f"post_ctx:{post_id}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("caption, like_count, comments_count, media_type, shares_count, reach")
                .eq("instagram_media_id", post_id)
                .limit(1)
            )

            if not result.data:
                return {}

            data = result.data[0]

            # Compute engagement_rate (column does not exist in DB)
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            reach = data.get("reach", 0) or 0
            data["engagement_rate"] = round((likes + comments) / reach, 4) if reach > 0 else 0.0

            _cache_set(cache_key, data, ttl=30)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping post context fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch post context for {post_id}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Account Info
    # --------------------------------------------------
    @staticmethod
    def get_account_info(business_account_id: str) -> dict:
        """Fetch account info from instagram_business_accounts.

        Real columns: username, name, account_type, followers_count, biography, category
        (instagram_business_username does NOT exist — use 'username')
        """
        if not supabase or not business_account_id:
            return {}

        cache_key = f"account:{business_account_id}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        try:
            result = _execute_query(
                supabase.table("instagram_business_accounts")
                .select("username, name, account_type, followers_count, biography, category")
                .eq("id", business_account_id)
                .limit(1)
            )

            if not result.data:
                return {}

            data = result.data[0]
            _cache_set(cache_key, data, ttl=60)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping account info fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch account info for {business_account_id}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Recent Comments
    # --------------------------------------------------
    @staticmethod
    def get_recent_comments(business_account_id: str, limit: int = 10) -> list:
        """Fetch recent comments for pattern context.

        Real columns: text (NOT comment_text), sentiment, category, priority, author_username
        (status column does NOT exist)
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = _execute_query(
                supabase.table("instagram_comments")
                .select("text, sentiment, category, priority, author_username, created_at")
                .eq("business_account_id", business_account_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping recent comments fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch recent comments: {e}")
            return []

    # --------------------------------------------------
    # READ: DM History (two-table structure)
    # --------------------------------------------------
    @staticmethod
    def get_dm_history(sender_id: str, business_account_id: str, limit: int = 5) -> list:
        """Fetch DM conversation history for a sender.

        Real DB has TWO tables (instagram_dms does NOT exist):
          1. instagram_dm_conversations — thread-level metadata
          2. instagram_dm_messages — individual messages

        Returns list of dicts with backward-compatible keys:
          message_text, direction (inbound/outbound), status, created_at, message_type
        """
        if not supabase or not sender_id:
            return []

        try:
            # Step 1: Find conversation by customer_instagram_id + business_account_id
            conv_result = _execute_query(
                supabase.table("instagram_dm_conversations")
                .select("id, conversation_status, within_window, window_expires_at")
                .eq("business_account_id", business_account_id)
                .eq("customer_instagram_id", sender_id)
                .limit(1)
            )

            if not conv_result.data:
                return []

            conversation = conv_result.data[0]
            conversation_id = conversation["id"]

            # Step 2: Fetch messages from that conversation
            msg_result = _execute_query(
                supabase.table("instagram_dm_messages")
                .select("message_text, message_type, is_from_business, sent_at, send_status")
                .eq("conversation_id", conversation_id)
                .order("sent_at", desc=True)
                .limit(limit)
            )

            # Map to backward-compatible format
            messages = []
            for m in (msg_result.data or []):
                messages.append({
                    "message_text": m.get("message_text", ""),
                    "direction": "outbound" if m.get("is_from_business") else "inbound",
                    "status": m.get("send_status", "unknown"),
                    "created_at": m.get("sent_at", ""),
                    "message_type": m.get("message_type", "text"),
                })

            return messages

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DM history fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch DM history for {sender_id}: {e}")
            return []

    # --------------------------------------------------
    # READ: DM Conversation Context
    # --------------------------------------------------
    @staticmethod
    def get_dm_conversation_context(sender_id: str, business_account_id: str) -> dict:
        """Fetch conversation-level metadata (window status, message count).

        Useful for verifying 24h window status from DB rather than trusting N8N payload.
        """
        if not supabase or not sender_id:
            return {}

        try:
            result = _execute_query(
                supabase.table("instagram_dm_conversations")
                .select("within_window, window_expires_at, conversation_status, message_count, last_message_at")
                .eq("business_account_id", business_account_id)
                .eq("customer_instagram_id", sender_id)
                .limit(1)
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DM conversation context fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch DM conversation context for {sender_id}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Recent Post Performance
    # --------------------------------------------------
    @staticmethod
    def get_recent_post_performance(business_account_id: str, limit: int = 10) -> dict:
        """Fetch recent posts to calculate average engagement for benchmarking.

        Note: engagement_rate is COMPUTED per-post (column does not exist in DB).
        """
        if not supabase or not business_account_id:
            return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("like_count, comments_count, shares_count, reach")
                .eq("business_account_id", business_account_id)
                .order("published_at", desc=True)
                .limit(limit)
            )

            if not result.data:
                return {"avg_likes": 0, "avg_comments": 0, "avg_engagement_rate": 0}

            posts = result.data

            # Compute engagement_rate per post, then average
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

    # --------------------------------------------------
    # WRITE: Audit Log
    # --------------------------------------------------
    @staticmethod
    def log_decision(
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        details: dict,
        ip_address: str = "",
    ) -> bool:
        """Log agent decision to audit_log table.

        Real audit_log schema:
          - event_type (varchar) — NOT 'event'
          - action (varchar) — top-level column, NOT nested in data
          - resource_type (varchar)
          - resource_id (UUID) — must be valid UUID or None
          - details (jsonb) — NOT 'data'
          - user_id (UUID) — FK to auth.users
          - ip_address (inet)
          - success (boolean)
        """
        if not supabase:
            logger.warning("Supabase not connected — skipping audit log")
            return False

        try:
            # Handle resource_id: must be valid UUID or None
            valid_resource_id = resource_id if _is_valid_uuid(resource_id) else None
            enriched_details = dict(details)
            if resource_id and not valid_resource_id:
                enriched_details["original_resource_id"] = resource_id

            # Handle user_id: must be valid UUID or None
            valid_user_id = user_id if _is_valid_uuid(user_id) else None
            if user_id and not valid_user_id:
                enriched_details["original_user_id"] = user_id

            row = {
                "event_type": event_type,
                "action": action,
                "resource_type": resource_type,
                "resource_id": valid_resource_id,
                "details": enriched_details,
                "user_id": valid_user_id,
                "ip_address": ip_address or None,
                "success": True,
            }

            _execute_query(supabase.table("audit_log").insert(row))
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to log decision to audit_log")
            return False
        except Exception as e:
            logger.error(f"Failed to log decision to audit_log: {e}")
            return False
