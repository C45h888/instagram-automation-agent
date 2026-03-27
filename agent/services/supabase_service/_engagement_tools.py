"""
Engagement Tools — @tool-decorated wrappers around EngagementService.
================================================================
Each tool is defined here ONCE: the description lives here, the function
signature lives here, the implementation lives in EngagementService.
supabase_tools.py imports from here — no Pydantic schemas, no Field descriptions.

This eliminates the two-contract problem:
  Before: args_schema (Pydantic) + function signature = two things to keep in sync
  After: @tool decorator = one thing (description + signature + implementation)

Pattern:
  @tool("Description shown to the LLM")
  def tool_name(param: Type) -> ReturnType:
      '''Docstring shown to the LLM alongside the description.'''
      return EngagementService.tool_name(param)
"""

from langchain_core.tools import tool

from ._engagement import EngagementService


@tool("Fetch post details from instagram_media: caption, like_count, comments_count, "
      "engagement_rate, media_type. Use when evaluating a comment reply or post.")
def get_post_context(post_id: str) -> dict:
    """Fetch post context from instagram_media.

    Args:
        post_id: Instagram media ID to fetch context for (not the Supabase UUID)
    """
    return EngagementService.get_post_context(post_id)


@tool("Fetch business account info: username, name, account_type, followers_count, "
      "biography, category. Use to understand brand voice and context.")
def get_account_info(business_account_id: str) -> dict:
    """Fetch account info from instagram_business_accounts.

    Args:
        business_account_id: UUID of the Instagram business account
    """
    return EngagementService.get_account_info(business_account_id)


@tool("Fetch recent comments for a business account: text, sentiment, category, priority, "
      "author_username, created_at. Use for pattern analysis and context.")
def get_recent_comments(business_account_id: str, limit: int = 10) -> list:
    """Fetch recent comments for a business account.

    Args:
        business_account_id: UUID of the Instagram business account
        limit: Number of recent comments to fetch (1-50, default 10)
    """
    return EngagementService.get_recent_comments(business_account_id, limit)


@tool("Fetch average engagement metrics for recent posts: avg_likes, avg_comments, "
      "avg_engagement_rate, sample_size. Use for benchmarking proposed posts.")
def get_post_performance(business_account_id: str, limit: int = 10) -> dict:
    """Fetch recent post performance for benchmarking.

    Args:
        business_account_id: UUID of the Instagram business account
        limit: Number of recent posts to analyze (1-50, default 10)
    """
    return EngagementService.get_recent_post_performance(business_account_id, limit)
