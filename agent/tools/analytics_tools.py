"""
Analytics Tools
================
Pure-Python aggregation, comparison, recommendation, and optional LLM insights
for the analytics reports pipeline.

Called by scheduler/analytics_reports.py —
NOT registered as LangChain tools (internal pipeline functions).

Mirrors attribution_tools.py / content_tools.py pattern:
pure functions for deterministic math, single LLM call via
AgentService.analyze_async() for optional insights.
"""

import json
import asyncio
import logging
from datetime import date, datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    logger,
    BACKEND_ACCOUNT_INSIGHTS_ENDPOINT,
    BACKEND_MEDIA_INSIGHTS_ENDPOINT,
    BACKEND_TIMEOUT_SECONDS,
    ANALYTICS_LLM_INSIGHTS_ENABLED,
)


# ================================
# Singleton Agent / Prompt Service (lazy import to avoid circular)
# ================================
_agent_service = None
_prompt_service = None


def _get_agent_service():
    global _agent_service
    if _agent_service is None:
        from services.agent_service import AgentService
        _agent_service = AgentService()
    return _agent_service


def _get_prompt_service():
    global _prompt_service
    if _prompt_service is None:
        from services.prompt_service import PromptService
        _prompt_service = PromptService
    return _prompt_service


# ================================
# Backend Proxy Fetchers (3-route resilience)
# ================================

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_account_insights(business_account_id: str, since: str, until: str) -> dict:
    """Backend proxy call for account-level IG metrics with retry."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_ACCOUNT_INSIGHTS_ENDPOINT,
            params={
                "business_account_id": business_account_id,
                "since": since,
                "until": until,
            },
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _call_backend_media_insights(business_account_id: str, since: str, until: str) -> dict:
    """Backend proxy call for post-level IG metrics with retry."""
    with httpx.Client(timeout=BACKEND_TIMEOUT_SECONDS) as client:
        response = client.get(
            BACKEND_MEDIA_INSIGHTS_ENDPOINT,
            params={
                "business_account_id": business_account_id,
                "since": since,
                "until": until,
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_account_insights(
    business_account_id: str,
    since: str,
    until: str,
) -> dict | None:
    """Fetch account-level IG metrics via backend proxy.

    Returns data dict on success, None on failure (caller falls back to Supabase DB).
    """
    try:
        response = await asyncio.to_thread(
            _call_backend_account_insights, business_account_id, since, until
        )
        if response.get("success") and response.get("data"):
            return response["data"]
        logger.warning(f"Backend proxy returned no data for account insights: {response}")
        return None
    except Exception as e:
        logger.warning(f"Backend proxy failed for account insights ({business_account_id}): {e}")
        return None


async def fetch_media_insights(
    business_account_id: str,
    since: str,
    until: str,
) -> list | None:
    """Fetch post-level IG metrics via backend proxy.

    Returns list of media dicts on success, None on failure.
    """
    try:
        response = await asyncio.to_thread(
            _call_backend_media_insights, business_account_id, since, until
        )
        if response.get("success") and response.get("data"):
            return response["data"]
        logger.warning(f"Backend proxy returned no data for media insights: {response}")
        return None
    except Exception as e:
        logger.warning(f"Backend proxy failed for media insights ({business_account_id}): {e}")
        return None


# ================================
# Data Collection (3-Route Resilience)
# ================================

async def collect_instagram_data(
    business_account_id: str,
    start_date: date,
    end_date: date,
) -> tuple[dict, list, list]:
    """Collect Instagram data from available sources.

    Returns: (account_metrics, media_list, data_sources_used)

    Priority: backend proxy > Supabase DB > empty fallback.
    Webhook data is always in DB (no separate route needed).
    """
    from services.supabase_service import SupabaseService

    data_sources = []

    # Route 1: Try backend proxy for both account + media insights
    proxy_account = await fetch_account_insights(
        business_account_id, str(start_date), str(end_date)
    )
    proxy_media = await fetch_media_insights(
        business_account_id, str(start_date), str(end_date)
    )

    # Resolve account metrics
    if proxy_account:
        data_sources.append("backend_proxy")
        account_metrics = proxy_account
    else:
        # Route 2: Fall back to Supabase DB
        account_metrics = SupabaseService.get_account_follower_snapshot(business_account_id)
        # Account-level reach/impressions not available from DB alone

    # Resolve media metrics
    if proxy_media:
        if "backend_proxy" not in data_sources:
            data_sources.append("backend_proxy")
        media_list = proxy_media
    else:
        # Route 2: Fall back to Supabase DB
        if "supabase_db" not in data_sources:
            data_sources.append("supabase_db")
        media_list = SupabaseService.get_media_stats_for_period(
            business_account_id, start_date, end_date
        )

    return account_metrics, media_list, data_sources


# ================================
# Pure Python Aggregation
# ================================

def _extract_post_summary(post: dict) -> dict:
    """Extract summary dict from a post for best/worst identification."""
    caption = post.get("caption") or ""
    return {
        "media_id": post.get("instagram_media_id") or post.get("id", ""),
        "caption_preview": (caption[:80] + "...") if len(caption) > 80 else caption,
        "engagement": (post.get("like_count", 0) or 0) + (post.get("comments_count", 0) or 0),
        "reach": post.get("reach", 0) or post.get("insights", {}).get("reach", 0) or 0,
        "media_type": post.get("media_type", "UNKNOWN"),
    }


def aggregate_metrics(
    account_data: dict,
    media_data: list,
    revenue_data: dict,
) -> dict:
    """Pure Python aggregation — mirrors N8N 'Aggregate Analytics' JS node.

    Returns dict with instagram_metrics, media_metrics, revenue_metrics keys.
    """
    # Instagram account-level metrics
    # Prefer proxy data, fall back to summing from media posts
    total_reach = account_data.get("reach") or sum(
        (m.get("reach", 0) or 0) for m in media_data
    )
    total_impressions = account_data.get("impressions") or sum(
        (m.get("insights", {}).get("impressions", 0) if isinstance(m.get("insights"), dict) else 0)
        for m in media_data
    )
    profile_views = account_data.get("profile_views", 0) or 0
    website_clicks = account_data.get("website_clicks", 0) or 0
    followers = account_data.get("follower_count") or account_data.get("followers_count", 0) or 0

    # Post-level aggregation
    total_likes = sum((m.get("like_count", 0) or 0) for m in media_data)
    total_comments = sum((m.get("comments_count", 0) or 0) for m in media_data)
    total_saves = sum(
        (m.get("insights", {}).get("saved", 0) if isinstance(m.get("insights"), dict) else 0)
        for m in media_data
    )
    total_shares = sum((m.get("shares_count", 0) or 0) for m in media_data)
    posts_count = len(media_data)

    # Engagement rate: (likes + comments + saves + shares) / reach * 100
    total_engagement = total_likes + total_comments + total_saves + total_shares
    engagement_rate = round(
        (total_engagement / total_reach * 100), 2
    ) if total_reach > 0 else 0.0

    # Best/worst post by engagement
    sorted_posts = sorted(
        media_data,
        key=lambda p: (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0),
        reverse=True,
    )
    best_post = _extract_post_summary(sorted_posts[0]) if sorted_posts else None
    worst_post = _extract_post_summary(sorted_posts[-1]) if len(sorted_posts) > 1 else None

    # By media type breakdown
    by_type = {}
    for post in media_data:
        mt = post.get("media_type", "UNKNOWN")
        if mt not in by_type:
            by_type[mt] = {"count": 0, "total_engagement": 0}
        by_type[mt]["count"] += 1
        by_type[mt]["total_engagement"] += (
            (post.get("like_count", 0) or 0) + (post.get("comments_count", 0) or 0)
        )
    for mt in by_type:
        by_type[mt]["avg_engagement"] = round(
            by_type[mt]["total_engagement"] / by_type[mt]["count"], 1
        )

    return {
        "instagram_metrics": {
            "reach": total_reach,
            "impressions": total_impressions,
            "profile_views": profile_views,
            "website_clicks": website_clicks,
            "followers_count": followers,
            "posts_published": posts_count,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_saves": total_saves,
            "total_shares": total_shares,
            "avg_engagement_rate": engagement_rate,
        },
        "media_metrics": {
            "total_posts_in_period": posts_count,
            "best_post": best_post,
            "worst_post": worst_post,
            "by_media_type": by_type,
            "avg_likes_per_post": round(total_likes / posts_count, 1) if posts_count > 0 else 0,
            "avg_comments_per_post": round(total_comments / posts_count, 1) if posts_count > 0 else 0,
        },
        "revenue_metrics": revenue_data,
    }


# ================================
# Historical Comparison
# ================================

def build_historical_comparison(aggregated: dict, historical_reports: list) -> dict:
    """Compare current aggregated metrics against most recent historical report.

    Pure Python — mirrors N8N 'Generate Insights' comparison logic.
    """
    if not historical_reports:
        return {
            "previous_period": None,
            "changes": {},
            "note": "No historical data available",
        }

    previous = historical_reports[0]  # Most recent
    prev_ig = previous.get("instagram_metrics", {})
    prev_rev = previous.get("revenue_metrics", {})
    curr_ig = aggregated["instagram_metrics"]
    curr_rev = aggregated["revenue_metrics"]

    def _pct_change(current, prev):
        if prev == 0:
            return 100.0 if current > 0 else 0.0
        return round((current - prev) / prev * 100, 1)

    def _trend(change_pct):
        if change_pct > 1:
            return "up"
        elif change_pct < -1:
            return "down"
        return "flat"

    metrics_to_compare = [
        ("reach", curr_ig, prev_ig),
        ("impressions", curr_ig, prev_ig),
        ("avg_engagement_rate", curr_ig, prev_ig),
        ("total_likes", curr_ig, prev_ig),
        ("total_comments", curr_ig, prev_ig),
        ("website_clicks", curr_ig, prev_ig),
        ("profile_views", curr_ig, prev_ig),
        ("attributed_revenue", curr_rev, prev_rev),
        ("attributed_orders", curr_rev, prev_rev),
    ]

    changes = {}
    for metric, curr_dict, prev_dict in metrics_to_compare:
        curr_val = curr_dict.get(metric, 0) or 0
        prev_val = prev_dict.get(metric, 0) or 0
        change = _pct_change(curr_val, prev_val)
        changes[metric] = {
            "previous": prev_val,
            "current": curr_val,
            "change_pct": change,
            "trend": _trend(change),
        }

    return {
        "previous_period": {
            "start_date": str(previous.get("start_date", "")),
            "end_date": str(previous.get("end_date", "")),
        },
        "changes": changes,
    }


# ================================
# Rule-Based Recommendations (from N8N logic + enhancements)
# ================================

def generate_recommendations(aggregated: dict, comparison: dict) -> list:
    """Rule-based recommendation engine — mirrors N8N hardcoded rules + enhancements."""
    recommendations = []
    ig = aggregated["instagram_metrics"]
    changes = comparison.get("changes", {})

    # Rule 1: Low engagement (from N8N: engagement_rate < 2%)
    if ig["avg_engagement_rate"] < 2.0:
        recommendations.append(
            "Engagement rate is below 2%. Try interactive content like polls, "
            "questions, and carousel posts to boost interaction."
        )

    # Rule 2: Low posting frequency (from N8N: weekly posts < 7)
    posts = ig["posts_published"]
    if posts < 7:
        recommendations.append(
            f"Only {posts} posts published this period. Consider increasing posting "
            "frequency to at least once daily for better reach."
        )

    # Rule 3: Low CTR (from N8N: clicks < 2% of reach)
    if ig["reach"] > 0 and ig["website_clicks"] / ig["reach"] < 0.02:
        recommendations.append(
            "Website click-through rate is below 2% of reach. Improve your link "
            "in bio and add stronger calls-to-action in captions."
        )

    # Rule 4: Low conversion (from N8N: conversion_rate < 1%)
    rev = aggregated["revenue_metrics"]
    if rev.get("attributed_orders", 0) > 0 and ig["website_clicks"] > 0:
        conv_rate = rev["attributed_orders"] / ig["website_clicks"] * 100
        if conv_rate < 1.0:
            recommendations.append(
                "Conversion rate from Instagram traffic is below 1%. Consider using "
                "Instagram Shopping features and optimizing your landing page."
            )

    # Rule 5: Engagement declining
    eng_change = changes.get("avg_engagement_rate", {})
    if eng_change.get("trend") == "down" and abs(eng_change.get("change_pct", 0)) > 10:
        recommendations.append(
            f"Engagement rate dropped {abs(eng_change['change_pct']):.1f}% vs previous "
            "period. Consider testing new content formats or posting at different times."
        )

    # Rule 6: Revenue increasing — positive reinforcement
    rev_change = changes.get("attributed_revenue", {})
    if rev_change.get("trend") == "up" and rev_change.get("change_pct", 0) > 15:
        recommendations.append(
            f"Instagram-attributed revenue up {rev_change['change_pct']:.1f}%! "
            "Double down on the content types driving sales."
        )

    # Rule 7: Saves are high relative to likes — content is valuable
    if ig["total_saves"] > 0 and ig["total_likes"] > 0:
        save_ratio = ig["total_saves"] / ig["total_likes"]
        if save_ratio > 0.1:
            recommendations.append(
                "High save-to-like ratio indicates your content is highly valuable. "
                "Create more educational or reference-worthy posts."
            )

    return recommendations


# ================================
# Rule-Based Insights Fallback
# ================================

def build_rule_based_insights(
    aggregated: dict,
    comparison: dict,
    recommendations: list,
) -> dict:
    """Fallback insights when LLM is disabled or fails."""
    trends = []
    changes = comparison.get("changes", {})

    for metric in ["reach", "impressions", "avg_engagement_rate", "attributed_revenue"]:
        data = changes.get(metric, {})
        if data.get("trend") in ("up", "down"):
            direction = "increased" if data["trend"] == "up" else "decreased"
            label = metric.replace("_", " ").title()
            trends.append(f"{label} {direction} by {abs(data['change_pct']):.1f}%")

    best = aggregated["media_metrics"].get("best_post")

    return {
        "trends": trends,
        "recommendations": recommendations,
        "best_performing_content": best or {},
        "key_takeaways": trends[:3] if trends else ["Insufficient historical data for trend analysis"],
        "source": "rule_based",
    }


# ================================
# Optional LLM Insights
# ================================

async def generate_llm_insights(
    aggregated: dict,
    comparison: dict,
    recommendations: list,
) -> dict:
    """Single LLM call for deeper insights.

    Only called when ANALYTICS_LLM_INSIGHTS_ENABLED=true.
    Uses AgentService.analyze_async() — mirrors content_tools.py pattern.
    """
    agent_svc = _get_agent_service()
    prompt_svc = _get_prompt_service()

    prompt_template = prompt_svc.get_prompt("generate_analytics_insights")
    prompt = prompt_template.format(
        instagram_metrics=json.dumps(aggregated["instagram_metrics"], indent=2),
        media_metrics=json.dumps(aggregated["media_metrics"], indent=2),
        revenue_metrics=json.dumps(aggregated["revenue_metrics"], indent=2),
        historical_comparison=json.dumps(comparison, indent=2),
        rule_recommendations=json.dumps(recommendations, indent=2),
    )

    try:
        result = await agent_svc.analyze_async(prompt)
        if "error" not in result:
            return {
                "trends": result.get("trends", []),
                "recommendations": result.get("recommendations", recommendations),
                "best_performing_content": result.get("best_performing_content", {}),
                "key_takeaways": result.get("key_takeaways", []),
                "source": "llm",
            }
    except Exception as e:
        logger.warning(f"LLM insights generation failed, falling back to rule-based: {e}")

    # Fallback to rule-based
    return build_rule_based_insights(aggregated, comparison, recommendations)


# ================================
# Report Builder
# ================================

def build_report(
    business_account_id: str,
    report_type: str,
    start_date: date,
    end_date: date,
    aggregated: dict,
    comparison: dict,
    insights: dict,
    data_sources: list,
    run_id: str,
) -> dict:
    """Build the final report dict ready for save_analytics_report()."""
    return {
        "business_account_id": business_account_id,
        "report_type": report_type,
        "report_date": str(end_date),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "instagram_metrics": aggregated["instagram_metrics"],
        "media_metrics": aggregated["media_metrics"],
        "revenue_metrics": aggregated["revenue_metrics"],
        "insights": insights,
        "historical_comparison": comparison,
        "run_id": run_id,
        "data_sources": data_sources,
    }
