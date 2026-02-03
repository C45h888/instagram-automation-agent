"""
Prometheus Metrics Endpoint
============================
Exposes counters and histograms at GET /metrics (no auth required).
Import counters from this module in other files to instrument them.
"""

from flask import Blueprint, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

metrics_bp = Blueprint("metrics", __name__)

# ================================
# Counters
# ================================
REQUEST_COUNT = Counter(
    "agent_requests_total",
    "Total requests processed",
    ["endpoint", "status"],
)

APPROVAL_DECISIONS = Counter(
    "agent_approval_decisions_total",
    "Approval decisions by type and outcome",
    ["task_type", "decision"],
)

DB_QUERY_COUNT = Counter(
    "agent_db_queries_total",
    "Supabase queries executed",
    ["table", "operation"],
)

CACHE_HITS = Counter(
    "agent_cache_hits_total",
    "Redis cache hits",
    ["key_type"],
)

CACHE_MISSES = Counter(
    "agent_cache_misses_total",
    "Redis cache misses",
    ["key_type"],
)

TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "LLM tool invocations",
    ["tool_name"],
)

LLM_ERRORS = Counter(
    "agent_llm_errors_total",
    "LLM inference errors",
    ["error_type"],
)

# ================================
# Histograms
# ================================
REQUEST_LATENCY = Histogram(
    "agent_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)


@metrics_bp.route("/metrics", methods=["GET"])
def metrics():
    """Expose Prometheus metrics. No auth (in PUBLIC_PATHS)."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
