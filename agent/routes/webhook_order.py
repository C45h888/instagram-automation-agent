"""
Order Created Webhook
======================
Standalone webhook for processing new orders through sales attribution.

Not using WebhookConfig because:
  - No "reply" to execute (save/queue instead)
  - Different analysis function (attribution, not message analysis)
  - Different domain (e-commerce orders, not Instagram messages)

Flow mirrors webhook_base.py manually:
  1. HMAC verify
  2. Parse order payload
  3. Hard rules (missing email, zero value, duplicate)
  4. Enrich (customer history + engagements via single call)
  5. Detect signals (pure Python)
  6. Strategy classify (high → skip LLM, medium/low → LLM)
  7. Build journey (pure Python)
  8. Get model weights (L1+L2 cached)
  9. Calculate multi-touch models (pure Python)
  10. Evaluate (fast-path or LLM)
  11. Apply hard rules
  12. Save or queue
  13. Log decision + metrics
  14. Return response

Endpoint:
  POST /webhook/order-created
"""

import hashlib
import hmac
import time
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from config import (
    logger,
    ORDER_WEBHOOK_SECRET,
    SALES_ATTRIBUTION_ENABLED,
    SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD,
    SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD,
    SALES_ATTRIBUTION_LOOKBACK_DAYS,
    SALES_ATTRIBUTION_HISTORY_DAYS,
)
from services.supabase_service import SupabaseService
from tools.attribution_tools import (
    detect_all_signals,
    classify_signal_strategy,
    build_fast_path_evaluation,
    build_customer_journey,
    calculate_multi_touch_models,
    evaluate_attribution,
    apply_hard_rules,
    build_attribution_result,
)

webhook_order_router = APIRouter(tags=["webhooks"])


# ================================
# HMAC Verification
# ================================

def _verify_order_signature(request: Request, body: bytes) -> bool:
    """Verify webhook signature using ORDER_WEBHOOK_SECRET.

    Mirrors verify_instagram_signature from webhook_base.py.
    Falls through in dev mode if secret not configured.
    """
    if not ORDER_WEBHOOK_SECRET:
        logger.warning("ORDER_WEBHOOK_SECRET not set — skipping signature verification (dev mode)")
        return True

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or invalid webhook signature header")
        return False

    expected = signature_header[7:]
    computed = hmac.new(
        ORDER_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected)


# ================================
# Parse & Validate
# ================================

def _parse_order_payload(raw: dict) -> dict:
    """Parse and normalize order webhook payload."""
    return {
        "order_id": raw.get("order_id", ""),
        "order_number": raw.get("order_number", ""),
        "order_date": raw.get("order_date", datetime.now(timezone.utc).isoformat()),
        "order_value": float(raw.get("order_value", 0) or 0),
        "customer_email": (raw.get("customer_email") or "").strip().lower(),
        "customer_tags": raw.get("customer_tags") or [],
        "discount_code": raw.get("discount_code", ""),
        "utm_source": raw.get("utm_source", ""),
        "utm_medium": raw.get("utm_medium", ""),
        "utm_campaign": raw.get("utm_campaign", ""),
        "utm_content": raw.get("utm_content", ""),
        "products_purchased": raw.get("products_purchased") or [],
        "business_account_id": raw.get("business_account_id", ""),
        "converting_post": raw.get("converting_post"),
    }


def _check_hard_rules(order: dict) -> dict | None:
    """Pre-flight validation. Returns error dict if triggered, None otherwise."""
    if not order.get("customer_email"):
        return {"error": "missing_email", "message": "Order has no customer email — cannot attribute"}

    if order.get("order_value", 0) <= 0:
        return {"error": "zero_value", "message": "Order value is zero or negative"}

    if not order.get("order_id"):
        return {"error": "missing_order_id", "message": "Order has no ID"}

    if not order.get("business_account_id"):
        return {"error": "missing_business_account", "message": "No business_account_id provided"}

    # Duplicate check
    existing = SupabaseService.get_order_attribution(order["order_id"])
    if existing:
        return {"error": "duplicate_order", "message": f"Order {order['order_id']} already attributed"}

    return None


# ================================
# Webhook Endpoint
# ================================

