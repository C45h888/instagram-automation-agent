"""
Weekly Attribution Learning
============================
Weekly scheduler job that analyzes attribution performance and adjusts
multi-touch model weights per business account.

Runs once a week (Monday 8am by default) via SchedulerService cron.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account:
     a. Get last week's attributions
     b. Compute performance metrics (totals, averages, method breakdown)
     c. Adjust model weights (70% new performance + 30% old weights)
     d. Normalize weights to sum=1.0
     e. Upsert to attribution_models table
     f. Log decision to audit_log
  3. Log batch summary + update Prometheus metrics

Error isolation: Each account is wrapped in try/except so a single
failure never crashes the batch.
"""

import time
import uuid as uuid_mod

from config import logger
from services.supabase_service import SupabaseService


# Default weights when no attribution_models row exists
_DEFAULT_WEIGHTS = {
    "last_touch": 0.40,
    "first_touch": 0.20,
    "linear": 0.20,
    "time_decay": 0.20,
}


# ================================
# Entry Point (called by scheduler)
# ================================
async def weekly_attribution_learning_run():
    """Top-level entry point called by APScheduler on weekly cron.

    Iterates all active business accounts, recomputes model weights,
    logs batch summary, and updates Prometheus metrics.
    """
    from routes.metrics import WEEKLY_LEARNING_RUNS

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] Weekly attribution learning cycle starting")

    stats = {"processed": 0, "updated": 0, "skipped": 0, "errors": 0}

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts — skipping learning cycle")
            WEEKLY_LEARNING_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s) for learning")

        for account in accounts:
            account_stats = _process_account_learning_safe(run_id, account)
            for key in stats:
                stats[key] += account_stats.get(key, 0)

        duration = time.time() - start
        status = "success" if stats["errors"] == 0 else "partial"

        _log_batch_summary(run_id, stats, duration)
        WEEKLY_LEARNING_RUNS.labels(status=status).inc()

        logger.info(
            f"[{run_id}] Weekly learning cycle complete "
            f"({duration:.1f}s): {stats}"
        )

    except Exception as e:
        duration = time.time() - start
        logger.error(f"[{run_id}] Weekly learning cycle failed ({duration:.1f}s): {e}")
        WEEKLY_LEARNING_RUNS.labels(status="error").inc()

        SupabaseService.log_decision(
            event_type="weekly_learning_cycle_failed",
            action="error",
            resource_type="weekly_learning",
            resource_id=run_id,
            user_id="system",
            details={"run_id": run_id, "error": str(e), "duration_seconds": round(duration, 2)},
        )


# ================================
# Per-Account Processing (Error-Isolated)
# ================================
def _process_account_learning_safe(run_id: str, account: dict) -> dict:
    """Wraps _process_account_learning in try/except. NEVER fails the batch."""
    try:
        return _process_account_learning(run_id, account)
    except Exception as e:
        account_id = account.get("id", "unknown")
        logger.error(f"[{run_id}] Learning failed for account {account_id}: {e}")
        _log_account_error(run_id, account, e)
        return {"processed": 0, "errors": 1}


def _process_account_learning(run_id: str, account: dict) -> dict:
    """Compute new model weights for a single business account.

    Steps:
      1. Fetch last week's attributions
      2. Compute performance metrics
      3. Adjust weights (70% new + 30% old)
      4. Normalize to sum=1.0
      5. Upsert weights
      6. Log decision
    """
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")

    # Step 1: Fetch last week's attributions
    attributions = SupabaseService.get_last_week_attributions(account_id)
    if not attributions:
        logger.info(f"[{run_id}] @{account_username}: no attributions last week — skipping")
        return {"processed": 1, "skipped": 1}

    # Step 2: Compute performance metrics
    metrics = _compute_performance_metrics(attributions)

    # Step 3: Get current weights
    current_weights = SupabaseService.get_attribution_model_weights(account_id)

    # Step 4: Adjust weights (70% new performance + 30% old)
    new_weights = _adjust_weights(current_weights, metrics)

    # Step 5: Build learning notes
    notes = (
        f"Week of {run_id[:8]}: {metrics['total']} attributions, "
        f"{metrics['approved_count']} approved, "
        f"avg score {metrics['avg_score']:.1f}, "
        f"methods: {metrics['method_breakdown']}"
    )

    # Step 6: Upsert
    success = SupabaseService.update_attribution_model_weights(
        business_account_id=account_id,
        weights=new_weights,
        metrics=metrics,
        notes=notes,
    )

    if success:
        SupabaseService.log_decision(
            event_type="weekly_learning_weights_updated",
            action="weights_updated",
            resource_type="attribution_models",
            resource_id=account_id,
            user_id=account_id,
            details={
                "run_id": run_id,
                "old_weights": current_weights,
                "new_weights": new_weights,
                "total_attributions": metrics["total"],
                "approved_count": metrics["approved_count"],
                "avg_score": metrics["avg_score"],
                "method_breakdown": metrics["method_breakdown"],
            },
        )
        logger.info(
            f"[{run_id}] @{account_username}: weights updated "
            f"({metrics['total']} attributions, avg={metrics['avg_score']:.1f})"
        )
        return {"processed": 1, "updated": 1}
    else:
        logger.warning(f"[{run_id}] @{account_username}: failed to update weights")
        return {"processed": 1, "errors": 1}


