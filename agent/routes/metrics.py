"""
Prometheus Metrics Endpoint
============================
Exposes counters and histograms at GET /metrics (no auth required).
Import counters from this module in other files to instrument them.
"""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

metrics_router = APIRouter()

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

OVERSIGHT_CHAT_QUERIES = Counter(
    "agent_oversight_chat_queries_total",
    "Oversight Brain chat queries by status",
    ["status"],  # started, success, error
)

# ================================
# Engagement Monitor Metrics
# ================================
ENGAGEMENT_MONITOR_RUNS = Counter(
    "agent_engagement_monitor_runs_total",
    "Engagement monitor cycles completed",
    ["status"],  # success, error, partial, no_accounts
)

ENGAGEMENT_MONITOR_COMMENTS = Counter(
    "agent_engagement_monitor_comments_total",
    "Comments processed by engagement monitor",
    ["action"],  # replied, escalated, skipped, error
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

ENGAGEMENT_MONITOR_DURATION = Histogram(
    "agent_engagement_monitor_duration_seconds",
    "Duration of engagement monitor cycle",
    buckets=[5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
)

# ================================
# Content Scheduler Metrics
# ================================
CONTENT_SCHEDULER_RUNS = Counter(
    "agent_content_scheduler_runs_total",
    "Content scheduler cycles completed",
    ["status"],  # success, error, partial, no_accounts
)

CONTENT_SCHEDULER_POSTS = Counter(
    "agent_content_scheduler_posts_total",
    "Posts processed by content scheduler",
    ["action"],  # approved, rejected, published, failed, no_assets, error
)

CONTENT_SCHEDULER_DURATION = Histogram(
    "agent_content_scheduler_duration_seconds",
    "Duration of content scheduler cycle",
    buckets=[5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
)


# ================================
# Sales Attribution Metrics
# ================================
ATTRIBUTION_RUNS = Counter(
    "agent_attribution_runs_total",
    "Attribution webhook calls",
    ["status"],  # started, success, error, invalid_signature, parse_error, hard_rule, fast_path
)

ATTRIBUTION_RESULTS = Counter(
    "agent_attribution_results_total",
    "Attribution outcomes",
    ["action"],  # auto_approved, queued_review, fast_path_approved, error
)

ATTRIBUTION_SCORES = Histogram(
    "agent_attribution_scores",
    "Attribution score distribution",
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

ATTRIBUTION_DURATION = Histogram(
    "agent_attribution_duration_seconds",
    "Attribution processing time",
    buckets=[1.0, 2.5, 5.0, 10.0, 15.0, 30.0],
)

ATTRIBUTION_TOUCHPOINTS = Histogram(
    "agent_attribution_touchpoints",
    "Touchpoints per attribution",
    buckets=[0, 1, 2, 3, 5, 10, 20],
)

# ================================
# Weekly Learning Metrics
# ================================
WEEKLY_LEARNING_RUNS = Counter(
    "agent_weekly_learning_runs_total",
    "Weekly learning cycles",
    ["status"],  # success, error, partial, no_accounts
)

# ================================
# UGC Collection Metrics
# ================================
UGC_COLLECTION_RUNS = Counter(
    "agent_ugc_collection_runs_total",
    "UGC discovery cycles completed",
    ["status"],  # success, error, partial, no_accounts
)

UGC_COLLECTION_ITEMS = Counter(
    "agent_ugc_collection_items_total",
    "UGC posts processed by discovery",
    ["action"],  # high_quality, moderate, discarded, duplicates_skipped, dms_sent, errors
)

UGC_COLLECTION_DURATION = Histogram(
    "agent_ugc_collection_duration_seconds",
    "Duration of UGC discovery cycle",
    buckets=[10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

# ================================
# Analytics Reports Metrics
# ================================
ANALYTICS_REPORT_RUNS = Counter(
    "agent_analytics_report_runs_total",
    "Analytics report cycles completed",
    ["status"],  # success, partial, error, no_accounts
)

ANALYTICS_REPORTS_GENERATED = Counter(
    "agent_analytics_reports_generated_total",
    "Analytics reports generated",
    ["report_type"],  # daily, weekly
)

ANALYTICS_REPORT_DURATION = Histogram(
    "agent_analytics_report_duration_seconds",
    "Duration of analytics report cycle",
    buckets=[5.0, 15.0, 30.0, 60.0, 120.0, 300.0],
)


@metrics_router.get("/metrics")
async def metrics():
    """Expose Prometheus metrics. No auth (in PUBLIC_PATHS)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
