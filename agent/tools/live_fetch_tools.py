"""
Live Fetch Tools
=================
Backend-proxied Instagram data fetching with Redis cache + Supabase write-through.
Called by engagement_monitor.py and ugc_discovery.py as fallback/action functions.
NOT registered as LangChain tools.

Pattern: Redis cache → backend proxy call → Supabase write-through → return data

Cache TTLs:
  - live_comments:   5 min (300s)
  - live_conversations: 2 min (120s) — shorter because 24h window is time-sensitive
  - live_conv_messages: 5 min (300s)

Functions:
  - fetch_live_comments:              GET /post-comments + write-through to instagram_comments
  - fetch_live_conversations:         GET /conversations + write-through to instagram_dm_conversations
  - fetch_live_conversation_messages: GET /conversation-messages + write-through to instagram_dm_messages
  - trigger_repost_ugc:               POST /repost-ugc (one-time action, no cache)
  - trigger_sync_ugc:                 POST /sync-ugc (end-of-run trigger, no cache)
"""

import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    logger,
    BACKEND_POST_COMMENTS_ENDPOINT,
    BACKEND_CONVERSATIONS_ENDPOINT,
    BACKEND_CONVERSATION_MESSAGES_ENDPOINT,
    BACKEND_REPOST_UGC_ENDPOINT,
    BACKEND_SYNC_UGC_ENDPOINT,
    BACKEND_TIMEOUT_SECONDS,
    backend_headers,
)
from services.supabase_service import (
    SupabaseService,
    _cache_get,
    _cache_set,
)


