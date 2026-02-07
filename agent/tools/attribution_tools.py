"""
Sales Attribution Tools
========================
Pure-Python signal detection, journey reconstruction, multi-touch attribution,
and LLM-powered quality validation.

Called by webhook_order.py and weekly_attribution_learning.py —
NOT registered as LangChain tools (internal pipeline functions).

Mirrors content_tools.py pattern: pure functions for deterministic math,
single LLM call via AgentService.analyze_async() for validation.
"""

import math
from datetime import datetime, timezone

from config import (
    logger,
    SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD,
    SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD,
    SALES_ATTRIBUTION_MAX_TOUCHPOINTS,
    SALES_ATTRIBUTION_VERSION,
)


# ================================
# Singleton Agent Service (lazy import to avoid circular)
# ================================
_agent_service = None


def _get_agent_service():
    global _agent_service
    if _agent_service is None:
        from services.agent_service import AgentService
        _agent_service = AgentService()
    return _agent_service


# ================================
# Signal Detection (Pure Python)
# ================================

def detect_utm_signals(order: dict) -> list:
    """Detect attribution signals from UTM parameters.

    Mirrors N8N UTM Detector: checks utm_source, utm_medium, utm_campaign.
    """
    signals = []
    utm_source = (order.get("utm_source") or "").strip().lower()
    utm_medium = (order.get("utm_medium") or "").strip().lower()
    utm_campaign = (order.get("utm_campaign") or "").strip()
    utm_content = (order.get("utm_content") or "").strip()

    if not utm_source:
        return signals

    is_instagram = utm_source in ("instagram", "ig") or "instagram" in utm_source
    signals.append({
        "type": "utm",
        "source": utm_source,
        "medium": utm_medium,
        "campaign": utm_campaign,
        "content": utm_content,
        "strength": "high" if is_instagram else "medium",
    })

    return signals


def detect_discount_signals(order: dict) -> list:
    """Detect attribution signals from discount/promo codes.

    Mirrors N8N Discount Code Analyzer.
    Instagram-specific codes (ig_, insta_, etc.) get high strength.
    """
    signals = []
    code = (order.get("discount_code") or "").strip()

    if not code:
        return signals

    code_lower = code.lower()
    ig_patterns = ("ig_", "insta_", "instagram_", "ig-", "insta-",
                   "igpost", "igreel", "igstory")
    is_instagram_code = any(code_lower.startswith(p) or p in code_lower for p in ig_patterns)

    signals.append({
        "type": "discount_code",
        "code": code,
        "is_instagram_code": is_instagram_code,
        "strength": "high" if is_instagram_code else "low",
    })

    return signals


def detect_tag_signals(order: dict, customer_history: dict = None) -> list:
    """Detect signals from customer tags and engagement history.

    Mirrors N8N Customer History + Social Tags detectors.
    """
    signals = []

    # Customer tags
    tags = order.get("customer_tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    ig_tags = [t for t in tags if any(
        kw in t.lower() for kw in ("instagram", "ig", "social", "influencer")
    )]

    if ig_tags:
        signals.append({
            "type": "customer_tag",
            "tags": ig_tags,
            "strength": "medium",
        })

    # Repeat customer + engagement history from DB
    if customer_history:
        purchase_count = customer_history.get("purchase_count", 0) or 0
        if purchase_count > 1:
            signals.append({
                "type": "repeat_customer",
                "purchase_count": purchase_count,
                "total_spend": customer_history.get("total_spend", 0),
                "strength": "medium",
            })

        ig_interactions = customer_history.get("instagram_interactions", 0) or 0
        if ig_interactions > 0:
            signals.append({
                "type": "instagram_engagement_history",
                "interaction_count": ig_interactions,
                "strength": "high" if ig_interactions >= 5 else "medium",
            })

    return signals


def detect_all_signals(order: dict, customer_history: dict = None) -> list:
    """Run all signal detectors and combine results.

    Mirrors N8N Merge node that combines 4 parallel detector outputs.
    """
    signals = []
    signals.extend(detect_utm_signals(order))
    signals.extend(detect_discount_signals(order))
    signals.extend(detect_tag_signals(order, customer_history))
    return signals


# ================================
# Strategy Classification (LLM fast-path optimization)
# ================================

def classify_signal_strategy(signals: list) -> str:
    """Classify signal strength to determine if LLM is needed.

    - high_signal: Direct UTM from Instagram or shopping → skip LLM
    - medium_signal: Discount codes or customer tags → LLM validates
    - low_signal: No strong signals → LLM validates
    """
    for s in signals:
        signal_type = s.get("type", "")
        strength = s.get("strength", "")

        # High confidence: direct Instagram UTM or shopping
        if signal_type == "utm" and strength == "high":
            return "high_signal"
        if signal_type == "instagram_engagement_history" and strength == "high":
            return "high_signal"

    # Medium: has some signals but not conclusive
    if signals:
        return "medium_signal"

    return "low_signal"


