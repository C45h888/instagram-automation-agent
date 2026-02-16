"""
Supabase Service Layer
======================
Handles all Supabase reads (context fetching) and writes (audit logging).
All queries match the REAL database schema (Supabase is source of truth).

Features:
  - Retry with exponential backoff (tenacity)
  - Circuit breaker (pybreaker) — fail fast when DB is down
  - Two-tier caching: L1 in-memory (cachetools) + L2 Redis (distributed)
  - Graceful fallback when Redis is unavailable
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta

import redis
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pybreaker import CircuitBreaker, CircuitBreakerError

from config import supabase, logger
from routes.metrics import DB_QUERY_COUNT, CACHE_HITS, CACHE_MISSES


# ================================
# In-Memory L1 Cache (cachetools)
# ================================
# L1 avoids Redis round-trips for hot data (~2-5ms saved per hit)
# TTLs match Redis TTLs so expiration is consistent
_post_context_cache: TTLCache = TTLCache(maxsize=100, ttl=30)
_account_info_cache: TTLCache = TTLCache(maxsize=50, ttl=60)
_attribution_model_cache: TTLCache = TTLCache(maxsize=20, ttl=300)  # 5 min for model weights


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
def _execute_query(query, table: str = "unknown", operation: str = "select"):
    """Execute a Supabase query with retry + circuit breaker.

    - Tenacity retries transient failures (3 attempts, exponential backoff)
    - Circuit breaker opens after 5 consecutive failures, fails fast for 30s
    - Tracks DB query metrics
    """
    DB_QUERY_COUNT.labels(table=table, operation=operation).inc()
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

        Caching: L1 in-memory (30s TTL) -> L2 Redis (30s TTL) -> Supabase
        """
        if not supabase or not post_id:
            return {}

        cache_key = f"post_ctx:{post_id}"

        # L1: Check in-memory cache first (fastest)
        if cache_key in _post_context_cache:
            logger.debug(f"L1 cache hit for {cache_key}")
            CACHE_HITS.labels(key_type="post_context_l1").inc()
            return _post_context_cache[cache_key]

        # L2: Check Redis cache
        cached = _cache_get(cache_key)
        if cached:
            logger.debug(f"L2 cache hit for {cache_key}")
            CACHE_HITS.labels(key_type="post_context_l2").inc()
            _post_context_cache[cache_key] = cached  # Populate L1
            return cached

        # Cache miss - query DB
        CACHE_MISSES.labels(key_type="post_context").inc()

        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("caption, like_count, comments_count, media_type, shares_count, reach")
                .eq("instagram_media_id", post_id)
                .limit(1),
                table="instagram_media",
                operation="select"
            )

            if not result.data:
                return {}

            data = result.data[0]

            # Compute engagement_rate (column does not exist in DB)
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            reach = data.get("reach", 0) or 0
            data["engagement_rate"] = round((likes + comments) / reach, 4) if reach > 0 else 0.0

            # Write to both cache layers
            _post_context_cache[cache_key] = data
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

        Caching: L1 in-memory (60s TTL) -> L2 Redis (60s TTL) -> Supabase
        """
        if not supabase or not business_account_id:
            return {}

        cache_key = f"account:{business_account_id}"

        # L1: Check in-memory cache first (fastest)
        if cache_key in _account_info_cache:
            logger.debug(f"L1 cache hit for {cache_key}")
            CACHE_HITS.labels(key_type="account_info_l1").inc()
            return _account_info_cache[cache_key]

        # L2: Check Redis cache
        cached = _cache_get(cache_key)
        if cached:
            logger.debug(f"L2 cache hit for {cache_key}")
            CACHE_HITS.labels(key_type="account_info_l2").inc()
            _account_info_cache[cache_key] = cached  # Populate L1
            return cached

        # Cache miss - query DB
        CACHE_MISSES.labels(key_type="account_info").inc()

        try:
            result = _execute_query(
                supabase.table("instagram_business_accounts")
                .select("username, name, account_type, followers_count, biography, category")
                .eq("id", business_account_id)
                .limit(1),
                table="instagram_business_accounts",
                operation="select"
            )

            if not result.data:
                return {}

            data = result.data[0]
            # Write to both cache layers
            _account_info_cache[cache_key] = data
            _cache_set(cache_key, data, ttl=60)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping account info fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch account info for {business_account_id}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Resolve IG Business ID → Supabase UUID
    # --------------------------------------------------
    @staticmethod
    def get_account_uuid_by_instagram_id(instagram_business_id: str) -> str | None:
        """Resolve Instagram Business ID (numeric string) → Supabase UUID.

        Queries instagram_business_accounts.instagram_business_id (unique varchar).
        Used by webhook handlers: Meta sends entry.id as the IG numeric ID but all
        backend proxy calls require the Supabase UUID (instagram_business_accounts.id).
        Returns None if not found.
        """
        if not supabase or not instagram_business_id:
            return None
        try:
            result = _execute_query(
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
                .limit(limit),
                table="instagram_comments",
                operation="select"
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
                .limit(1),
                table="instagram_dm_conversations",
                operation="select"
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
                .limit(limit),
                table="instagram_dm_messages",
                operation="select"
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
                .limit(1),
                table="instagram_dm_conversations",
                operation="select"
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
                .limit(limit),
                table="instagram_media",
                operation="select"
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
    # READ: Active Business Accounts (Engagement Monitor)
    # --------------------------------------------------
    @staticmethod
    def get_active_business_accounts() -> list:
        """Fetch all active connected business accounts.

        Used by engagement monitor to iterate over all accounts.
        Returns list of dicts with id, username, name, instagram_business_id, account_type.
        """
        if not supabase:
            return []

        try:
            result = _execute_query(
                supabase.table("instagram_business_accounts")
                .select("id, username, name, instagram_business_id, account_type, followers_count")
                .eq("is_connected", True)
                .eq("connection_status", "active"),
                table="instagram_business_accounts",
                operation="select"
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping active accounts fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch active business accounts: {e}")
            return []

    # --------------------------------------------------
    # READ: Unprocessed Comments (Engagement Monitor)
    # --------------------------------------------------
    @staticmethod
    def get_unprocessed_comments(business_account_id: str, limit: int = 50, hours_back: int = 24) -> list:
        """Fetch comments not yet processed by the engagement monitor.

        Filters:
          - business_account_id matches
          - processed_by_automation = false
          - created_at > now - hours_back
          - parent_comment_id IS NULL (skip replies-to-replies)

        Returns oldest-first (FIFO) for fair processing.
        """
        if not supabase or not business_account_id:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

        try:
            result = _execute_query(
                supabase.table("instagram_comments")
                .select("id, instagram_comment_id, text, author_username, "
                        "author_instagram_id, media_id, sentiment, category, "
                        "priority, like_count, created_at")
                .eq("business_account_id", business_account_id)
                .eq("processed_by_automation", False)
                .is_("parent_comment_id", "null")
                .gte("created_at", cutoff)
                .order("created_at", desc=False)
                .limit(limit),
                table="instagram_comments",
                operation="select"
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping unprocessed comments fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch unprocessed comments for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # WRITE: Mark Comment Processed (Engagement Monitor)
    # --------------------------------------------------
    @staticmethod
    def mark_comment_processed(
        comment_id: str,
        response_text: str = None,
        was_replied: bool = False,
    ) -> bool:
        """Update instagram_comments to mark as processed by automation.

        Sets processed_by_automation = true.
        If replied, also sets automated_response_sent, response_text, response_sent_at.
        """
        if not supabase or not comment_id:
            return False

        update_data = {"processed_by_automation": True}
        if was_replied and response_text:
            update_data["automated_response_sent"] = True
            update_data["response_text"] = response_text
            update_data["response_sent_at"] = datetime.now(timezone.utc).isoformat()

        try:
            _execute_query(
                supabase.table("instagram_comments")
                .update(update_data)
                .eq("id", comment_id),
                table="instagram_comments",
                operation="update"
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to mark comment processed")
            return False
        except Exception as e:
            logger.error(f"Failed to mark comment {comment_id} as processed: {e}")
            return False

    # --------------------------------------------------
    # READ: Post Context by UUID (Engagement Monitor)
    # --------------------------------------------------
    @staticmethod
    def get_post_context_by_uuid(media_uuid: str) -> dict:
        """Fetch post context using Supabase UUID (not Instagram media ID).

        The instagram_comments table has media_id (FK to instagram_media.id),
        which is the Supabase UUID. Existing get_post_context queries by
        instagram_media_id. This method queries by id (UUID) instead.

        Caching: L1 in-memory (30s TTL) -> L2 Redis (30s TTL) -> Supabase
        """
        if not supabase or not media_uuid:
            return {}

        cache_key = f"post_ctx_uuid:{media_uuid}"

        # L1: Check in-memory cache
        if cache_key in _post_context_cache:
            CACHE_HITS.labels(key_type="post_context_uuid_l1").inc()
            return _post_context_cache[cache_key]

        # L2: Check Redis cache
        cached = _cache_get(cache_key)
        if cached:
            CACHE_HITS.labels(key_type="post_context_uuid_l2").inc()
            _post_context_cache[cache_key] = cached
            return cached

        CACHE_MISSES.labels(key_type="post_context_uuid").inc()

        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("instagram_media_id, caption, like_count, comments_count, "
                        "media_type, shares_count, reach")
                .eq("id", media_uuid)
                .limit(1),
                table="instagram_media",
                operation="select"
            )

            if not result.data:
                return {}

            data = result.data[0]

            # Compute engagement_rate (column does not exist in DB)
            likes = data.get("like_count", 0) or 0
            comments = data.get("comments_count", 0) or 0
            reach = data.get("reach", 0) or 0
            data["engagement_rate"] = round((likes + comments) / reach, 4) if reach > 0 else 0.0

            # Write to both cache layers
            _post_context_cache[cache_key] = data
            _cache_set(cache_key, data, ttl=30)
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping post context (UUID) fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch post context for UUID {media_uuid}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Recent Media IDs (Live Fetch Fallback)
    # --------------------------------------------------
    @staticmethod
    def get_recent_media_ids(business_account_id: str, limit: int = 10) -> list:
        """Fetch recent media with both Supabase UUID and Instagram media ID.

        Used by engagement_monitor fallback to know which posts to poll for live comments.
        Returns: [{"id": supabase_uuid, "instagram_media_id": "..."}]
        """
        if not supabase or not business_account_id:
            return []
        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("id, instagram_media_id")
                .eq("business_account_id", business_account_id)
                .order("published_at", desc=True)
                .limit(limit),
                table="instagram_media",
                operation="select"
            )
            return result.data or []
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping get_recent_media_ids")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch recent media ids for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # WRITE: Save Live Comments (Live Fetch Write-Through)
    # --------------------------------------------------
    @staticmethod
    def save_live_comments(comments: list, business_account_id: str, media_id: str) -> int:
        """Upsert live comments (from /post-comments backend proxy) into instagram_comments.

        Args:
            comments: list of dicts from /post-comments response data[]
                      fields: id, text, timestamp, username, like_count, replies_count
            media_id: Supabase UUID for instagram_media FK (NOT instagram_media_id)
        Returns count upserted.
        """
        if not supabase or not comments:
            return 0
        records = [
            {
                "instagram_comment_id": c["id"],
                "text": c.get("text", ""),
                "author_username": c.get("username", ""),
                "author_instagram_id": None,        # not returned by /post-comments
                "media_id": media_id,               # Supabase UUID FK
                "business_account_id": business_account_id,
                "created_at": c.get("timestamp"),
                "like_count": c.get("like_count", 0) or 0,
                "processed_by_automation": False,   # fresh — not yet processed
            }
            for c in comments if c.get("id")
        ]
        if not records:
            return 0
        try:
            result = _execute_query(
                supabase.table("instagram_comments")
                .upsert(records, on_conflict="instagram_comment_id"),
                table="instagram_comments",
                operation="upsert"
            )
            return len(result.data or [])
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save live comments")
            return 0
        except Exception as e:
            logger.error(f"Failed to save live comments: {e}")
            return 0

    # --------------------------------------------------
    # WRITE: Save Live Conversations (Live Fetch Write-Through)
    # --------------------------------------------------
    @staticmethod
    def save_live_conversations(conversations: list, business_account_id: str) -> int:
        """Upsert DM conversations (from /conversations backend proxy) into instagram_dm_conversations.

        Args:
            conversations: list of dicts from /conversations response data[]
                           fields: id, participants, last_message_at, message_count, messaging_window
        Returns count upserted.
        """
        from datetime import timedelta
        if not supabase or not conversations:
            return 0
        now = datetime.now(timezone.utc)
        records = []
        for conv in conversations:
            participants = conv.get("participants", [])
            customer_id = participants[0]["id"] if participants else None
            if not customer_id:
                continue
            mw = conv.get("messaging_window", {})
            is_open = mw.get("is_open", False)
            hours_rem = mw.get("hours_remaining")
            window_expires_at = (
                (now + timedelta(hours=hours_rem)).isoformat()
                if is_open and hours_rem is not None else None
            )
            records.append({
                "customer_instagram_id": customer_id,
                "business_account_id": business_account_id,
                "instagram_thread_id": conv["id"],   # DB column, not conversation_id
                "within_window": is_open,
                "window_expires_at": window_expires_at,
                "last_message_at": conv.get("last_message_at"),
                "message_count": conv.get("message_count", 0) or 0,
                "conversation_status": "active",     # DB check: active/archived/muted/blocked/pending
            })
        if not records:
            return 0
        try:
            result = _execute_query(
                supabase.table("instagram_dm_conversations")
                .upsert(records, on_conflict="instagram_thread_id"),
                table="instagram_dm_conversations",
                operation="upsert"
            )
            return len(result.data or [])
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save live conversations")
            return 0
        except Exception as e:
            logger.error(f"Failed to save live conversations: {e}")
            return 0

    # --------------------------------------------------
    # WRITE: Save Live Conversation Messages (Live Fetch Write-Through)
    # --------------------------------------------------
    @staticmethod
    def save_live_conversation_messages(
        messages: list,
        conversation_id: str,
        business_account_id: str,
        business_ig_user_id: str,
    ) -> int:
        """Upsert DM messages (from /conversation-messages backend proxy) into instagram_dm_messages.

        Args:
            messages: list of dicts — fields: id, message, from{id,username}, created_time
            business_ig_user_id: Instagram numeric user ID of the business account
                                 Used to determine is_from_business flag.
        Returns count upserted.
        """
        if not supabase or not messages:
            return 0
        records = [
            {
                "instagram_message_id": m["id"],        # DB unique column (not message_id)
                "message_text": m.get("message", ""),
                "conversation_id": conversation_id,     # UUID FK (nullable) — passed by caller
                "business_account_id": business_account_id,
                "is_from_business": m.get("from", {}).get("id") == business_ig_user_id,
                "recipient_instagram_id": m.get("from", {}).get("id") or "",  # NOT NULL in DB
                "sent_at": m.get("created_time"),
                "send_status": "delivered",             # DB check: pending/sent/delivered/failed/rejected
            }
            for m in messages if m.get("id")
        ]
        if not records:
            return 0
        try:
            result = _execute_query(
                supabase.table("instagram_dm_messages")
                .upsert(records, on_conflict="instagram_message_id"),
                table="instagram_dm_messages",
                operation="upsert"
            )
            return len(result.data or [])
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save live conversation messages")
            return 0
        except Exception as e:
            logger.error(f"Failed to save live conversation messages: {e}")
            return 0

    # --------------------------------------------------
    # READ: Granted UGC Permissions (UGC Auto-Repost)
    # --------------------------------------------------
    @staticmethod
    def get_granted_ugc_permissions(business_account_id: str) -> list:
        """Fetch ugc_permissions with status='granted' not yet reposted.

        The backend /repost-ugc sets status='reposted' after publish,
        so filtering on 'granted' naturally excludes already-reposted records.
        """
        if not supabase or not business_account_id:
            return []
        try:
            result = _execute_query(
                supabase.table("ugc_permissions")
                .select("id, ugc_content_id")        # DB FK is ugc_content_id, no username column
                .eq("business_account_id", business_account_id)
                .eq("status", "granted"),
                table="ugc_permissions",
                operation="select"
            )
            return result.data or []
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping get_granted_ugc_permissions")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch granted UGC permissions: {e}")
            return []

    # --------------------------------------------------
    # READ: Eligible Assets (Content Scheduler)
    # --------------------------------------------------
    @staticmethod
    def get_eligible_assets(business_account_id: str, limit: int = 50) -> list:
        """Fetch assets eligible for posting (not posted in last 7 days).

        Filters:
          - business_account_id matches
          - is_active = true
          - last_posted IS NULL or last_posted < 7 days ago

        Returns never-posted first, then oldest-posted.
        """
        if not supabase or not business_account_id:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        try:
            # Assets never posted
            never_posted = _execute_query(
                supabase.table("instagram_assets")
                .select("id, storage_path, title, description, tags, media_type, "
                        "last_posted, post_count, avg_engagement, created_at")
                .eq("business_account_id", business_account_id)
                .eq("is_active", True)
                .is_("last_posted", "null")
                .limit(limit),
                table="instagram_assets",
                operation="select"
            )

            # Assets posted more than 7 days ago
            old_posted = _execute_query(
                supabase.table("instagram_assets")
                .select("id, storage_path, title, description, tags, media_type, "
                        "last_posted, post_count, avg_engagement, created_at")
                .eq("business_account_id", business_account_id)
                .eq("is_active", True)
                .lt("last_posted", cutoff)
                .order("last_posted", desc=False)
                .limit(limit),
                table="instagram_assets",
                operation="select"
            )

            results = (never_posted.data or []) + (old_posted.data or [])
            return results[:limit]

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping eligible assets fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch eligible assets for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # READ: Recent Post Tags (Content Scheduler)
    # --------------------------------------------------
    @staticmethod
    def get_recent_post_tags(business_account_id: str, limit: int = 3) -> list:
        """Fetch hashtags from recent published posts for diversity scoring.

        Returns list of hashtag arrays (each is a list of strings).
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = _execute_query(
                supabase.table("scheduled_posts")
                .select("generated_hashtags")
                .eq("business_account_id", business_account_id)
                .eq("status", "published")
                .order("created_at", desc=True)
                .limit(limit),
                table="scheduled_posts",
                operation="select"
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

    # --------------------------------------------------
    # READ: Posts Today Count (Content Scheduler)
    # --------------------------------------------------
    @staticmethod
    def get_posts_today_count(business_account_id: str) -> int:
        """Count posts created today for daily cap enforcement."""
        if not supabase or not business_account_id:
            return 0

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        try:
            result = _execute_query(
                supabase.table("scheduled_posts")
                .select("id", count="exact")
                .eq("business_account_id", business_account_id)
                .in_("status", ["approved", "publishing", "published"])
                .gte("created_at", today_start),
                table="scheduled_posts",
                operation="select"
            )
            return result.count or 0

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping posts today count")
            return 0
        except Exception as e:
            logger.warning(f"Failed to get posts today count: {e}")
            return 0

    # --------------------------------------------------
    # WRITE: Create Scheduled Post (Content Scheduler)
    # --------------------------------------------------
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
            result = _execute_query(
                supabase.table("scheduled_posts").insert(row),
                table="scheduled_posts",
                operation="insert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create scheduled post")
            return {}
        except Exception as e:
            logger.error(f"Failed to create scheduled post: {e}")
            return {}

    # --------------------------------------------------
    # WRITE: Update Scheduled Post Status (Content Scheduler)
    # --------------------------------------------------
    @staticmethod
    def update_scheduled_post_status(
        post_id: str,
        status: str,
        extra_fields: dict = None,
    ) -> bool:
        """Update scheduled post status with optional extra fields.

        Used for state transitions:
          approved → publishing → published | failed
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
            _execute_query(
                supabase.table("scheduled_posts")
                .update(update_data)
                .eq("id", post_id),
                table="scheduled_posts",
                operation="update"
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update scheduled post status")
            return False
        except Exception as e:
            logger.error(f"Failed to update scheduled post {post_id}: {e}")
            return False

    # --------------------------------------------------
    # WRITE: Update Asset After Post (Content Scheduler)
    # --------------------------------------------------
    @staticmethod
    def update_asset_after_post(asset_id: str) -> bool:
        """Update asset metadata after successful publish.

        Increments post_count and sets last_posted to now.
        """
        if not supabase or not asset_id:
            return False

        try:
            current = _execute_query(
                supabase.table("instagram_assets")
                .select("post_count")
                .eq("id", asset_id)
                .limit(1),
                table="instagram_assets",
                operation="select"
            )

            current_count = 0
            if current.data:
                current_count = current.data[0].get("post_count", 0) or 0

            _execute_query(
                supabase.table("instagram_assets")
                .update({
                    "last_posted": datetime.now(timezone.utc).isoformat(),
                    "post_count": current_count + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                .eq("id", asset_id),
                table="instagram_assets",
                operation="update"
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update asset after post")
            return False
        except Exception as e:
            logger.error(f"Failed to update asset {asset_id} after post: {e}")
            return False

    # --------------------------------------------------
    # READ: Monitored Hashtags (UGC Collection)
    # --------------------------------------------------
    @staticmethod
    def get_monitored_hashtags(business_account_id: str) -> list:
        """Fetch active monitored hashtags for UGC discovery.

        Returns list of dicts with: id, hashtag.
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = _execute_query(
                supabase.table("ugc_monitored_hashtags")
                .select("id, hashtag")
                .eq("business_account_id", business_account_id)
                .eq("is_active", True),
                table="ugc_monitored_hashtags",
                operation="select"
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping monitored hashtags fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch monitored hashtags for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # READ: Existing UGC IDs (UGC Collection — DB-level dedup)
    # --------------------------------------------------
    @staticmethod
    def get_existing_ugc_ids(business_account_id: str) -> set:
        """Fetch instagram_media_ids already in ugc_discovered for this account.

        Used as authoritative dedup when Redis is unavailable.
        """
        if not supabase or not business_account_id:
            return set()

        try:
            result = _execute_query(
                supabase.table("ugc_discovered")
                .select("instagram_media_id")
                .eq("business_account_id", business_account_id),
                table="ugc_discovered",
                operation="select"
            )
            return {row["instagram_media_id"] for row in (result.data or [])}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping existing UGC IDs fetch")
            return set()
        except Exception as e:
            logger.warning(f"Failed to fetch existing UGC IDs: {e}")
            return set()

    # --------------------------------------------------
    # WRITE: Create UGC Discovered (UGC Collection)
    # --------------------------------------------------
    @staticmethod
    def create_ugc_discovered(data: dict) -> dict:
        """Upsert a discovered UGC post into ugc_discovered.

        Uses upsert on instagram_media_id to safely overwrite unscored rows
        pre-populated by the backend's /sync-ugc endpoint.

        Expected data keys:
          business_account_id, instagram_media_id, source, source_hashtag,
          username, caption, media_type, media_url, permalink,
          like_count, comments_count, quality_score, quality_tier,
          quality_factors, post_timestamp, run_id
        """
        if not supabase:
            return {}

        try:
            result = _execute_query(
                supabase.table("ugc_discovered").upsert(data, on_conflict="instagram_media_id"),
                table="ugc_discovered",
                operation="upsert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create ugc_discovered")
            return {}
        except Exception as e:
            logger.error(f"Failed to create ugc_discovered: {e}")
            return {}

    # --------------------------------------------------
    # WRITE: Create UGC Permission (UGC Collection)
    # --------------------------------------------------
    @staticmethod
    def create_or_get_ugc_content(
        business_account_id: str,
        instagram_media_id: str,
        author_id: str,
        author_username: str,
        media_url: str,
        media_type: str,
        caption: str,
        permalink: str,
        like_count: int,
        comment_count: int,
        post_timestamp: str,
    ) -> str | None:
        """Upsert a ugc_content record (DB source of truth for permissions FK).

        The ugc_permissions table requires a ugc_content_id FK to ugc_content.
        This method upserts a minimal ugc_content row and returns the UUID.
        Returns the ugc_content.id UUID, or None on failure.
        """
        if not supabase or not instagram_media_id:
            return None
        try:
            result = _execute_query(
                supabase.table("ugc_content")
                .upsert({
                    "business_account_id": business_account_id,
                    "visitor_post_id": instagram_media_id,
                    "author_id": author_id or "",
                    "author_username": author_username,
                    "message": caption[:2000] if caption else None,
                    "permalink_url": permalink or "",
                    "media_type": media_type or "IMAGE",
                    "media_url": media_url,
                    "like_count": like_count or 0,
                    "comment_count": comment_count or 0,
                    "created_time": post_timestamp or datetime.now(timezone.utc).isoformat(),
                }, on_conflict="visitor_post_id")
                .select("id")
                .single(),
                table="ugc_content",
                operation="upsert",
            )
            return result.data["id"] if result.data else None
        except Exception as e:
            logger.error(f"Failed to create ugc_content for {instagram_media_id}: {e}")
            return None

    @staticmethod
    def create_ugc_permission(data: dict) -> dict:
        """Insert a UGC permission request into ugc_permissions.

        Expected data keys:
          ugc_content_id (FK to ugc_content.id), business_account_id,
          dm_message_text, status (pending/granted/denied/expired), run_id
        """
        if not supabase:
            return {}

        try:
            result = _execute_query(
                supabase.table("ugc_permissions").insert(data),
                table="ugc_permissions",
                operation="insert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to create ugc_permission")
            return {}
        except Exception as e:
            logger.error(f"Failed to create ugc_permission: {e}")
            return {}

    # --------------------------------------------------
    # WRITE: Update UGC Permission Status (UGC Collection)
    # --------------------------------------------------
    @staticmethod
    def update_ugc_permission_status(
        permission_id: str,
        status: str,
        extra_fields: dict = None,
    ) -> bool:
        """Update UGC permission status. Valid values: pending/granted/denied/expired."""
        if not supabase or not permission_id:
            return False

        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_fields:
            update_data.update(extra_fields)

        try:
            _execute_query(
                supabase.table("ugc_permissions")
                .update(update_data)
                .eq("id", permission_id),
                table="ugc_permissions",
                operation="update"
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update ugc_permission status")
            return False
        except Exception as e:
            logger.error(f"Failed to update ugc_permission {permission_id}: {e}")
            return False

    # --------------------------------------------------
    # READ: UGC Stats (UGC Collection — for status endpoint)
    # --------------------------------------------------
    @staticmethod
    def get_ugc_stats(business_account_id: str = None) -> dict:
        """Aggregate UGC discovery stats for the status endpoint.

        Returns counts by quality tier.
        """
        if not supabase:
            return {}

        try:
            query = supabase.table("ugc_discovered").select("id", count="exact")
            if business_account_id:
                query = query.eq("business_account_id", business_account_id)
            result = _execute_query(query, table="ugc_discovered", operation="select")
            total = result.count or 0

            tiers = {}
            for tier in ("high", "moderate"):
                q = supabase.table("ugc_discovered").select("id", count="exact").eq("quality_tier", tier)
                if business_account_id:
                    q = q.eq("business_account_id", business_account_id)
                r = _execute_query(q, table="ugc_discovered", operation="select")
                tiers[tier] = r.count or 0

            return {"total_discovered": total, "by_tier": tiers}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping UGC stats")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch UGC stats: {e}")
            return {}

    # --------------------------------------------------
    # READ: Order Attribution (Sales Attribution - dedup)
    # --------------------------------------------------
    @staticmethod
    def get_order_attribution(order_id: str) -> dict:
        """Check if an order has already been attributed (dedup).

        Returns the existing attribution row or empty dict.
        """
        if not supabase or not order_id:
            return {}

        try:
            result = _execute_query(
                supabase.table("sales_attributions")
                .select("id, order_id")
                .eq("order_id", order_id)
                .limit(1),
                table="sales_attributions",
                operation="select"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping order attribution check")
            return {}
        except Exception as e:
            logger.warning(f"Failed to check order attribution for {order_id}: {e}")
            return {}

    # --------------------------------------------------
    # READ: Customer Enrichment (Sales Attribution)
    # --------------------------------------------------
    @staticmethod
    def get_customer_enrichment(
        email: str,
        business_account_id: str,
        history_days: int = 90,
        engagement_days: int = 30,
    ) -> dict:
        """Fetch customer history + recent engagements in one call.

        Combines two queries internally but exposes a single method
        to simplify the webhook pipeline.

        Returns: {"history": {...}, "engagements": [...]}
        """
        if not supabase or not email:
            return {"history": {}, "engagements": []}

        history = {}
        engagements = []

        # Query 1: Customer Instagram history
        history_cutoff = (datetime.now(timezone.utc) - timedelta(days=history_days)).isoformat()
        try:
            result = _execute_query(
                supabase.table("customer_instagram_history")
                .select("purchase_count, total_spend, first_purchase, last_purchase, "
                        "customer_tags, instagram_interactions, average_order_value")
                .eq("email", email)
                .gte("last_purchase", history_cutoff)
                .limit(1),
                table="customer_instagram_history",
                operation="select"
            )
            history = result.data[0] if result.data else {}
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping customer history fetch")
        except Exception as e:
            logger.warning(f"Failed to fetch customer history for {email}: {e}")

        # Query 2: Recent Instagram engagements
        eng_cutoff = (datetime.now(timezone.utc) - timedelta(days=engagement_days)).isoformat()
        try:
            result = _execute_query(
                supabase.table("instagram_engagements")
                .select("engagement_type, content_id, post_id, timestamp, metadata")
                .eq("customer_email", email)
                .eq("business_account_id", business_account_id)
                .gte("timestamp", eng_cutoff)
                .order("timestamp", desc=False)
                .limit(100),
                table="instagram_engagements",
                operation="select"
            )
            engagements = result.data or []
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping recent engagements fetch")
        except Exception as e:
            logger.warning(f"Failed to fetch engagements for {email}: {e}")

        return {"history": history, "engagements": engagements}

    # --------------------------------------------------
    # WRITE: Save Attribution (Sales Attribution)
    # --------------------------------------------------
    @staticmethod
    def save_attribution(data: dict) -> dict:
        """Insert a completed attribution result into sales_attributions."""
        if not supabase:
            return {}

        try:
            result = _execute_query(
                supabase.table("sales_attributions").insert(data),
                table="sales_attributions",
                operation="insert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save attribution")
            return {}
        except Exception as e:
            logger.error(f"Failed to save attribution: {e}")
            return {}

    # --------------------------------------------------
    # WRITE: Queue for Review (Sales Attribution)
    # --------------------------------------------------
    @staticmethod
    def queue_for_review(data: dict) -> dict:
        """Insert an attribution that needs manual review."""
        if not supabase:
            return {}

        try:
            result = _execute_query(
                supabase.table("attribution_review_queue").insert(data),
                table="attribution_review_queue",
                operation="insert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to queue for review")
            return {}
        except Exception as e:
            logger.error(f"Failed to queue for review: {e}")
            return {}

    # --------------------------------------------------
    # READ: Last Week Attributions (Weekly Learning)
    # --------------------------------------------------
    @staticmethod
    def get_last_week_attributions(business_account_id: str = None) -> list:
        """Fetch last 7 days of attributions for weekly learning.

        If business_account_id provided, filters by account.
        """
        if not supabase:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        try:
            query = (
                supabase.table("sales_attributions")
                .select("order_id, order_value, attribution_method, attribution_score, "
                        "model_scores, auto_approved, validation_results, "
                        "business_account_id, processed_at")
                .gte("processed_at", cutoff)
            )
            if business_account_id:
                query = query.eq("business_account_id", business_account_id)

            result = _execute_query(query, table="sales_attributions", operation="select")
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping last week attributions fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch last week attributions: {e}")
            return []

    # --------------------------------------------------
    # WRITE: Update Attribution Model Weights (Weekly Learning)
    # --------------------------------------------------
    @staticmethod
    def update_attribution_model_weights(
        business_account_id: str,
        weights: dict,
        metrics: dict,
        notes: str = "",
    ) -> bool:
        """Upsert attribution model weights for a business account.

        Invalidates L1 cache after write.
        """
        if not supabase or not business_account_id:
            return False

        row = {
            "business_account_id": business_account_id,
            "weights": weights,
            "performance_metrics": metrics,
            "learning_notes": notes,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            _execute_query(
                supabase.table("attribution_models")
                .upsert(row, on_conflict="business_account_id"),
                table="attribution_models",
                operation="upsert"
            )

            # Invalidate L1 cache
            cache_key = f"attr_model:{business_account_id}"
            if cache_key in _attribution_model_cache:
                del _attribution_model_cache[cache_key]

            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update model weights")
            return False
        except Exception as e:
            logger.error(f"Failed to update model weights: {e}")
            return False

    # --------------------------------------------------
    # READ: Attribution Model Weights (Sales Attribution)
    # --------------------------------------------------
    @staticmethod
    def get_attribution_model_weights(business_account_id: str) -> dict:
        """Fetch current attribution model weights.

        L1 in-memory (5 min TTL) -> L2 Redis (5 min TTL) -> Supabase.
        Returns default weights if no custom model exists.
        """
        default_weights = {
            "last_touch": 0.40, "first_touch": 0.20,
            "linear": 0.20, "time_decay": 0.20,
        }
        if not supabase or not business_account_id:
            return default_weights

        cache_key = f"attr_model:{business_account_id}"

        # L1: Check in-memory cache
        if cache_key in _attribution_model_cache:
            CACHE_HITS.labels(key_type="attribution_model_l1").inc()
            return _attribution_model_cache[cache_key]

        # L2: Check Redis cache
        cached = _cache_get(cache_key)
        if cached:
            CACHE_HITS.labels(key_type="attribution_model_l2").inc()
            _attribution_model_cache[cache_key] = cached
            return cached

        CACHE_MISSES.labels(key_type="attribution_model").inc()

        try:
            result = _execute_query(
                supabase.table("attribution_models")
                .select("weights")
                .eq("business_account_id", business_account_id)
                .limit(1),
                table="attribution_models",
                operation="select"
            )

            if result.data:
                weights = result.data[0].get("weights", default_weights)
                _attribution_model_cache[cache_key] = weights
                _cache_set(cache_key, weights, ttl=300)
                return weights

            return default_weights

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — using default attribution weights")
            return default_weights
        except Exception as e:
            logger.warning(f"Failed to fetch model weights: {e}")
            return default_weights

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

            _execute_query(
                supabase.table("audit_log").insert(row),
                table="audit_log",
                operation="insert"
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to log decision to audit_log")
            return False
        except Exception as e:
            logger.error(f"Failed to log decision to audit_log: {e}")
            return False

    # --------------------------------------------------
    # READ: Historical Analytics Reports (Analytics Reports)
    # --------------------------------------------------
    @staticmethod
    def get_historical_reports(
        business_account_id: str,
        report_type: str,
        days: int = 30,
    ) -> list:
        """Fetch recent analytics reports for historical comparison.

        Returns most recent reports first, limited by days lookback.
        Caching: L1 in-memory (60s TTL) — reports don't change frequently.
        """
        if not supabase or not business_account_id:
            return []

        cache_key = f"analytics_hist:{business_account_id}:{report_type}:{days}"

        # L1: Check in-memory cache
        if cache_key in _account_info_cache:  # Reuse account_info cache (60s TTL fits)
            CACHE_HITS.labels(key_type="analytics_historical_l1").inc()
            return _account_info_cache[cache_key]

        CACHE_MISSES.labels(key_type="analytics_historical").inc()

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            result = _execute_query(
                supabase.table("analytics_reports")
                .select("report_date, start_date, end_date, instagram_metrics, "
                        "media_metrics, revenue_metrics, insights, historical_comparison")
                .eq("business_account_id", business_account_id)
                .eq("report_type", report_type)
                .gte("report_date", cutoff)
                .order("report_date", desc=True)
                .limit(30),
                table="analytics_reports",
                operation="select"
            )

            data = result.data or []
            _account_info_cache[cache_key] = data
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping historical reports fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch historical reports for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # WRITE: Save Analytics Report (Analytics Reports)
    # --------------------------------------------------
    @staticmethod
    def save_analytics_report(report_data: dict) -> dict:
        """Upsert an analytics report.

        Uses ON CONFLICT (business_account_id, report_type, report_date)
        to update if a report already exists for the same day/type.
        """
        if not supabase:
            return {}

        try:
            result = _execute_query(
                supabase.table("analytics_reports")
                .upsert(report_data, on_conflict="business_account_id,report_type,report_date"),
                table="analytics_reports",
                operation="upsert"
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save analytics report")
            return {}
        except Exception as e:
            logger.error(f"Failed to save analytics report: {e}")
            return {}

    # --------------------------------------------------
    # READ: Attribution Revenue (Analytics Reports)
    # --------------------------------------------------
    @staticmethod
    def get_attribution_revenue(
        business_account_id: str,
        start_date,
        end_date,
    ) -> dict:
        """Aggregate revenue data from sales_attributions for a date range.

        Returns dict with attributed_orders, attributed_revenue, avg_order_value,
        avg_attribution_score, top_touchpoint_type.
        """
        default = {
            "attributed_orders": 0, "attributed_revenue": 0.0,
            "avg_order_value": 0.0, "avg_attribution_score": 0.0,
            "top_touchpoint_type": "none",
        }
        if not supabase or not business_account_id:
            return default

        try:
            result = _execute_query(
                supabase.table("sales_attributions")
                .select("order_value, attribution_score, attribution_method")
                .eq("business_account_id", business_account_id)
                .gte("processed_at", str(start_date))
                .lte("processed_at", str(end_date)),
                table="sales_attributions",
                operation="select"
            )

            rows = result.data or []
            if not rows:
                return default

            total_revenue = sum(float(r.get("order_value", 0) or 0) for r in rows)
            total_orders = len(rows)
            avg_score = sum(float(r.get("attribution_score", 0) or 0) for r in rows) / total_orders

            # Find most common attribution method
            method_counts = {}
            for r in rows:
                method = r.get("attribution_method", "unknown")
                method_counts[method] = method_counts.get(method, 0) + 1
            top_method = max(method_counts, key=method_counts.get) if method_counts else "none"

            return {
                "attributed_orders": total_orders,
                "attributed_revenue": round(total_revenue, 2),
                "avg_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0,
                "avg_attribution_score": round(avg_score, 2),
                "top_touchpoint_type": top_method,
            }

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping attribution revenue fetch")
            return default
        except Exception as e:
            logger.warning(f"Failed to fetch attribution revenue for {business_account_id}: {e}")
            return default

    # --------------------------------------------------
    # READ: Media Stats for Period (Analytics Reports)
    # --------------------------------------------------
    @staticmethod
    def get_media_stats_for_period(
        business_account_id: str,
        start_date,
        end_date,
    ) -> list:
        """Fetch post metrics from instagram_media for a date range.

        Used as Supabase DB fallback when backend proxy is unavailable.
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = _execute_query(
                supabase.table("instagram_media")
                .select("instagram_media_id, caption, media_type, like_count, "
                        "comments_count, reach, shares_count, published_at")
                .eq("business_account_id", business_account_id)
                .gte("published_at", str(start_date))
                .lte("published_at", str(end_date))
                .order("published_at", desc=True),
                table="instagram_media",
                operation="select"
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping media stats fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch media stats for {business_account_id}: {e}")
            return []

    # --------------------------------------------------
    # READ: Account Follower Snapshot (Analytics Reports)
    # --------------------------------------------------
    @staticmethod
    def get_account_follower_snapshot(business_account_id: str) -> dict:
        """Fetch current follower count and account info for analytics.

        Reuses account_info_cache (60s TTL) via get_account_info pattern.
        """
        account_info = SupabaseService.get_account_info(business_account_id)
        return {
            "followers_count": account_info.get("followers_count", 0),
            "username": account_info.get("username", ""),
            "account_type": account_info.get("account_type", ""),
        }

    # --------------------------------------------------
    # Outbound Queue — Fallback + DLQ persistence
    # --------------------------------------------------

    @staticmethod
    def create_outbound_job(job: dict) -> dict:
        """Insert a job into outbound_queue_jobs (Supabase fallback when Redis unavailable).

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
            "business_account_id": job.get("business_account_id") if _is_valid_uuid(job.get("business_account_id", "")) else None,
            "idempotency_key": job.get("idempotency_key"),
            "source": job.get("source", "unknown"),
            "status": "pending",
            "retry_count": job.get("retry_count", 0),
            "max_retries": job.get("max_retries", 5),
            "created_at": job.get("created_at", datetime.now(timezone.utc).isoformat()),
        }

        try:
            result = _execute_query(
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

    @staticmethod
    def get_pending_outbound_jobs(limit: int = 50) -> list:
        """Fetch pending Supabase fallback jobs (Redis was unavailable at enqueue time).

        Ordered by created_at ASC (FIFO). Used by drain_supabase_fallback().
        Returns list of job dicts.
        """
        if not supabase:
            return []

        try:
            result = _execute_query(
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

    @staticmethod
    def update_outbound_job_status(
        job_id: str,
        status: str,
        extra_fields: dict = None,
    ) -> bool:
        """Update outbound_queue_jobs status for a given job_id UUID.

        Mirrors update_scheduled_post_status pattern.
        """
        if not supabase or not job_id:
            return False

        update_data = {"status": status}
        if extra_fields:
            update_data.update(extra_fields)

        try:
            _execute_query(
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

    @staticmethod
    def get_outbound_dlq(limit: int = 50) -> list:
        """Fetch DLQ jobs from outbound_queue_jobs for the /queue/dlq endpoint."""
        if not supabase:
            return []

        try:
            result = _execute_query(
                supabase.table("outbound_queue_jobs")
                .select("*")
                .eq("status", "dlq")
                .order("created_at", desc=True)
                .limit(limit),
                table="outbound_queue_jobs",
                operation="select",
            )
            return result.data or []
        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DLQ fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch DLQ jobs: {e}")
            return []

    @staticmethod
    def get_outbound_job_by_idempotency_key(idempotency_key: str) -> dict:
        """Fetch most recent active job matching this idempotency_key.

        Used by OutboundQueue.enqueue() to deduplicate before pushing.
        Returns {} if not found or key is empty.
        """
        if not supabase or not idempotency_key:
            return {}

        try:
            result = _execute_query(
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
