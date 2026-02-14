"""
UGC Collection Tools
=====================
Pure-Python quality scoring, backend-proxied Instagram data fetching,
and DM composition for UGC rights management.

Called by ugc_discovery.py — NOT registered as LangChain tools
(these are internal pipeline functions, not agent-callable tools).

Functions:
  - score_ugc_quality:      Deterministic 0-95 scoring (engagement, media type, caption, brand, keywords)
  - fetch_hashtag_media:    Backend proxy: POST /api/instagram/search-hashtag
  - fetch_tagged_media:     Backend proxy: GET /api/instagram/tags
  - compose_dm_message:     Build permission request DM text
  - send_permission_dm:     Backend proxy: POST /api/instagram/send-dm (with retry)
"""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    logger,
    BACKEND_SEARCH_HASHTAG_ENDPOINT,
    BACKEND_GET_TAGS_ENDPOINT,
    BACKEND_SEND_DM_ENDPOINT,
    BACKEND_TIMEOUT_SECONDS,
    UGC_COLLECTION_PRODUCT_KEYWORDS,
    UGC_COLLECTION_HIGH_QUALITY_THRESHOLD,
    UGC_COLLECTION_MODERATE_QUALITY_THRESHOLD,
    backend_headers,
)


# ================================
# Quality Scoring (Pure Python)
# ================================
def score_ugc_quality(post: dict, brand_username: str) -> dict:
    """Score UGC quality on 0-95 scale.

    Factors:
      - Engagement (0-30): like_count + comments_count*2
        >100: +30, >50: +20, >20: +10, else: 0
      - Media Type (0-25): CAROUSEL_ALBUM: +25, IMAGE: +20, VIDEO: +15
      - Caption Quality (0-10): len(caption) > 100: +10
      - Brand Mention (0-15): @brand_username in caption: +15
      - Product Keywords (0-15): any keyword match: +15

    Returns:
        {"score": int, "factors": {...}, "tier": "high"|"moderate"|"low"}
    """
    factors = {}
    caption = (post.get("caption") or "").lower()
    like_count = post.get("like_count", 0) or 0
    comments_count = post.get("comments_count", 0) or 0

    # --- Engagement (max 30) ---
    engagement_total = like_count + (comments_count * 2)
    if engagement_total > 100:
        factors["engagement"] = 30
    elif engagement_total > 50:
        factors["engagement"] = 20
    elif engagement_total > 20:
        factors["engagement"] = 10
    else:
        factors["engagement"] = 0

    # --- Media Type (max 25) ---
    media_type = (post.get("media_type") or "").upper()
    if media_type == "CAROUSEL_ALBUM":
        factors["media_type"] = 25
    elif media_type == "IMAGE":
        factors["media_type"] = 20
    elif media_type == "VIDEO":
        factors["media_type"] = 15
    else:
        factors["media_type"] = 10

    # --- Caption Quality (max 10) ---
    factors["caption_quality"] = 10 if len(caption) > 100 else 0

    # --- Brand Mention (max 15) ---
    brand_lower = f"@{brand_username.lower()}" if brand_username else ""
    factors["brand_mention"] = 15 if brand_lower and brand_lower in caption else 0

    # --- Product Keywords (max 15) ---
    keyword_match = any(
        kw.strip().lower() in caption
        for kw in UGC_COLLECTION_PRODUCT_KEYWORDS
    )
    factors["product_keywords"] = 15 if keyword_match else 0

    score = sum(factors.values())

    # Determine tier
    if score >= UGC_COLLECTION_HIGH_QUALITY_THRESHOLD:
        tier = "high"
    elif score >= UGC_COLLECTION_MODERATE_QUALITY_THRESHOLD:
        tier = "moderate"
    else:
        tier = "low"

    return {"score": score, "factors": factors, "tier": tier}


# ================================
# Backend Proxy: Hashtag Search
# ================================
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_search_hashtag(payload: dict) -> dict:
    """Backend hashtag search with retry logic."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_SEARCH_HASHTAG_ENDPOINT,
            json=payload,
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


def fetch_hashtag_media(business_account_id: str, hashtag: str, limit: int = 30) -> list:
    """Fetch recent media for a hashtag via backend proxy.

    Returns list of dicts with: id, caption, media_type, media_url,
    permalink, username, timestamp, like_count, comments_count.
    Returns empty list on any error.
    """
    payload = {
        "business_account_id": business_account_id,
        "hashtag": hashtag.lstrip("#"),
        "limit": limit,
    }
    try:
        result = _call_backend_search_hashtag(payload)
        return result.get("recent_media", result.get("data", []))
    except httpx.TimeoutException:
        logger.error(f"Backend timeout searching hashtag #{hashtag}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error searching hashtag #{hashtag}: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Hashtag search failed for #{hashtag}: {e}")
        return []


# ================================
# Backend Proxy: Tagged Posts
# ================================
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_get_tags(params: dict) -> dict:
    """Backend tagged posts fetch with retry logic."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_GET_TAGS_ENDPOINT,
            params=params,
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


def fetch_tagged_media(business_account_id: str, limit: int = 25) -> list:
    """Fetch posts where the brand account is tagged via backend proxy.

    Returns list of dicts with same shape as fetch_hashtag_media.
    Returns empty list on any error.
    """
    params = {
        "business_account_id": business_account_id,
        "limit": str(limit),
    }
    try:
        result = _call_backend_get_tags(params)
        return result.get("tagged_posts", result.get("data", []))
    except httpx.TimeoutException:
        logger.error(f"Backend timeout fetching tagged posts for {business_account_id}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error fetching tagged posts: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Tagged posts fetch failed: {e}")
        return []


# ================================
# DM Composition (Pure Function)
# ================================
def compose_dm_message(username: str, brand_username: str, post_permalink: str) -> str:
    """Compose a UGC permission request DM.

    Kept concise for Instagram DM best practices.
    """
    return (
        f"Hi @{username}! We love your post and would love to feature it "
        f"on @{brand_username}. Would you give us permission to share it? "
        f"Full credit to you of course!"
    )


# ================================
# Backend Proxy: Send DM
# ================================
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_send_dm(payload: dict) -> dict:
    """Backend DM send with retry logic."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.post(
            BACKEND_SEND_DM_ENDPOINT,
            json=payload,
            headers=backend_headers(),
        )
        response.raise_for_status()
        return response.json()


def send_permission_dm(
    business_account_id: str,
    recipient_id: str,
    recipient_username: str,
    message_text: str,
) -> dict:
    """Send permission request DM via backend proxy.

    Args:
        recipient_id: Numeric Instagram user ID (IGSID). Backend requires this.
        recipient_username: Username for audit context / backend fallback resolution.

    Returns {"success": bool, "error": str | None}
    """
    payload = {
        "business_account_id": business_account_id,
        "recipient_id": recipient_id,
        "recipient_username": recipient_username,
        "message_text": message_text,
    }
    try:
        result = _call_backend_send_dm(payload)
        return {"success": True, "response": result}
    except httpx.TimeoutException:
        logger.error(f"Backend timeout sending DM to {recipient_username}")
        return {"success": False, "error": "timeout"}
    except httpx.HTTPStatusError as e:
        logger.error(f"Backend error sending DM: {e.response.status_code}")
        return {"success": False, "error": f"http_{e.response.status_code}"}
    except Exception as e:
        logger.error(f"DM send failed: {e}")
        return {"success": False, "error": str(e)}
