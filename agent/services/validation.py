import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional

import bleach


# ================================
# Sanitization Helpers
# ================================
def _sanitize_text(value: str, max_length: int = 2000) -> str:
    """Strip all HTML tags and cap length. Prevents XSS/injection."""
    if not isinstance(value, str):
        return str(value)[:max_length]
    cleaned = bleach.clean(value, tags=[], strip=True)
    return cleaned[:max_length]


def _validate_uuid_format(value: str) -> str:
    """Validate that a string looks like a UUID."""
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    if not uuid_pattern.match(value):
        raise ValueError(f"Invalid UUID format: {value}")
    return value


# ================================
# Pydantic Request Models (with sanitization)
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

    @field_validator("comment_text", "proposed_reply", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _sanitize_text(v, max_length=2000)

    @field_validator("business_account_id", mode="before")
    @classmethod
    def validate_account_id(cls, v):
        return _validate_uuid_format(v)


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

    @field_validator("dm_text", "proposed_reply", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _sanitize_text(v, max_length=2000)

    @field_validator("business_account_id", mode="before")
    @classmethod
    def validate_account_id(cls, v):
        return _validate_uuid_format(v)


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

    @field_validator("proposed_caption", mode="before")
    @classmethod
    def sanitize_caption(cls, v):
        return _sanitize_text(v, max_length=2200)

    @field_validator("business_account_id", mode="before")
    @classmethod
    def validate_account_id(cls, v):
        return _validate_uuid_format(v)


# ================================
# Instagram Webhook Models
# ================================
class CommentWebhookData(BaseModel):
    """Parsed comment from Instagram webhook."""
    comment_id: str
    comment_text: str
    post_id: str
    commenter_username: str
    commenter_id: str
    business_account_id: str
    timestamp: str

    @field_validator("comment_text", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _sanitize_text(v, max_length=2000)


class DMWebhookData(BaseModel):
    """Parsed DM from Instagram webhook."""
    message_id: str
    message_text: str
    sender_username: str
    sender_id: str
    business_account_id: str
    conversation_id: str
    timestamp: str
    has_attachments: bool = False

    @field_validator("message_text", mode="before")
    @classmethod
    def sanitize_text(cls, v):
        return _sanitize_text(v, max_length=2000)


class ExecutionOutcome(BaseModel):
    """For /log-outcome feedback endpoint."""
    resource_type: str  # "comment" or "dm"
    resource_id: str
    execution_id: str
    success: bool
    instagram_response: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
