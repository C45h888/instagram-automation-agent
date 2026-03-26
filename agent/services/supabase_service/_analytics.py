"""
Analytics Service
================
Analytics reports, revenue attribution, and media stats.
Used by: analytics scheduler pipelines.

All methods: @staticmethod
"""

from datetime import datetime, timezone, timedelta
from pybreaker import CircuitBreakerError

from ._infra import (
    execute,
    cache_get,
    cache_set,
    analytics_cache,   # Fix #1: dedicated cache (maxsize=20, ttl=300s) instead of account_info_cache
    db_breaker,
    supabase,
    logger,
)


class AnalyticsService:
    """Analytics reports, revenue, and media stats."""

    # ─────────────────────────────────────────
    # READ: Historical Analytics Reports
    # ─────────────────────────────────────────
    @staticmethod
    def get_historical_reports(
        business_account_id: str, report_type: str, days: int = 30
    ) -> list:
        """Fetch recent analytics reports for historical comparison.

        Caching: L1 (analytics_cache, 5 min TTL, maxsize=20).
        L2 Redis intentionally skipped — reports are infrequent.
        """
        if not supabase or not business_account_id:
            return []

        cache_key = f"analytics_hist:{business_account_id}:{report_type}:{days}"

        if cache_key in analytics_cache:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="analytics_historical_l1").inc()
            return analytics_cache[cache_key]

        from metrics import CACHE_MISSES
        CACHE_MISSES.labels(key_type="analytics_historical").inc()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        try:
            result = execute(
                supabase.table("analytics_reports")
                .select(
                    "report_date, start_date, end_date, instagram_metrics, "
                    "media_metrics, revenue_metrics, insights, historical_comparison"
                )
                .eq("business_account_id", business_account_id)
                .eq("report_type", report_type)
                .gte("report_date", cutoff_str)
                .order("report_date", desc=True)
                .limit(30),
                table="analytics_reports",
                operation="select",
            )

            data = result.data or []
            analytics_cache[cache_key] = data
            return data

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping historical reports fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch historical reports for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # WRITE: Save Analytics Report
    # ─────────────────────────────────────────
    @staticmethod
    def save_analytics_report(report_data: dict) -> dict:
        """Upsert an analytics report.

        Uses ON CONFLICT (business_account_id, report_type, report_date)
        to update if a report already exists for the same day/type.
        """
        if not supabase:
            return {}

        try:
            result = execute(
                supabase.table("analytics_reports")
                .upsert(report_data, on_conflict="business_account_id,report_type,report_date"),
                table="analytics_reports",
                operation="upsert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save analytics report")
            return {}
        except Exception as e:
            logger.error(f"Failed to save analytics report: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Attribution Revenue
    # ─────────────────────────────────────────
    @staticmethod
    def get_attribution_revenue(
        business_account_id: str, start_date, end_date
    ) -> dict:
        """Aggregate revenue data from sales_attributions for a date range.

        Returns: attributed_orders, attributed_revenue, avg_order_value,
        avg_attribution_score, top_touchpoint_type.
        """
        default = {
            "attributed_orders": 0,
            "attributed_revenue": 0.0,
            "avg_order_value": 0.0,
            "avg_attribution_score": 0.0,
            "top_touchpoint_type": "none",
        }
        if not supabase or not business_account_id:
            return default

        try:
            result = execute(
                supabase.table("sales_attributions")
                .select("order_value, attribution_score, attribution_method")
                .eq("business_account_id", business_account_id)
                .gte("processed_at", str(start_date))
                .lte("processed_at", str(end_date)),
                table="sales_attributions",
                operation="select",
            )

            rows = result.data or []
            if not rows:
                return default

            total_revenue = sum(float(r.get("order_value", 0) or 0) for r in rows)
            total_orders = len(rows)
            avg_score = (
                sum(float(r.get("attribution_score", 0) or 0) for r in rows) / total_orders
            )

            method_counts = {}
            for r in rows:
                method = r.get("attribution_method", "unknown")
                method_counts[method] = method_counts.get(method, 0) + 1
            top_method = max(method_counts, key=method_counts.get) if method_counts else "none"

            return {
                "attributed_orders": total_orders,
                "attributed_revenue": round(total_revenue, 2),
                "avg_order_value": round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0,
                "avg_attribution_score": round(avg_score, 2),
                "top_touchpoint_type": top_method,
            }

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping attribution revenue fetch")
            return default
        except Exception as e:
            logger.warning(f"Failed to fetch attribution revenue for {business_account_id}: {e}")
            return default

    # ─────────────────────────────────────────
    # READ: Media Stats for Period
    # ─────────────────────────────────────────
    @staticmethod
    def get_media_stats_for_period(
        business_account_id: str, start_date, end_date
    ) -> list:
        """Fetch post metrics from instagram_media for a date range.

        DB-only fallback when backend proxy is unavailable.
        """
        if not supabase or not business_account_id:
            return []

        try:
            result = execute(
                supabase.table("instagram_media")
                .select(
                    "instagram_media_id, caption, media_type, like_count, "
                    "comments_count, reach, shares_count, published_at"
                )
                .eq("business_account_id", business_account_id)
                .gte("published_at", str(start_date))
                .lte("published_at", str(end_date))
                .order("published_at", desc=True),
                table="instagram_media",
                operation="select",
            )
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping media stats fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch media stats for {business_account_id}: {e}")
            return []