def build_fast_path_evaluation(signals: list, attribution_score: float) -> dict:
    """Generate evaluation result without LLM for HIGH_SIGNAL orders.

    Called when classify_signal_strategy returns "high_signal".
    Saves LLM tokens and ~2-5s latency on obvious attributions.
    """
    primary = _determine_primary_method(signals)
    return {
        "quality_score": 8.5,
        "approved": True,
        "concerns": [],
        "fraud_risk": "low",
        "logical_consistency": "strong",
        "reasoning": (
            f"Direct Instagram attribution via {primary} — "
            f"high confidence ({attribution_score:.1f}/100), no LLM needed"
        ),
    }


# ================================
# Journey & Models (Pure Python)
# ================================

def build_customer_journey(
    engagements: list,
    order_date: datetime,
    max_touchpoints: int = None,
) -> dict:
    """Build customer journey timeline with time-decay weights.

    Mirrors N8N Journey Reconstruction: exponential decay with half-life of 7 days.
    Newer touchpoints get higher weight.
    """
    if max_touchpoints is None:
        max_touchpoints = SALES_ATTRIBUTION_MAX_TOUCHPOINTS

    if not engagements:
        return {
            "touchpoints": [],
            "total_touchpoints": 0,
            "days_to_purchase": 0,
            "first_touch_date": None,
            "last_touch_date": None,
            "journey_summary": "No engagement data found",
        }

    # Sort by timestamp ascending, cap at max
    sorted_engagements = sorted(
        engagements,
        key=lambda e: e.get("timestamp", ""),
    )[:max_touchpoints]

    touchpoints = []
    for eng in sorted_engagements:
        ts_str = eng.get("timestamp", "")
        if isinstance(ts_str, str) and ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                ts = datetime.now(timezone.utc)
        elif isinstance(ts_str, datetime):
            ts = ts_str
        else:
            ts = datetime.now(timezone.utc)

        days_before = max((order_date - ts).total_seconds() / 86400, 0)
        # Exponential decay: half-life of 7 days
        weight = math.exp(-0.693 * days_before / 7.0)

        touchpoints.append({
            "type": eng.get("engagement_type", "unknown"),
            "timestamp": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            "weight": round(weight, 4),
            "content_id": eng.get("content_id") or eng.get("post_id", ""),
            "metadata": eng.get("metadata", {}),
        })

    first_ts = touchpoints[0]["timestamp"] if touchpoints else None
    last_ts = touchpoints[-1]["timestamp"] if touchpoints else None

    # Days to purchase
    days_to_purchase = 0
    if first_ts:
        try:
            first_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            days_to_purchase = max(int((order_date - first_dt).total_seconds() / 86400), 0)
        except (ValueError, TypeError):
            pass

    # Build summary
    type_counts = {}
    for tp in touchpoints:
        tp_type = tp["type"]
        type_counts[tp_type] = type_counts.get(tp_type, 0) + 1

    summary_parts = [f"{count} {eng_type}(s)" for eng_type, count in type_counts.items()]
    journey_summary = (
        f"{len(touchpoints)} touchpoints over {days_to_purchase} days: "
        + ", ".join(summary_parts)
    )

    return {
        "touchpoints": touchpoints,
        "total_touchpoints": len(touchpoints),
        "days_to_purchase": days_to_purchase,
        "first_touch_date": first_ts,
        "last_touch_date": last_ts,
        "journey_summary": journey_summary,
    }


