import time
from fastapi import APIRouter
from config import OLLAMA_MODEL, supabase, logger
from services.llm_service import LLMService
from services.supabase_service import is_redis_healthy

health_router = APIRouter()

_start_time = time.time()
_request_count = 0
_total_latency = 0

# Tables the agent depends on
AGENT_TABLES = [
    "audit_log",
    "instagram_media",
    "instagram_business_accounts",
    "instagram_comments",
    "instagram_dm_conversations",
    "instagram_dm_messages",
]


def track_request(latency_ms: int):
    """Track request metrics for health endpoint."""
    global _request_count, _total_latency
    _request_count += 1
    _total_latency += latency_ms


@health_router.get("/health")
async def health():
    """Enhanced health check: verifies Ollama + Supabase (per-table) + Redis."""
    status = "healthy"
    issues = []

    # Check Ollama
    ollama_status = LLMService.is_available()
    if not ollama_status.get("available"):
        status = "degraded"
        issues.append(f"Ollama: {ollama_status.get('reason', 'unavailable')}")

    # Check Supabase — per-table verification
    db_connected = False
    tables_ok = []
    tables_failed = []

    if supabase:
        for table_name in AGENT_TABLES:
            try:
                supabase.table(table_name).select("id").limit(1).execute()
                tables_ok.append(table_name)
            except Exception as e:
                tables_failed.append({"table": table_name, "error": str(e)[:100]})

        db_connected = len(tables_ok) == len(AGENT_TABLES)
        if tables_failed:
            status = "degraded"
            issues.append(f"Supabase: {len(tables_failed)} table(s) unreachable")
    else:
        status = "degraded"
        issues.append("Supabase: not configured")

    # Check Redis
    redis_ok = is_redis_healthy()
    if not redis_ok:
        # Redis is optional — degraded but not unhealthy
        issues.append("Redis: unavailable (caching disabled)")

    uptime = int(time.time() - _start_time)
    avg_latency = int(_total_latency / _request_count) if _request_count > 0 else 0

    return {
        "status": status,
        "model": OLLAMA_MODEL,
        "model_loaded": ollama_status.get("available", False),
        "models_available": ollama_status.get("models_loaded", []),
        "db_connection": "connected" if db_connected else "degraded",
        "db_tables_ok": tables_ok,
        "db_tables_failed": tables_failed if tables_failed else None,
        "redis_connected": redis_ok,
        "uptime_seconds": uptime,
        "requests_processed": _request_count,
        "average_response_time_ms": avg_latency,
        "issues": issues if issues else None,
    }
