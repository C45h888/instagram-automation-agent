import os
from functools import wraps
from flask import request, jsonify
from pydantic import BaseModel, Field
from typing import Optional


# ================================
# API Key Authentication Middleware
# ================================
def require_api_key(f):
    """Decorator to enforce X-API-Key header on approval routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = os.getenv("AGENT_API_KEY", "")
        if not api_key:
            # No key configured - skip auth (dev mode)
            return f(*args, **kwargs)

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != api_key:
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid or missing X-API-Key header"
            }), 401

        return f(*args, **kwargs)
    return decorated


# ================================
# Pydantic Request Models
# ================================
class CommentApprovalRequest(BaseModel):
    comment_id: str
    comment_text: str
    post_id: str
    business_account_id: str
    proposed_reply: str
    detected_intent: str = "general"
    sentiment: str = "neutral"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    commenter_username: Optional[str] = None


class CustomerHistory(BaseModel):
    previous_interactions: int = 0
    sentiment_history: str = "neutral"
    lifetime_value: float = 0.0


class DMApprovalRequest(BaseModel):
    message_id: str
    dm_text: str
    sender_username: str
    sender_id: str
    business_account_id: str
    proposed_reply: str
    detected_intent: str = "general"
    sentiment: str = "neutral"
    within_24h_window: bool = True
    priority: str = "medium"
    customer_history: Optional[CustomerHistory] = None


class AssetInfo(BaseModel):
    public_id: str = ""
    image_url: str = ""
    width: int = 0
    height: int = 0
    tags: list[str] = []


class PostApprovalRequest(BaseModel):
    scheduled_post_id: str = ""
    asset: Optional[AssetInfo] = None
    proposed_caption: str
    business_account_id: str
    hashtags: list[str] = []
    hashtag_count: int = 0
    caption_length: int = 0
    engagement_prediction: float = 0.0
    post_type: str = "general"
    scheduled_time: str = ""


def validate_request(model_class, data: dict):
    """Validate request data against a Pydantic model.
    Returns (parsed_model, None) on success or (None, error_response) on failure.
    """
    try:
        parsed = model_class(**data)
        return parsed, None
    except Exception as e:
        error_msg = str(e)
        return None, jsonify({
            "error": "validation_error",
            "message": f"Invalid request payload: {error_msg}"
        })