def calculate_multi_touch_models(
    signals: list,
    touchpoints: list,
    weights: dict = None,
) -> dict:
    """Calculate attribution scores using 4 multi-touch models.

    Mirrors N8N Attribution Calculator: last_touch 40%, first_touch 20%,
    linear 20%, time_decay 20% (or custom weights from DB).
    """
    if weights is None:
        weights = {
            "last_touch": 0.40, "first_touch": 0.20,
            "linear": 0.20, "time_decay": 0.20,
        }

    signal_count = len(signals)
    tp_count = len(touchpoints)

    # Base score from signal strength
    strength_scores = {"high": 30, "medium": 20, "low": 10}
    signal_score = sum(
        strength_scores.get(s.get("strength", "low"), 10)
        for s in signals
    )
    # Normalize signal score to 0-100
    max_possible = signal_count * 30 if signal_count > 0 else 1
    normalized_signal = min((signal_score / max_possible) * 100, 100)

    # Touchpoint score (more touchpoints = higher confidence, capped)
    tp_score = min(tp_count * 5, 50)

    # Last touch: most credit to most recent touchpoint
    last_touch = normalized_signal if tp_count > 0 else normalized_signal * 0.5

    # First touch: credit to first touchpoint (awareness)
    first_touch = normalized_signal * 0.8 if tp_count > 0 else normalized_signal * 0.3

    # Linear: equal credit across all touchpoints
    linear = (normalized_signal * 0.6 + tp_score) if tp_count > 0 else normalized_signal * 0.4

    # Time decay: weighted by recency
    if touchpoints:
        total_weight = sum(tp.get("weight", 0) for tp in touchpoints)
        max_weight = tp_count
        decay_ratio = total_weight / max_weight if max_weight > 0 else 0.5
        time_decay = normalized_signal * decay_ratio + tp_score * 0.5
    else:
        time_decay = normalized_signal * 0.3

    # Cap all at 100
    scores = {
        "last_touch": min(round(last_touch, 2), 100),
        "first_touch": min(round(first_touch, 2), 100),
        "linear": min(round(linear, 2), 100),
        "time_decay": min(round(time_decay, 2), 100),
    }

    # Final weighted score
    final = (
        scores["last_touch"] * weights.get("last_touch", 0.40)
        + scores["first_touch"] * weights.get("first_touch", 0.20)
        + scores["linear"] * weights.get("linear", 0.20)
        + scores["time_decay"] * weights.get("time_decay", 0.20)
    )
    scores["final_weighted"] = min(round(final, 2), 100)

    return scores


def apply_hard_rules(
    evaluation: dict,
    attribution_score: float,
    auto_approve_threshold: float = None,
    fraud_threshold: float = None,
) -> dict:
    """Override LLM evaluation with hard rules.

    Mirrors _apply_hard_rules from content_tools.py.
    """
    if auto_approve_threshold is None:
        auto_approve_threshold = SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD
    if fraud_threshold is None:
        fraud_threshold = SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD

    result = dict(evaluation)
    reasons = []

    # Normalize quality_score (LLM may return 0-10 scale)
    quality_score = result.get("quality_score", 0)
    if isinstance(quality_score, (int, float)) and quality_score > 10:
        quality_score = quality_score / 10.0
    elif isinstance(quality_score, (int, float)) and quality_score > 1:
        quality_score = quality_score / 10.0

    # Rule 1: Attribution score below threshold
    normalized_attr = attribution_score / 100.0
    if normalized_attr < auto_approve_threshold:
        result["approved"] = False
        reasons.append(
            f"Attribution score {attribution_score:.1f}/100 "
            f"({normalized_attr:.2f}) below threshold ({auto_approve_threshold})"
        )

    # Rule 2: Quality score below threshold
    if quality_score < auto_approve_threshold:
        result["approved"] = False
        reasons.append(
            f"Quality score {result.get('quality_score', 0)} "
            f"({quality_score:.2f}) below threshold ({auto_approve_threshold})"
        )

    # Rule 3: Fraud risk is high
    if result.get("fraud_risk", "low") == "high":
        result["approved"] = False
        reasons.append("High fraud risk detected")

    if reasons:
        existing = result.get("concerns", []) or []
        result["concerns"] = existing + reasons

    return result


# ================================
# LLM Evaluation (MEDIUM/LOW signal only)
# ================================

async def evaluate_attribution(
    order: dict,
    signals: list,
    journey: dict,
    model_scores: dict,
) -> dict:
    """Single LLM call for quality validation of attribution results.

    Only called for MEDIUM/LOW signal orders. HIGH_SIGNAL uses fast-path.
    Mirrors generate_and_evaluate pattern from content_tools.py.
    """
    from services.prompt_service import PromptService

    signals_summary = _format_signals_summary(signals)
    journey_summary = _format_journey_summary(journey)

    prompt = PromptService.get("generate_and_evaluate_attribution").format(
        order_id=order.get("order_id", "unknown"),
        order_value=order.get("order_value", 0),
        order_date=order.get("order_date", "unknown"),
        customer_email=order.get("customer_email", "unknown"),
        products=order.get("products_purchased", "N/A"),
        signal_count=len(signals),
        signals_summary=signals_summary,
        total_touchpoints=journey.get("total_touchpoints", 0),
        days_to_purchase=journey.get("days_to_purchase", 0),
        journey_summary=journey_summary,
        last_touch_score=model_scores.get("last_touch", 0),
        first_touch_score=model_scores.get("first_touch", 0),
        linear_score=model_scores.get("linear", 0),
        time_decay_score=model_scores.get("time_decay", 0),
        final_weighted_score=model_scores.get("final_weighted", 0),
        attribution_method=_determine_primary_method(signals),
        attribution_score=model_scores.get("final_weighted", 0),
    )

    agent = _get_agent_service()

    try:
        result = await agent.analyze_async(prompt)
    except Exception as e:
        logger.error(f"LLM attribution evaluation failed: {e}")
        return _evaluation_fallback()

    # Validate LLM returned expected structure
    if "error" in result and "quality_score" not in result:
        logger.warning(f"LLM returned error, using fallback: {result.get('error')}")
        return _evaluation_fallback()

    return result


