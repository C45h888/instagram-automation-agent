"""
Prometheus Metrics Endpoint
============================
Re-exports all counters/histograms from the top-level metrics module
and exposes them at GET /metrics (no auth required).
All definitions live in agent/metrics.py to avoid circular imports.
"""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Re-export everything so existing `from routes.metrics import X` calls keep working
from metrics import (  # noqa: F401
    REQUEST_COUNT, APPROVAL_DECISIONS, REQUEST_LATENCY,
    TOOL_CALLS, LLM_ERRORS,
    DB_QUERY_COUNT, CACHE_HITS, CACHE_MISSES,
    OVERSIGHT_CHAT_QUERIES,
    ENGAGEMENT_MONITOR_RUNS, ENGAGEMENT_MONITOR_COMMENTS, ENGAGEMENT_MONITOR_DURATION,
    CONTENT_SCHEDULER_RUNS, CONTENT_SCHEDULER_POSTS, CONTENT_SCHEDULER_DURATION,
    ATTRIBUTION_RUNS, ATTRIBUTION_RESULTS, ATTRIBUTION_SCORES,
    ATTRIBUTION_DURATION, ATTRIBUTION_TOUCHPOINTS,
    WEEKLY_LEARNING_RUNS,
    UGC_COLLECTION_RUNS, UGC_COLLECTION_ITEMS, UGC_COLLECTION_DURATION,
    ANALYTICS_REPORT_RUNS, ANALYTICS_REPORTS_GENERATED, ANALYTICS_REPORT_DURATION,
    OUTBOUND_QUEUE_ENQUEUED, OUTBOUND_QUEUE_EXECUTE, OUTBOUND_QUEUE_RETRIES,
    OUTBOUND_QUEUE_DLQ, AUTH_FAILURE_DISCONNECTS, OUTBOUND_QUEUE_DEPTH, OUTBOUND_QUEUE_LATENCY,
    HEARTBEAT_SENDS,
)

metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics():
    """Expose Prometheus metrics. No auth (in PUBLIC_PATHS)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
