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


# ================================
# JSONB Column Models (agent-writable tables)
# These mirror the TypeScript interfaces + Zod schemas in the dashboard.
# SYNC: src/types/agent-tables.ts
# ================================

class PostSelectionFactors(BaseModel):
    """scheduled_posts.selection_factors — SYNC: agent-tables.ts PostSelectionFactors"""
    visual_quality: Optional[float] = Field(None, ge=0, le=100)
    engagement_potential: Optional[float] = Field(None, ge=0, le=100)
    brand_alignment: Optional[float] = Field(None, ge=0, le=100)
    recency: Optional[float] = Field(None, ge=0, le=100)
    uniqueness: Optional[float] = Field(None, ge=0, le=100)

    class Config:
        extra = "allow"  # Content tools may add scoring-specific keys


class AgentModifications(BaseModel):
    """scheduled_posts.agent_modifications — SYNC: agent-tables.ts AgentModifications"""
    caption: Optional[str] = None
    hook: Optional[str] = None
    body: Optional[str] = None
    cta: Optional[str] = None
    hashtags: Optional[list[str]] = None
    reason: str = Field(..., min_length=1)

    class Config:
        extra = "allow"


class AttributionModelWeightsModel(BaseModel):
    """attribution_models.weights — SYNC: agent-tables.ts AttributionModelWeights"""
    first_touch: float = Field(..., ge=0, le=1)
    last_touch: float = Field(..., ge=0, le=1)
    linear: float = Field(..., ge=0, le=1)
    time_decay: float = Field(..., ge=0, le=1)


class AttributionPerformanceMetricsModel(BaseModel):
    """attribution_models.performance_metrics — SYNC: agent-tables.ts AttributionPerformanceMetrics"""
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    last_evaluated: Optional[str] = None
    sample_size: Optional[int] = None

    class Config:
        extra = "allow"
