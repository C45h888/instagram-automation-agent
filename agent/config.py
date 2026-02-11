import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_ollama import ChatOllama

load_dotenv()

# ================================
# Logging
# ================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("oversight-agent")

# ================================
# Supabase (Source of Truth)
# ================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("FATAL: SUPABASE_URL and SUPABASE_KEY environment variables are required")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def verify_supabase_connection():
    """Test Supabase connectivity on startup. Crashes if unreachable."""
    try:
        supabase.table("audit_log").select("id").limit(1).execute()
        logger.info("Supabase connection verified successfully")
    except Exception as e:
        logger.error(f"FATAL: Supabase connection failed: {e}")
        sys.exit(1)


def validate_schema():
    """Verify DB schema matches code expectations at startup.

    Prevents silent mismatches — if a column was renamed or table dropped,
    the agent crashes immediately instead of returning wrong data.
    """
    required = {
        "instagram_media": ["caption", "like_count", "comments_count", "reach", "published_at"],
        "instagram_business_accounts": ["username", "name", "account_type", "followers_count"],
        "instagram_comments": ["text", "sentiment", "business_account_id", "created_at",
                                "processed_by_automation", "automated_response_sent",
                                "response_text", "media_id", "instagram_comment_id"],
        "instagram_dm_conversations": ["customer_instagram_id", "business_account_id", "within_window"],
        "instagram_dm_messages": ["message_text", "conversation_id", "is_from_business", "sent_at"],
        "audit_log": ["event_type", "action", "details", "resource_type"],
    }
    for table, columns in required.items():
        try:
            supabase.table(table).select(",".join(columns)).limit(0).execute()
            logger.info(f"Schema OK: {table}")
        except Exception as e:
            logger.error(f"SCHEMA MISMATCH: {table} — {e}")
            sys.exit(1)

    logger.info("All required schema validations passed")

    # Optional tables (warn instead of crash if missing)
    optional_tables = {
        "prompt_templates": ["prompt_key", "template", "version", "is_active"],
        "instagram_assets": ["business_account_id", "storage_path", "tags", "last_posted", "is_active"],
        "scheduled_posts": ["business_account_id", "status", "generated_caption", "agent_quality_score", "run_id"],
        "sales_attributions": ["order_id", "order_value", "attribution_score", "auto_approved", "business_account_id"],
        "attribution_review_queue": ["order_id", "review_status", "business_account_id"],
        "attribution_models": ["weights", "business_account_id"],
        "ugc_monitored_hashtags": ["business_account_id", "hashtag", "is_active"],
        "ugc_discovered": ["business_account_id", "instagram_media_id", "quality_score", "quality_tier"],
        "ugc_permissions": ["ugc_discovered_id", "business_account_id", "status"],
        "analytics_reports": ["business_account_id", "report_type", "report_date", "instagram_metrics", "insights"],
    }
    for table, columns in optional_tables.items():
        try:
            supabase.table(table).select(",".join(columns)).limit(0).execute()
            logger.info(f"Schema OK (optional): {table}")
        except Exception:
            logger.warning(f"Optional table '{table}' not found — using default prompts")


# Run startup checks
verify_supabase_connection()
validate_schema()

# ================================
# Ollama / Nemotron LLM
# ================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q5_K_M")

llm = ChatOllama(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_HOST,
    timeout=10,
    temperature=0.3,  # Lower for consistent analysis
)

# ================================
# Security
# ================================
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

# ================================
# Instagram Webhook Security
# ================================
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN", "")

# ================================
# Backend Proxy URLs (for Instagram API calls)
# ================================
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3001")
BACKEND_REPLY_COMMENT_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/reply-comment"
BACKEND_REPLY_DM_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/reply-dm"

# ================================
# Timeouts & Resilience
# ================================
BACKEND_TIMEOUT_SECONDS = 8.0
WEBHOOK_RATE_LIMIT = "10/minute"
OVERSIGHT_RATE_LIMIT = "20/minute"  # per-user rate limit (was 10/minute per-IP)

# ================================
# Oversight Brain (Enhanced)
# ================================
OVERSIGHT_STREAM_ENABLED = os.getenv("OVERSIGHT_STREAM_ENABLED", "true").lower() == "true"
OVERSIGHT_AUTO_CONTEXT_LIMIT = int(os.getenv("OVERSIGHT_AUTO_CONTEXT_LIMIT", "12"))
OVERSIGHT_LLM_TIMEOUT_SECONDS = int(os.getenv("OVERSIGHT_LLM_TIMEOUT_SECONDS", "15"))

