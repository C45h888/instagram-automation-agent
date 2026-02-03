"""
LangChain Supabase Tools
=========================
StructuredTool wrappers around SupabaseService methods.
These are bound to the LLM via llm.bind_tools() so the agent
can fetch context and log decisions during analysis.

Each tool uses a Pydantic input schema for type safety.
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from services.supabase_service import SupabaseService


# ================================
# Input Schemas
# ================================
class PostContextInput(BaseModel):
    post_id: str = Field(description="Instagram media ID to fetch context for")


class AccountInfoInput(BaseModel):
    business_account_id: str = Field(description="UUID of the Instagram business account")


class RecentCommentsInput(BaseModel):
    business_account_id: str = Field(description="UUID of the Instagram business account")
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent comments to fetch")


class DMHistoryInput(BaseModel):
    sender_id: str = Field(description="Instagram ID of the DM sender")
    business_account_id: str = Field(description="UUID of the Instagram business account")
    limit: int = Field(default=5, ge=1, le=20, description="Number of recent messages to fetch")


class DMConversationContextInput(BaseModel):
    sender_id: str = Field(description="Instagram ID of the DM sender")
    business_account_id: str = Field(description="UUID of the Instagram business account")


class PostPerformanceInput(BaseModel):
    business_account_id: str = Field(description="UUID of the Instagram business account")
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent posts to analyze")


class LogDecisionInput(BaseModel):
    event_type: str = Field(description="Type of event: comment_reply_approval, dm_reply_approval, post_approval")
    action: str = Field(description="Decision taken: approved, rejected, modified, escalated")
    resource_type: str = Field(description="Type of resource: comment, dm, post")
    resource_id: str = Field(description="ID of the resource being evaluated")
    user_id: str = Field(description="UUID of the business account (user)")
    details: dict = Field(default_factory=dict, description="Additional context about the decision")
    ip_address: str = Field(default="", description="IP address of the requesting client")


# ================================
# Tool Definitions
# ================================
get_post_context_tool = StructuredTool.from_function(
    func=SupabaseService.get_post_context,
    name="get_post_context",
    description="Fetch post details from Instagram media table: caption, like_count, comments_count, engagement_rate, media_type. Use when evaluating a comment reply or post.",
    args_schema=PostContextInput,
)

get_account_info_tool = StructuredTool.from_function(
    func=SupabaseService.get_account_info,
    name="get_account_info",
    description="Fetch business account info: username, name, account_type, followers_count, biography, category. Use to understand brand voice and context.",
    args_schema=AccountInfoInput,
)

get_recent_comments_tool = StructuredTool.from_function(
    func=SupabaseService.get_recent_comments,
    name="get_recent_comments",
    description="Fetch recent comments for a business account: text, sentiment, category, priority. Use for pattern analysis and context.",
    args_schema=RecentCommentsInput,
)

get_dm_history_tool = StructuredTool.from_function(
    func=SupabaseService.get_dm_history,
    name="get_dm_history",
    description="Fetch DM conversation history between a sender and business account. Returns messages with direction (inbound/outbound) and timestamps.",
    args_schema=DMHistoryInput,
)

get_dm_conversation_context_tool = StructuredTool.from_function(
    func=SupabaseService.get_dm_conversation_context,
    name="get_dm_conversation_context",
    description="Fetch DM conversation metadata: within_window (24h status), window_expires_at, conversation_status, message_count. Use to verify messaging window.",
    args_schema=DMConversationContextInput,
)

get_post_performance_tool = StructuredTool.from_function(
    func=SupabaseService.get_recent_post_performance,
    name="get_post_performance",
    description="Fetch average engagement metrics for recent posts: avg_likes, avg_comments, avg_engagement_rate. Use for benchmarking proposed posts.",
    args_schema=PostPerformanceInput,
)

log_decision_tool = StructuredTool.from_function(
    func=SupabaseService.log_decision,
    name="log_agent_decision",
    description="Log an agent decision to the audit_log table. Records event_type, action, resource details, and reasoning for traceability.",
    args_schema=LogDecisionInput,
)

# ================================
# Tool Registry (used by AgentService)
# ================================
SUPABASE_TOOLS = [
    get_post_context_tool,
    get_account_info_tool,
    get_recent_comments_tool,
    get_dm_history_tool,
    get_dm_conversation_context_tool,
    get_post_performance_tool,
    log_decision_tool,
]
