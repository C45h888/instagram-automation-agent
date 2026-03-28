"""
Supabase Service Package
=======================
Split from the original monolith supabase_service.py into domain modules.

Package structure:
    _infra.py         — caches, Redis, circuit breaker, execute(), helpers
    _engagement.py    — EngagementService: post context, comments, accounts
    _dms.py           — DMService: conversations, messages, window status
    _content.py       — ContentService: assets, scheduled posts, publishing
    _ugc.py           — UGCService: discovery, content, permissions
    _attribution.py   — AttributionService: sales attribution, model weights
    _analytics.py     — AnalyticsService: reports, revenue, media stats
    _ops.py           — OpsService: audit_log, system_alerts, account ops
    _outbound.py      — OutboundQueueSupabase: job persistence, DLQ

Backward compatibility:
    The SupabaseService class re-exports all original static methods.
    All existing callers work without changes. To use the new clean interface,
    import the domain service directly:
        from services.supabase_service._engagement import EngagementService

Re-exported infra helpers (for existing callers that import these directly):
    supabase, execute, cache_get, cache_set,
    _redis, _redis_available, is_redis_healthy,
    post_context_cache, account_info_cache, attribution_model_cache, analytics_cache

Tool modules (for tools/ package):
    OVERSIGHT_TOOLS — @tool-decorated oversight/explainability tools
"""

from datetime import datetime, timezone, timedelta

# Re-export infrastructure helpers so existing callers don't break
from ._infra import (
    execute as _execute_query,   # alias: agent.py imports this as _execute_query
    db_breaker,
    supabase,
    logger,
    cache_get,
    cache_set,
    # Aliases for callers that used underscore-prefixed names
    cache_get as _cache_get,
    cache_set as _cache_set,
    _redis,
    _redis_available,
    is_redis_healthy,
    post_context_cache,
    account_info_cache,
    attribution_model_cache,
    analytics_cache,
)

# Domain services
from ._engagement import EngagementService
from ._dms import DMService
from ._content import ContentService
from ._ugc import UGCService
from ._attribution import AttributionService
from ._analytics import AnalyticsService
from ._ops import OpsService
from ._outbound import OutboundQueueSupabase


