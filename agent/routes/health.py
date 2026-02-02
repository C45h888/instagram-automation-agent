import time
from flask import Blueprint, jsonify
from config import OLLAMA_MODEL, supabase, logger
from services.llm_service import LLMService

health_bp = Blueprint("health", __name__)

_start_time = time.time()
_request_count = 0
_total_latency = 0


def track_request(latency_ms: int):
    """Track request metrics for health endpoint."""
    global _request_count, _total_latency
    _request_count += 1
    _total_latency += latency_ms


@health_bp.route("/health", methods=["GET"])
def health():
    """Enhanced health check: verifies Ollama + Supabase connectivity."""
    status = "healthy"
    issues = []

    # Check Ollama
    ollama_status = LLMService.is_available()
    if not ollama_status.get("available"):
        status = "degraded"
        issues.append(f"Ollama: {ollama_status.get('reason', 'unavailable')}")

    # Check Supabase
    db_connected = False
    if supabase:
        try:
            supabase.table("audit_log").select("id").limit(1).execute()
            db_connected = True
        except Exception as e:
            status = "degraded"
            issues.append(f"Supabase: {str(e)[:100]}")
    else:
        status = "degraded"
        issues.append("Supabase: not configured")

    uptime = int(time.time() - _start_time)
    avg_latency = int(_total_latency / _request_count) if _request_count > 0 else 0

    return jsonify({
        "status": status,
        "model": OLLAMA_MODEL,
        "model_loaded": ollama_status.get("available", False),
        "models_available": ollama_status.get("models_loaded", []),
        "db_connection": "connected" if db_connected else "disconnected",
        "uptime_seconds": uptime,
        "requests_processed": _request_count,
        "average_response_time_ms": avg_latency,
        "issues": issues if issues else None
    })
