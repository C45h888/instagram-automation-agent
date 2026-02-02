import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client
from langchain_ollama import OllamaLLM

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

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# ================================
# Ollama / Nemotron LLM
# ================================
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "nemotron:8b-q5_K_M")

llm = OllamaLLM(
    model=OLLAMA_MODEL,
    base_url=OLLAMA_HOST,
    timeout=10,
)

# ================================
# Security
# ================================
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")

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
