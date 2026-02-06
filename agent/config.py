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

# ================================
# Approval Thresholds & Constants
# ================================
COMMENT_APPROVAL_THRESHOLD = 0.75
DM_APPROVAL_THRESHOLD = 0.75
POST_APPROVAL_THRESHOLD = 0.72

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