# ================================
# Assembly
# ================================

def build_attribution_result(
    order: dict,
    signals: list,
    journey: dict,
    model_scores: dict,
    evaluation: dict,
    run_id: str,
    business_account_id: str,
    strategy: str,
    llm_skipped: bool,
) -> dict:
    """Assemble final result dict matching sales_attributions schema.

    Includes attribution_version, strategy_used, llm_skipped fields.
    """
    attribution_score = model_scores.get("final_weighted", 0)
    primary_method = _determine_primary_method(signals)

    return {
        "order_id": order.get("order_id", ""),
        "order_number": order.get("order_number", ""),
        "order_date": order.get("order_date"),
        "order_value": order.get("order_value", 0),
        "customer_email": order.get("customer_email", ""),
        "attribution_method": primary_method,
        "attribution_score": attribution_score,
        "attribution_confidence": _score_to_confidence(attribution_score),
        "attribution_version": SALES_ATTRIBUTION_VERSION,
        "model_scores": model_scores,
        "customer_journey": journey.get("journey_summary", ""),
        "journey_timeline": journey.get("touchpoints", []),
        "total_touchpoints": journey.get("total_touchpoints", 0),
        "days_to_purchase": journey.get("days_to_purchase", 0),
        "signals_detected": [s.get("type", "") for s in signals],
        "primary_signal": signals[0] if signals else None,
        "all_signals": signals,
        "converting_post": order.get("converting_post"),
        "products_purchased": order.get("products_purchased"),
        "validation_results": {
            "quality_score": evaluation.get("quality_score", 0),
            "approved": evaluation.get("approved", False),
            "concerns": evaluation.get("concerns", []),
            "fraud_risk": evaluation.get("fraud_risk", "low"),
            "logical_consistency": evaluation.get("logical_consistency", "unknown"),
            "reasoning": evaluation.get("reasoning", ""),
        },
        "auto_approved": evaluation.get("approved", False),
        "strategy_used": strategy,
        "llm_skipped": llm_skipped,
        "run_id": run_id,
        "business_account_id": business_account_id,
    }


# ================================
# Helpers
# ================================

def _determine_primary_method(signals: list) -> str:
    """Determine the primary attribution method from detected signals.

    Priority: utm > discount_code > instagram_engagement_history >
              customer_tag > repeat_customer > behavioral
    """
    if not signals:
        return "behavioral"

    type_priority = {
        "utm": 1,
        "discount_code": 2,
        "instagram_engagement_history": 3,
        "customer_tag": 4,
        "repeat_customer": 5,
    }

    best = min(signals, key=lambda s: type_priority.get(s.get("type", ""), 99))
    return best.get("type", "behavioral")


def _score_to_confidence(score: float) -> str:
    """Map attribution score (0-100) to confidence label."""
    if score >= 80:
        return "Very High"
    elif score >= 60:
        return "High"
    elif score >= 40:
        return "Medium"
    elif score >= 20:
        return "Low"
    return "Very Low"


def _evaluation_fallback() -> dict:
    """Fallback evaluation when LLM fails — queue for manual review."""
    return {
        "quality_score": 0,
        "approved": False,
        "concerns": ["LLM evaluation failed — requires manual review"],
        "fraud_risk": "medium",
        "logical_consistency": "unknown",
        "reasoning": "LLM evaluation failed — queued for manual review",
    }


def _format_signals_summary(signals: list) -> str:
    """Format signals list into clean multi-line string for LLM prompt."""
    if not signals:
        return "  No signals detected"

    lines = []
    for s in signals:
        signal_type = s.get("type", "unknown")
        strength = s.get("strength", "unknown")
        details = {k: v for k, v in s.items() if k not in ("type", "strength")}
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        lines.append(f"  - [{signal_type}] strength={strength}, {detail_str}")

    return "\n".join(lines)


def _format_journey_summary(journey: dict) -> str:
    """Format journey dict into clean summary string for LLM prompt."""
    summary = journey.get("journey_summary", "No journey data")
    touchpoints = journey.get("touchpoints", [])

    if not touchpoints:
        return summary

    # Add top 5 touchpoints for context
    tp_lines = []
    for tp in touchpoints[:5]:
        tp_lines.append(
            f"    {tp.get('type', '?')} at {tp.get('timestamp', '?')} "
            f"(weight={tp.get('weight', 0)})"
        )

    if len(touchpoints) > 5:
        tp_lines.append(f"    ... and {len(touchpoints) - 5} more")

    return summary + "\n  Touchpoint details:\n" + "\n".join(tp_lines)