# ─────────────────────────────────────────
# Backward-compatible SupabaseService class
# Maps every original method to its domain service
# ─────────────────────────────────────────
class SupabaseService:

    # ── Engagement ──────────────────────────
    get_post_context = staticmethod(EngagementService.get_post_context)
    get_account_info = staticmethod(EngagementService.get_account_info)
    get_account_uuid_by_instagram_id = staticmethod(
        EngagementService.get_account_uuid_by_instagram_id
    )
    get_recent_comments = staticmethod(EngagementService.get_recent_comments)
    get_recent_post_performance = staticmethod(
        EngagementService.get_recent_post_performance
    )
    get_active_business_accounts = staticmethod(
        EngagementService.get_active_business_accounts
    )
    get_unprocessed_comments = staticmethod(
        EngagementService.get_unprocessed_comments
    )
    mark_comment_processed = staticmethod(EngagementService.mark_comment_processed)
    get_post_context_by_uuid = staticmethod(EngagementService.get_post_context_by_uuid)
    get_recent_media_ids = staticmethod(EngagementService.get_recent_media_ids)
    save_live_comments = staticmethod(EngagementService.save_live_comments)
    upsert_webhook_comment = staticmethod(EngagementService.upsert_webhook_comment)

    # ── DM ──────────────────────────────────
    get_dm_history = staticmethod(DMService.get_dm_history)
    get_dm_conversation_context = staticmethod(DMService.get_dm_conversation_context)
    get_unprocessed_dms = staticmethod(DMService.get_unprocessed_dms)
    mark_dm_processed = staticmethod(DMService.mark_dm_processed)
    save_live_conversation_messages = staticmethod(
        DMService.save_live_conversation_messages
    )

    # ── Content ───────────────────────────────
    get_asset_by_id = staticmethod(ContentService.get_asset_by_id)
    get_eligible_assets = staticmethod(ContentService.get_eligible_assets)
    get_recent_post_tags = staticmethod(ContentService.get_recent_post_tags)
    get_posts_today_count = staticmethod(ContentService.get_posts_today_count)
    create_scheduled_post = staticmethod(ContentService.create_scheduled_post)
    update_scheduled_post_status = staticmethod(
        ContentService.update_scheduled_post_status
    )
    update_asset_after_post = staticmethod(ContentService.update_asset_after_post)

    # ── UGC ─────────────────────────────────
    get_monitored_hashtags = staticmethod(UGCService.get_monitored_hashtags)
    get_existing_ugc_ids = staticmethod(UGCService.get_existing_ugc_ids)
    create_or_update_ugc = staticmethod(UGCService.create_or_update_ugc)
    create_ugc_permission = staticmethod(UGCService.create_ugc_permission)
    get_granted_ugc_permissions = staticmethod(
        UGCService.get_granted_ugc_permissions
    )
    get_ugc_content_for_repost = staticmethod(UGCService.get_ugc_content_for_repost)
    mark_ugc_reposted = staticmethod(UGCService.mark_ugc_reposted)
    get_ugc_content_by_id = staticmethod(UGCService.get_ugc_content_by_id)

    # ── Attribution ─────────────────────────
    get_order_attribution = staticmethod(AttributionService.get_order_attribution)
    get_customer_enrichment = staticmethod(AttributionService.get_customer_enrichment)
    save_attribution = staticmethod(AttributionService.save_attribution)
    queue_for_review = staticmethod(AttributionService.queue_for_review)
    get_attribution_model_weights = staticmethod(
        AttributionService.get_attribution_model_weights
    )
    update_attribution_model_weights = staticmethod(
        AttributionService.update_attribution_model_weights
    )
    get_last_week_attributions = staticmethod(
        AttributionService.get_last_week_attributions
    )

    # ── Analytics ─────────────────────────────
    get_historical_reports = staticmethod(AnalyticsService.get_historical_reports)
    save_analytics_report = staticmethod(AnalyticsService.save_analytics_report)
    get_attribution_revenue = staticmethod(
        AnalyticsService.get_attribution_revenue
    )
    get_media_stats_for_period = staticmethod(
        AnalyticsService.get_media_stats_for_period
    )

    # ── Ops ──────────────────────────────────
    log_decision = staticmethod(OpsService.log_decision)
    get_business_account = staticmethod(OpsService.get_business_account)
    mark_account_disconnected = staticmethod(OpsService.mark_account_disconnected)
    create_system_alert = staticmethod(OpsService.create_system_alert)

    # ── Outbound ────────────────────────────
    create_outbound_job = staticmethod(OutboundQueueSupabase.create_outbound_job)
    get_pending_outbound_jobs = staticmethod(
        OutboundQueueSupabase.get_pending_outbound_jobs
    )
    update_outbound_job_status = staticmethod(
        OutboundQueueSupabase.update_outbound_job_status
    )
    get_outbound_dlq = staticmethod(OutboundQueueSupabase.get_outbound_dlq)
    get_outbound_job_by_idempotency_key = staticmethod(
        OutboundQueueSupabase.get_outbound_job_by_idempotency_key
    )

    # ── DM Conversation upsert ───────────────
    # Was in the original monolith's engagement section but is DM-specific.
    # Exact backward compat with original method name.
    @staticmethod
    def upsert_webhook_dm_conversation(
        sender_id: str,
        business_account_id: str,
        timestamp: str,
    ) -> bool:
        """Create/refresh a DM conversation when a real-time DM webhook fires.

        Sets within_window=True and window_expires_at=now+24h.
        Conflict key: (business_account_id, customer_instagram_id).
        """
        if not supabase or not sender_id or not business_account_id:
            return False
        try:
            now = datetime.now(timezone.utc)
            record = {
                "customer_instagram_id": sender_id,
                "business_account_id": business_account_id,
                "within_window": True,
                "window_expires_at": (now + timedelta(hours=24)).isoformat(),
                "last_message_at": timestamp or now.isoformat(),
                "conversation_status": "active",
            }
            execute(
                supabase.table("instagram_dm_conversations")
                .upsert(record, on_conflict=["business_account_id", "customer_instagram_id"]),
                table="instagram_dm_conversations",
                operation="upsert",
            )
            return True
        except Exception:
            return False


# ================================
# Oversight Tools (for tools/ package)
# ================================
from ._oversight_tools import (
    get_audit_log_entries,
    get_run_summary,
)

OVERSIGHT_TOOLS = [
    get_audit_log_entries,
    get_run_summary,
]