# ================================
# Sync Backend Callers (with retry)
# ================================

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_post_comments(business_account_id: str, media_id: str, limit: int) -> dict:
    """Backend proxy for live post comments."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_POST_COMMENTS_ENDPOINT,
            params={
                "business_account_id": business_account_id,
                "media_id": media_id,
                "limit": limit,
            },
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_conversations(business_account_id: str, limit: int) -> dict:
    """Backend proxy for DM conversations."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_CONVERSATIONS_ENDPOINT,
            params={
                "business_account_id": business_account_id,
                "limit": limit,
            },
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_conversation_messages(
    business_account_id: str, conversation_id: str, limit: int
) -> dict:
    """Backend proxy for conversation message thread."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_CONVERSATION_MESSAGES_ENDPOINT,
            params={
                "business_account_id": business_account_id,
                "conversation_id": conversation_id,
                "limit": limit,
            },
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_repost_ugc(business_account_id: str, permission_id: str) -> dict:
    """Backend proxy to repost UGC after permission is granted."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_REPOST_UGC_ENDPOINT,
            json={
                "business_account_id": business_account_id,
                "permission_id": permission_id,
            },
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_sync_ugc(business_account_id: str) -> dict:
    """Backend proxy to sync tagged posts from Graph API into ugc_discovered."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_SYNC_UGC_ENDPOINT,
            json={"business_account_id": business_account_id},
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


# ================================
# Async Fetch Functions
# ================================

async def fetch_live_comments(
    business_account_id: str,
    instagram_media_id: str,
    media_supabase_uuid: str,
    limit: int = 50,
) -> list:
    """Fetch live comments from backend proxy, cache in Redis, write-through to Supabase.

    Args:
        instagram_media_id: Numeric Instagram media ID (used for Graph API + cache key)
        media_supabase_uuid: Supabase UUID for the FK in instagram_comments.media_id

    Returns list of comment dicts from backend response.
    """
    cache_key = f"live_comments:{business_account_id}:{instagram_media_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.to_thread(
            _call_backend_post_comments, business_account_id, instagram_media_id, limit
        )
        comments = result.get("data", [])
        _cache_set(cache_key, comments, ttl=300)
        await asyncio.to_thread(
            SupabaseService.save_live_comments,
            comments, business_account_id, media_supabase_uuid
        )
        return comments
    except httpx.TimeoutException:
        logger.error(f"Backend timeout fetching comments for media {instagram_media_id}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend HTTP {e.response.status_code} fetching comments for media {instagram_media_id}")
        return []
    except Exception as e:
        logger.error(f"fetch_live_comments failed for media {instagram_media_id}: {e}")
        return []


async def fetch_live_conversations(
    business_account_id: str,
    limit: int = 20,
) -> list:
    """Fetch DM conversations from backend proxy, cache in Redis, write-through to Supabase.

    Cache TTL is 120s (short) because 24-hour messaging window status changes frequently.

    Returns list of conversation dicts from backend response.
    """
    cache_key = f"live_conversations:{business_account_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.to_thread(
            _call_backend_conversations, business_account_id, limit
        )
        conversations = result.get("data", [])
        _cache_set(cache_key, conversations, ttl=120)
        await asyncio.to_thread(
            SupabaseService.save_live_conversations, conversations, business_account_id
        )
        return conversations
    except httpx.TimeoutException:
        logger.error(f"Backend timeout fetching conversations for {business_account_id}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend HTTP {e.response.status_code} fetching conversations for {business_account_id}")
        return []
    except Exception as e:
        logger.error(f"fetch_live_conversations failed for {business_account_id}: {e}")
        return []


async def fetch_live_conversation_messages(
    business_account_id: str,
    conversation_id: str,
    business_ig_user_id: str,
    limit: int = 20,
) -> list:
    """Fetch message thread from backend proxy, cache in Redis, write-through to Supabase.

    Args:
        business_ig_user_id: Instagram numeric user ID of the business (for is_from_business flag)

    Returns list of message dicts from backend response.
    """
    cache_key = f"live_conv_messages:{conversation_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        result = await asyncio.to_thread(
            _call_backend_conversation_messages, business_account_id, conversation_id, limit
        )
        messages = result.get("data", [])
        _cache_set(cache_key, messages, ttl=300)
        await asyncio.to_thread(
            SupabaseService.save_live_conversation_messages,
            messages, conversation_id, business_account_id, business_ig_user_id
        )
        return messages
    except httpx.TimeoutException:
        logger.error(f"Backend timeout fetching messages for conversation {conversation_id}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend HTTP {e.response.status_code} fetching messages for {conversation_id}")
        return []
    except Exception as e:
        logger.error(f"fetch_live_conversation_messages failed for {conversation_id}: {e}")
        return []


# ================================
# Async Action Triggers
# ================================

async def trigger_repost_ugc(business_account_id: str, permission_id: str) -> dict:
    """Trigger UGC repost via backend after creator grants permission.

    The backend verifies permission.status == 'granted', publishes to Instagram,
    and updates ugc_permissions.status = 'reposted'.

    No cache — this is a one-time action.

    Returns {"success": bool, "id": instagram_media_id, "original_author": str, "error": str|None}
    """
    try:
        result = await asyncio.to_thread(
            _call_backend_repost_ugc, business_account_id, permission_id
        )
        return {
            "success": True,
            "id": result.get("id"),
            "original_author": result.get("original_author"),
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            f"repost-ugc HTTP {e.response.status_code} for permission {permission_id}: "
            f"{e.response.text[:200]}"
        )
        return {"success": False, "error": f"http_{e.response.status_code}"}
    except httpx.TimeoutException:
        logger.error(f"repost-ugc timeout for permission {permission_id}")
        return {"success": False, "error": "timeout"}
    except Exception as e:
        logger.error(f"trigger_repost_ugc failed for permission {permission_id}: {e}")
        return {"success": False, "error": str(e)}


async def trigger_sync_ugc(business_account_id: str) -> dict:
    """Trigger UGC sync at end of ugc_discovery run.

    The backend fetches tagged posts from Graph API and upserts into ugc_discovered.
    Called once per account per ugc_discovery cycle.

    No cache — end-of-run trigger.

    Returns {"success": bool, "synced_count": int, "error": str|None}
    """
    try:
        result = await asyncio.to_thread(_call_backend_sync_ugc, business_account_id)
        return {"success": True, "synced_count": result.get("synced_count", 0)}
    except httpx.TimeoutException:
        logger.error(f"sync-ugc timeout for {business_account_id}")
        return {"success": False, "synced_count": 0, "error": "timeout"}
    except httpx.HTTPStatusError as e:
        logger.error(f"sync-ugc HTTP {e.response.status_code} for {business_account_id}")
        return {"success": False, "synced_count": 0, "error": f"http_{e.response.status_code}"}
    except Exception as e:
        logger.error(f"trigger_sync_ugc failed for {business_account_id}: {e}")
        return {"success": False, "synced_count": 0, "error": str(e)}
