from .supabase_tools import SUPABASE_TOOLS
from .automation_tools import AUTOMATION_TOOLS
from services.supabase_service import OVERSIGHT_TOOLS  # single source of truth

# Combined tool list for AgentService
ALL_TOOLS = SUPABASE_TOOLS + AUTOMATION_TOOLS + OVERSIGHT_TOOLS