# ================================
# Performance Computation
# ================================
def _compute_performance_metrics(attributions: list) -> dict:
    """Compute aggregate performance metrics from a week of attributions.

    Returns dict with:
      - total, approved_count, avg_score
      - method_breakdown: {method: count}
      - model_averages: {model_name: avg_score} for each multi-touch model
    """
    total = len(attributions)
    approved_count = sum(1 for a in attributions if a.get("auto_approved"))
    scores = [a.get("attribution_score", 0) or 0 for a in attributions]
    avg_score = sum(scores) / total if total else 0

    # Method breakdown
    method_breakdown = {}
    for a in attributions:
        method = a.get("attribution_method", "unknown")
        method_breakdown[method] = method_breakdown.get(method, 0) + 1

    # Per-model average scores (from model_scores JSONB)
    model_totals = {"last_touch": 0, "first_touch": 0, "linear": 0, "time_decay": 0}
    model_counts = {"last_touch": 0, "first_touch": 0, "linear": 0, "time_decay": 0}

    for a in attributions:
        model_scores = a.get("model_scores") or {}
        for model in model_totals:
            val = model_scores.get(model)
            if val is not None:
                model_totals[model] += float(val)
                model_counts[model] += 1

    model_averages = {}
    for model in model_totals:
        count = model_counts[model]
        model_averages[model] = model_totals[model] / count if count > 0 else 0

    return {
        "total": total,
        "approved_count": approved_count,
        "avg_score": avg_score,
        "method_breakdown": method_breakdown,
        "model_averages": model_averages,
    }


# ================================
# Weight Adjustment
# ================================
def _adjust_weights(current_weights: dict, metrics: dict) -> dict:
    """Adjust model weights based on performance.

    Strategy: 70% new performance proportional + 30% old weights.
    Normalized to sum=1.0 after blending.
    """
    model_averages = metrics.get("model_averages", {})

    # If no model data, keep current weights
    total_avg = sum(model_averages.values())
    if total_avg <= 0:
        return current_weights

    # New weights proportional to model average performance
    new_proportional = {}
    for model in _DEFAULT_WEIGHTS:
        new_proportional[model] = model_averages.get(model, 0) / total_avg

    # Blend: 70% new + 30% old
    blended = {}
    for model in _DEFAULT_WEIGHTS:
        old_val = current_weights.get(model, _DEFAULT_WEIGHTS[model])
        new_val = new_proportional.get(model, _DEFAULT_WEIGHTS[model])
        blended[model] = (0.7 * new_val) + (0.3 * old_val)

    # Normalize to sum=1.0
    total = sum(blended.values())
    if total > 0:
        blended = {k: round(v / total, 4) for k, v in blended.items()}

    return blended


# ================================
# Helpers
# ================================
def _log_account_error(run_id: str, account: dict, error: Exception):
    """Log a learning error for a single account."""
    SupabaseService.log_decision(
        event_type="weekly_learning_account_error",
        action="error",
        resource_type="weekly_learning",
        resource_id=run_id,
        user_id=account.get("id", ""),
        details={
            "run_id": run_id,
            "account_username": account.get("username", ""),
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def _log_batch_summary(run_id: str, stats: dict, duration: float):
    """Log cycle completion with aggregate stats to audit_log."""
    SupabaseService.log_decision(
        event_type="weekly_learning_cycle_complete",
        action="batch_processed",
        resource_type="weekly_learning",
        resource_id=run_id,
        user_id="system",
        details={
            "run_id": run_id,
            "duration_seconds": round(duration, 2),
            **stats,
        },
    )
