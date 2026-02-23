# agent/ugc_field_map.py
# Single source of truth for scored post dict → ugc_content column mapping.
#
# PROXY-FIRST PATTERN:
#   Backend writes raw row (quality_score=null) → ugc_content
#   Agent upserts enrichment onto SAME row via composite key (business_account_id, visitor_post_id)
#
# Conflict key for all agent upserts: (business_account_id, visitor_post_id)

_VALID_MEDIA_TYPES = {"IMAGE", "VIDEO", "CAROUSEL_ALBUM", "TEXT"}


def _normalise_media_type(raw: str | None) -> str:
    upper = (raw or "IMAGE").upper()
    return upper if upper in _VALID_MEDIA_TYPES else "IMAGE"


def map_scored_post_to_ugc_content(
    post: dict,
    account_id: str,
    score: int,
    tier: str,
    factors: dict,
    run_id: str,
) -> dict:
    """Map a scored Instagram post to ugc_content columns for upsert.

    Args:
        post:       Raw post dict from Graph API (via backend proxy)
        account_id: business_account_id UUID
        score:      quality_score (0-95)
        tier:       quality_tier ('high' | 'moderate')
        factors:    quality_factors dict
        run_id:     UGC discovery run UUID

    Returns:
        Dict ready for ugc_content upsert with on_conflict=business_account_id,visitor_post_id
    """
    return {
        "business_account_id": account_id,
        "visitor_post_id":     post.get("id", ""),
        "author_username":     post.get("username", ""),
        "message":            (post.get("caption") or "")[:2000],
        "media_type":          _normalise_media_type(post.get("media_type")),
        "media_url":           post.get("media_url", ""),
        "permalink_url":       post.get("permalink", ""),
        "like_count":          post.get("like_count", 0) or 0,
        "comment_count":       post.get("comments_count", 0) or 0,
        "created_time":        post.get("timestamp"),
        "source":              post.get("_source", "unknown"),
        "source_hashtag":      post.get("_source_hashtag"),
        "quality_score":       score,
        "quality_tier":        tier,
        "quality_factors":     factors,
        "run_id":              run_id,
    }