# ================================
# Rate Limiter (shared instance — import in routes for @limiter.limit())
# ================================
from slowapi import Limiter
from slowapi.util import get_remote_address as _get_remote_address

_redis_host = os.getenv("REDIS_HOST", "redis")
_redis_port = os.getenv("REDIS_PORT", "6379")

limiter = Limiter(
    key_func=_get_remote_address,
    storage_uri=f"redis://{_redis_host}:{_redis_port}",
    default_limits=["60/minute"],
)

MAX_DM_REPLY_LENGTH = 150
MAX_CAPTION_LENGTH = 2200
MAX_HASHTAG_COUNT = 10

VIP_LIFETIME_VALUE_THRESHOLD = 500.0

ESCALATION_INTENTS = {"complaint", "refund", "return", "legal"}

# ================================
# Message Classification Constants
# ================================
MESSAGE_CATEGORIES = {
    "sizing", "shipping", "returns", "availability",
    "order_status", "complaint", "price", "praise", "general"
}
ESCALATION_CATEGORIES = {"complaint", "returns", "order_status"}
URGENT_KEYWORDS = {"urgent", "asap", "emergency", "immediately", "now"}

# ================================
# Engagement Monitor (Scheduler)
# ================================
ENGAGEMENT_MONITOR_ENABLED = os.getenv("ENGAGEMENT_MONITOR_ENABLED", "true").lower() == "true"
ENGAGEMENT_MONITOR_INTERVAL_MINUTES = int(os.getenv("ENGAGEMENT_MONITOR_INTERVAL_MINUTES", "5"))
ENGAGEMENT_MONITOR_MAX_COMMENTS_PER_RUN = int(os.getenv("ENGAGEMENT_MONITOR_MAX_COMMENTS_PER_RUN", "50"))
ENGAGEMENT_MONITOR_MAX_CONCURRENT_ANALYSES = int(os.getenv("ENGAGEMENT_MONITOR_MAX_CONCURRENT_ANALYSES", "3"))
ENGAGEMENT_MONITOR_HOURS_BACK = int(os.getenv("ENGAGEMENT_MONITOR_HOURS_BACK", "24"))
ENGAGEMENT_MONITOR_AUTO_REPLY_ENABLED = os.getenv("ENGAGEMENT_MONITOR_AUTO_REPLY_ENABLED", "true").lower() == "true"
ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD = float(os.getenv("ENGAGEMENT_MONITOR_CONFIDENCE_THRESHOLD", "0.75"))

# ================================
# Content Scheduler
# ================================
CONTENT_SCHEDULER_ENABLED = os.getenv("CONTENT_SCHEDULER_ENABLED", "true").lower() == "true"
CONTENT_SCHEDULER_TIMES = os.getenv("CONTENT_SCHEDULER_TIMES", "09:00,14:00,19:00").split(",")
CONTENT_SCHEDULER_MAX_CONCURRENT_GENERATIONS = int(os.getenv("CONTENT_SCHEDULER_MAX_CONCURRENT_GENERATIONS", "2"))
CONTENT_SCHEDULER_MAX_POSTS_PER_DAY = int(os.getenv("CONTENT_SCHEDULER_MAX_POSTS_PER_DAY", "1"))
CONTENT_SCHEDULER_AUTO_PUBLISH = os.getenv("CONTENT_SCHEDULER_AUTO_PUBLISH", "false").lower() == "true"
CONTENT_SCHEDULER_MAX_ASSETS_TO_SCORE = int(os.getenv("CONTENT_SCHEDULER_MAX_ASSETS_TO_SCORE", "50"))

# Backend publish endpoint
BACKEND_PUBLISH_POST_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/publish-post"

