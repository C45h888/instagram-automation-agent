"""
Analytics Reports Scheduler
=============================
Daily + weekly analytics report generation pipeline.

Mirrors engagement_monitor.py / weekly_attribution_learning.py pattern:
  - Per-account error isolation
  - Semaphore-limited concurrency
  - Prometheus metrics
  - Audit log via log_decision()

Pipeline per account:
  1. Collect IG data (3-route resilience: backend proxy > Supabase DB > fallback)
  2. Get revenue data from sales_attributions
  3. Aggregate metrics (pure Python)
  4. Historical comparison (pure Python)
  5. Rule-based recommendations (pure Python)
  6. Optional LLM insights (single AgentService.analyze_async call)
  7. Save report to Supabase
  8. Log decision to audit_log
"""

import time
import asyncio
from uuid import uuid4
from datetime import date, timedelta

from config import (
    logger,
    ANALYTICS_HISTORICAL_DAYS,
    ANALYTICS_MAX_CONCURRENT_ACCOUNTS,
    ANALYTICS_LLM_INSIGHTS_ENABLED,
)
from services.supabase_service import SupabaseService
from tools.analytics_tools import (
    collect_instagram_data,
    aggregate_metrics,
    build_historical_comparison,
    generate_recommendations,
    build_rule_based_insights,
    generate_llm_insights,
    build_report,
)


async def analytics_reports_run(report_type: str = "daily"):
    """Main entry point — called by APScheduler.

    Args:
        report_type: "daily" or "weekly"
    """
    from routes.metrics import (
        ANALYTICS_REPORT_RUNS,
        ANALYTICS_REPORT_DURATION,
    )

    run_id = str(uuid4())
    logger.info(f"[{run_id}] Analytics reports cycle starting (type={report_type})")
    start_time = time.time()

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping")
            ANALYTICS_REPORT_RUNS.labels(status="no_accounts").inc()
            return

        # Calculate date range
        today = date.today()
        if report_type == "daily":
            start_date = today - timedelta(days=1)
            end_date = today
        else:  # weekly
            start_date = today - timedelta(days=7)
            end_date = today

        logger.info(
            f"[{run_id}] Processing {len(accounts)} accounts "
            f"(range: {start_date} to {end_date})"
        )

        semaphore = asyncio.Semaphore(ANALYTICS_MAX_CONCURRENT_ACCOUNTS)
        tasks = [
            _process_account_safe(
                run_id, account, report_type, start_date, end_date, semaphore
            )
            for account in accounts
        ]
        results = await asyncio.gather(*tasks)

        # Aggregate stats
        batch_stats = {"processed": 0, "saved": 0, "llm_used": 0, "errors": 0}
        for r in results:
            for key in batch_stats:
                batch_stats[key] += r.get(key, 0)

        # Log batch summary
        SupabaseService.log_decision(
            event_type="analytics_report_cycle_complete",
            action=report_type,
            resource_type="analytics_reports",
            resource_id=run_id,
            user_id="system",
            details={"batch_stats": batch_stats, "accounts": len(accounts)},
        )

        status = "success" if batch_stats["errors"] == 0 else "partial"
        ANALYTICS_REPORT_RUNS.labels(status=status).inc()

        logger.info(f"[{run_id}] Batch stats: {batch_stats}")

    except Exception as e:
        logger.error(f"[{run_id}] Analytics reports cycle failed: {e}")
        ANALYTICS_REPORT_RUNS.labels(status="error").inc()

    finally:
        duration = time.time() - start_time
        ANALYTICS_REPORT_DURATION.observe(duration)
        logger.info(f"[{run_id}] Analytics reports cycle completed in {duration:.1f}s")


async def _process_account_safe(
    run_id: str,
    account: dict,
    report_type: str,
    start_date: date,
    end_date: date,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Error isolation wrapper — single account failure never crashes the batch."""
    async with semaphore:
        try:
            return await _process_account(
                run_id, account, report_type, start_date, end_date
            )
        except Exception as e:
            account_id = account.get("id", "unknown")
            username = account.get("username", "unknown")
            logger.error(
                f"[{run_id}] Account {username} ({account_id}) analytics failed: {e}"
            )
            return {"processed": 0, "saved": 0, "llm_used": 0, "errors": 1}


async def _process_account(
    run_id: str,
    account: dict,
    report_type: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Core per-account analytics pipeline."""
    account_id = account["id"]
    username = account.get("username", "unknown")
    stats = {"processed": 1, "saved": 0, "llm_used": 0, "errors": 0}

    logger.info(f"[{run_id}] Processing account @{username} ({account_id})")

    # 1. Collect Instagram data (3-route resilience)
    account_data, media_data, data_sources = await collect_instagram_data(
        account_id, start_date, end_date
    )

    logger.info(
        f"[{run_id}] @{username}: collected {len(media_data)} media items "
        f"from sources: {data_sources}"
    )

    # 2. Get revenue data from sales_attributions
    revenue_data = SupabaseService.get_attribution_revenue(
        account_id, start_date, end_date
    )

    # 3. Aggregate metrics (pure Python)
    aggregated = aggregate_metrics(account_data, media_data, revenue_data)

    # 4. Historical comparison (pure Python)
    historical = SupabaseService.get_historical_reports(
        account_id, report_type, ANALYTICS_HISTORICAL_DAYS
    )
    comparison = build_historical_comparison(aggregated, historical)

    # 5. Rule-based recommendations (pure Python)
    recommendations = generate_recommendations(aggregated, comparison)

    # 6. Insights (optional LLM or rule-based fallback)
    if ANALYTICS_LLM_INSIGHTS_ENABLED:
        insights = await generate_llm_insights(aggregated, comparison, recommendations)
        if insights.get("source") == "llm":
            stats["llm_used"] = 1
            logger.info(f"[{run_id}] @{username}: LLM insights generated")
    else:
        insights = build_rule_based_insights(aggregated, comparison, recommendations)

    # 7. Build and save report
    report = build_report(
        account_id, report_type, start_date, end_date,
        aggregated, comparison, insights, data_sources, run_id,
    )
    saved = SupabaseService.save_analytics_report(report)

    if saved:
        stats["saved"] = 1
        from routes.metrics import ANALYTICS_REPORTS_GENERATED
        ANALYTICS_REPORTS_GENERATED.labels(report_type=report_type).inc()

        # 8. Log decision to audit trail
        SupabaseService.log_decision(
            event_type="analytics_report_generated",
            action=f"{report_type}_report",
            resource_type="analytics_reports",
            resource_id=saved.get("id", ""),
            user_id="system",
            details={
                "account_id": account_id,
                "username": username,
                "data_sources": data_sources,
                "engagement_rate": aggregated["instagram_metrics"]["avg_engagement_rate"],
                "posts_in_period": aggregated["media_metrics"]["total_posts_in_period"],
                "insights_source": insights.get("source", "unknown"),
                "recommendations_count": len(recommendations),
            },
        )

        logger.info(
            f"[{run_id}] @{username}: {report_type} report saved "
            f"(engagement: {aggregated['instagram_metrics']['avg_engagement_rate']}%, "
            f"insights: {insights.get('source', 'unknown')})"
        )
    else:
        stats["errors"] = 1
        logger.error(f"[{run_id}] @{username}: failed to save {report_type} report")

    return stats