@webhook_order_router.post("/webhook/order-created")
async def process_order_webhook(request: Request):
    """Process incoming order webhook for sales attribution.

    Full pipeline: verify → parse → validate → enrich →
    detect → strategy → journey → model → evaluate → save → log
    """
    from routes.metrics import (
        ATTRIBUTION_RUNS,
        ATTRIBUTION_RESULTS,
        ATTRIBUTION_SCORES,
        ATTRIBUTION_DURATION,
        ATTRIBUTION_TOUCHPOINTS,
    )

    pipeline_start = time.time()
    run_id = str(uuid_mod.uuid4())
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info(f"[{request_id}] Starting order attribution pipeline [{run_id}]")

    ATTRIBUTION_RUNS.labels(status="started").inc()

    # Check if feature is enabled
    if not SALES_ATTRIBUTION_ENABLED:
        return JSONResponse(
            status_code=503,
            content={"error": "disabled", "message": "Sales attribution is disabled"},
        )

    # Step 1: Verify signature
    body = await request.body()
    if not _verify_order_signature(request, body):
        logger.warning(f"[{request_id}] Invalid order webhook signature")
        ATTRIBUTION_RUNS.labels(status="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Step 2: Parse payload
    try:
        raw_payload = await request.json()
        order = _parse_order_payload(raw_payload)
    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse order payload: {e}")
        ATTRIBUTION_RUNS.labels(status="parse_error").inc()
        return JSONResponse(
            status_code=400,
            content={"error": "parse_error", "message": str(e), "request_id": request_id},
        )

    order_id = order.get("order_id", "unknown")
    business_account_id = order.get("business_account_id", "")

    # Step 3: Hard rules
    hard_rule = _check_hard_rules(order)
    if hard_rule:
        logger.info(f"[{request_id}] Hard rule triggered: {hard_rule['error']}")
        ATTRIBUTION_RUNS.labels(status="hard_rule").inc()
        SupabaseService.log_decision(
            event_type="sales_attribution_hard_rule",
            action=hard_rule["error"],
            resource_type="order",
            resource_id=order_id,
            user_id=business_account_id,
            details={"run_id": run_id, **hard_rule},
            ip_address=request.client.host if request.client else "unknown",
        )
        hard_rule["request_id"] = request_id
        return JSONResponse(status_code=400, content=hard_rule)

    try:
        # Step 4: Enrich with customer data (single combined call)
        enrichment = SupabaseService.get_customer_enrichment(
            order["customer_email"],
            business_account_id,
            history_days=SALES_ATTRIBUTION_HISTORY_DAYS,
            engagement_days=SALES_ATTRIBUTION_LOOKBACK_DAYS,
        )
        customer_history = enrichment.get("history", {})
        engagements = enrichment.get("engagements", [])

        # Step 5: Detect signals (pure Python)
        signals = detect_all_signals(order, customer_history)
        logger.info(f"[{run_id}] Detected {len(signals)} signal(s) for order {order_id}")

        # Step 6: Classify strategy (determines if LLM needed)
        strategy = classify_signal_strategy(signals)
        llm_skipped = strategy == "high_signal"

        # Step 7: Build customer journey (pure Python)
        order_date_str = order.get("order_date", "")
        if isinstance(order_date_str, str) and order_date_str:
            try:
                order_date = datetime.fromisoformat(order_date_str.replace("Z", "+00:00"))
            except ValueError:
                order_date = datetime.now(timezone.utc)
        else:
            order_date = datetime.now(timezone.utc)

        journey = build_customer_journey(engagements, order_date)

        # Step 8: Get model weights from DB (L1+L2 cached)
        weights = SupabaseService.get_attribution_model_weights(business_account_id)

        # Step 9: Calculate multi-touch models (pure Python)
        model_scores = calculate_multi_touch_models(
            signals, journey.get("touchpoints", []), weights
        )

        # Step 10: Evaluate — fast-path or LLM
        if llm_skipped:
            evaluation = build_fast_path_evaluation(signals, model_scores.get("final_weighted", 0))
            logger.info(f"[{run_id}] Fast-path: skipping LLM for HIGH_SIGNAL order {order_id}")
        else:
            evaluation = await evaluate_attribution(order, signals, journey, model_scores)

        # Step 11: Apply hard rules on top of evaluation
        evaluation = apply_hard_rules(
            evaluation,
            model_scores.get("final_weighted", 0),
            SALES_ATTRIBUTION_AUTO_APPROVE_THRESHOLD,
            SALES_ATTRIBUTION_FRAUD_SCORE_THRESHOLD,
        )

        # Step 12: Build final result and save/queue
        result = build_attribution_result(
            order, signals, journey, model_scores, evaluation,
            run_id, business_account_id, strategy, llm_skipped,
        )

        is_approved = result.get("auto_approved", False)

        # Save attribution
        SupabaseService.save_attribution(result)

        # If not approved, also queue for review
        if not is_approved:
            SupabaseService.queue_for_review({
                "order_id": order_id,
                "order_value": order.get("order_value", 0),
                "customer_email": order.get("customer_email", ""),
                "attribution_score": model_scores.get("final_weighted", 0),
                "quality_score": evaluation.get("quality_score", 0),
                "concerns": evaluation.get("concerns", []),
                "fraud_risk": evaluation.get("fraud_risk", "low"),
                "full_attribution_data": result,
                "business_account_id": business_account_id,
            })

        # Step 13: Log decision
        action = "fast_path_approved" if llm_skipped and is_approved else (
            "auto_approved" if is_approved else "queued_review"
        )
        latency = int((time.time() - pipeline_start) * 1000)

        SupabaseService.log_decision(
            event_type="sales_attribution_processed",
            action=action,
            resource_type="order",
            resource_id=order_id,
            user_id=business_account_id,
            details={
                "run_id": run_id,
                "order_value": order.get("order_value", 0),
                "attribution_score": model_scores.get("final_weighted", 0),
                "attribution_method": result.get("attribution_method", ""),
                "signal_count": len(signals),
                "touchpoints": journey.get("total_touchpoints", 0),
                "quality_score": evaluation.get("quality_score", 0),
                "fraud_risk": evaluation.get("fraud_risk", "low"),
                "auto_approved": is_approved,
                "strategy_used": strategy,
                "llm_skipped": llm_skipped,
                "latency_ms": latency,
            },
            ip_address=request.client.host if request.client else "unknown",
        )

        # Step 14: Track metrics
        duration = time.time() - pipeline_start
        ATTRIBUTION_RUNS.labels(status="success").inc()
        ATTRIBUTION_RESULTS.labels(action=action).inc()
        ATTRIBUTION_SCORES.observe(model_scores.get("final_weighted", 0))
        ATTRIBUTION_DURATION.observe(duration)
        ATTRIBUTION_TOUCHPOINTS.observe(journey.get("total_touchpoints", 0))

        logger.info(
            f"[{request_id}] Order {order_id} attributed: {action} "
            f"(score={model_scores.get('final_weighted', 0):.1f}, "
            f"strategy={strategy}, latency={latency}ms)"
        )

        # Step 15: Return response
        return {
            "processed": True,
            "order_id": order_id,
            "attribution_score": model_scores.get("final_weighted", 0),
            "attribution_confidence": result.get("attribution_confidence"),
            "attribution_method": result.get("attribution_method"),
            "auto_approved": is_approved,
            "signal_count": len(signals),
            "total_touchpoints": journey.get("total_touchpoints", 0),
            "strategy_used": strategy,
            "llm_skipped": llm_skipped,
            "request_id": request_id,
            "run_id": run_id,
        }

    except Exception as e:
        duration = time.time() - pipeline_start
        logger.error(f"[{request_id}] Attribution pipeline failed for {order_id}: {e}")
        ATTRIBUTION_RUNS.labels(status="error").inc()
        ATTRIBUTION_RESULTS.labels(action="error").inc()
        ATTRIBUTION_DURATION.observe(duration)

        SupabaseService.log_decision(
            event_type="sales_attribution_error",
            action="error",
            resource_type="order",
            resource_id=order_id,
            user_id=business_account_id,
            details={
                "run_id": run_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_seconds": round(duration, 2),
            },
            ip_address=request.client.host if request.client else "unknown",
        )

        return JSONResponse(
            status_code=500,
            content={
                "processed": False,
                "error": "attribution_failed",
                "message": "Could not process order attribution",
                "request_id": request_id,
            },
        )