# ================================
# UGC Collection (Scheduler)
# ================================
UGC_COLLECTION_ENABLED = os.getenv("UGC_COLLECTION_ENABLED", "true").lower() == "true"
UGC_COLLECTION_INTERVAL_HOURS = int(os.getenv("UGC_COLLECTION_INTERVAL_HOURS", "4"))
UGC_COLLECTION_MAX_POSTS_PER_HASHTAG = int(os.getenv("UGC_COLLECTION_MAX_POSTS_PER_HASHTAG", "30"))
UGC_COLLECTION_MAX_TAGGED_POSTS = int(os.getenv("UGC_COLLECTION_MAX_TAGGED_POSTS", "25"))
UGC_COLLECTION_MAX_CONCURRENT_ACCOUNTS = int(os.getenv("UGC_COLLECTION_MAX_CONCURRENT_ACCOUNTS", "2"))
UGC_COLLECTION_HIGH_QUALITY_THRESHOLD = int(os.getenv("UGC_COLLECTION_HIGH_QUALITY_THRESHOLD", "70"))
UGC_COLLECTION_MODERATE_QUALITY_THRESHOLD = int(os.getenv("UGC_COLLECTION_MODERATE_QUALITY_THRESHOLD", "41"))
UGC_COLLECTION_AUTO_SEND_DM = os.getenv("UGC_COLLECTION_AUTO_SEND_DM", "false").lower() == "true"
UGC_COLLECTION_PRODUCT_KEYWORDS = os.getenv(
    "UGC_COLLECTION_PRODUCT_KEYWORDS",
    "wearing,styled,love my,obsessed with,favorite"
).split(",")

# Backend UGC endpoints
BACKEND_SEARCH_HASHTAG_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/search-hashtag"
BACKEND_GET_TAGS_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/tags"
BACKEND_SEND_DM_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/send-dm"

# ================================
# Sales Attribution
# ================================
SALES_ATTRIBUTION_ENABLED = os.getenv("SALES_ATTRIBUTION_ENABLED", "true").lower() == "true"
SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD = float(os.getenv("SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD", "0.65"))
SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD = float(os.getenv("SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD", "0.40"))
SALES_ATTRIBUTION_MAX_TOUCHPOINTS = int(os.getenv("SALES_ATTRIBUTION_MAX_TOUCHPOINTS", "30"))
SALES_ATTRIBUTION_LOOKBACK_DAYS = int(os.getenv("SALES_ATTRIBUTION_LOOKBACK_DAYS", "30"))
SALES_ATTRIBUTION_HISTORY_DAYS = int(os.getenv("SALES_ATTRIBUTION_HISTORY_DAYS", "90"))
SALES_ATTRIBUTION_VERSION = os.getenv("SALES_ATTRIBUTION_VERSION", "v1_agentic")
ORDER_WEBHOOK_SECRET = os.getenv("ORDER_WEBHOOK_SECRET", "")

# ================================
# Weekly Learning (Sales Attribution)
# ================================
WEEKLY_LEARNING_ENABLED = os.getenv("WEEKLY_LEARNING_ENABLED", "true").lower() == "true"
WEEKLY_LEARNING_DAY = os.getenv("WEEKLY_LEARNING_DAY", "mon")
WEEKLY_LEARNING_HOUR = int(os.getenv("WEEKLY_LEARNING_HOUR", "8"))

# ================================
# Analytics Reports
# ================================
ANALYTICS_REPORTS_ENABLED = os.getenv("ANALYTICS_REPORTS_ENABLED", "true").lower() == "true"
ANALYTICS_DAILY_HOUR = int(os.getenv("ANALYTICS_DAILY_HOUR", "23"))
ANALYTICS_DAILY_MINUTE = int(os.getenv("ANALYTICS_DAILY_MINUTE", "0"))
ANALYTICS_WEEKLY_DAY = os.getenv("ANALYTICS_WEEKLY_DAY", "sun")
ANALYTICS_WEEKLY_HOUR = int(os.getenv("ANALYTICS_WEEKLY_HOUR", "23"))
ANALYTICS_HISTORICAL_DAYS = int(os.getenv("ANALYTICS_HISTORICAL_DAYS", "30"))
ANALYTICS_MAX_CONCURRENT_ACCOUNTS = int(os.getenv("ANALYTICS_MAX_CONCURRENT_ACCOUNTS", "3"))
ANALYTICS_LLM_INSIGHTS_ENABLED = os.getenv("ANALYTICS_LLM_INSIGHTS_ENABLED", "false").lower() == "true"

# Backend analytics proxy endpoints
BACKEND_ACCOUNT_INSIGHTS_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/account-insights"
BACKEND_MEDIA_INSIGHTS_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/media-insights"
