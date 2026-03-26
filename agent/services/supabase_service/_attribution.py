"""
Attribution Service
====================
Sales attribution, customer enrichment, and model weights.
Used by: order webhook, weekly learning scheduler.

All methods: @staticmethod
"""

from datetime import datetime, timezone, timedelta
from pybreaker import CircuitBreakerError

from ._infra import (
    execute,
    cache_get,
    cache_set,
    attribution_model_cache,
    db_breaker,
    supabase,
    logger,
)


class AttributionService:
    """Sales attribution, customer enrichment, and attribution model weights."""

    # ─────────────────────────────────────────
    # READ: Order Attribution (dedup check)
    # ─────────────────────────────────────────
    @staticmethod
    def get_order_attribution(order_id: str) -> dict:
        """Check if an order has already been attributed (dedup).

        Returns the existing attribution row or empty dict.
        """
        if not supabase or not order_id:
            return {}

        try:
            result = execute(
                supabase.table("sales_attributions")
                .select("id, order_id")
                .eq("order_id", order_id)
                .limit(1),
                table="sales_attributions",
                operation="select",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping order attribution check")
            return {}
        except Exception as e:
            logger.warning(f"Failed to check order attribution for {order_id}: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Customer Enrichment (3 sub-queries)
    # ─────────────────────────────────────────
    @staticmethod
    def get_customer_enrichment(
        email: str,
        business_account_id: str,
        history_days: int = 90,
        engagement_days: int = 30,
    ) -> dict:
        """Fetch customer history + recent engagements in one call.

        Combines three queries internally:
          1. Customer Instagram history (customer_instagram_history)
          2. Comment engagements (instagram_comments)
          3. DM conversation engagements (instagram_dm_conversations)

        Single outer try/except — CircuitBreakerError fails the whole method (fail fast
        on sustained outage), other exceptions log and return partial data gracefully.
        """
        if not supabase or not email:
            return {"history": {}, "engagements": []}

        history_cutoff = (datetime.now(timezone.utc) - timedelta(days=history_days)).isoformat()
        eng_cutoff = (datetime.now(timezone.utc) - timedelta(days=engagement_days)).isoformat()

        history: dict = {}
        comment_engagements: list = []
        dm_engagements: list = []

        try:
            # Query 1: Customer Instagram history
            result = execute(
                supabase.table("customer_instagram_history")
                .select(
                    "purchase_count, total_spend, first_purchase, last_purchase, "
                    "customer_tags, instagram_interactions, average_order_value"
                )
                .eq("email", email)
                .gte("last_purchase", history_cutoff)
                .limit(1),
                table="customer_instagram_history",
                operation="select",
            )
            history = result.data[0] if result.data else {}

            # Query 2: Comment engagements
            result_comments = execute(
                supabase.table("instagram_comments")
                .select("instagram_comment_id, media_id, published_at, sentiment, category, text")
                .eq("business_account_id", business_account_id)
                .not_.is_("published_at", "null")
                .gte("published_at", eng_cutoff)
                .is_("parent_comment_id", "null")
                .order("published_at", desc=False)
                .limit(75),
                table="instagram_comments",
                operation="select",
            )
            comment_engagements = [
                {
                    "engagement_type": "comment",
                    "content_id": r.get("instagram_comment_id", ""),
                    "post_id": r.get("media_id", ""),
                    "timestamp": r.get("published_at", ""),
                    "metadata": {
                        "sentiment": r.get("sentiment"),
                        "category": r.get("category"),
                        "text_preview": (r.get("text") or "")[:100],
                    },
                }
                for r in (result_comments.data or [])
            ]

            # Query 3: DM conversation engagements
            result_convs = execute(
                supabase.table("instagram_dm_conversations")
                .select(
                    "customer_instagram_id, customer_username, first_message_at, "
                    "last_message_at, message_count, last_message_preview"
                )
                .eq("business_account_id", business_account_id)
                .not_.is_("last_message_at", "null")
                .gte("last_message_at", eng_cutoff)
                .order("first_message_at", desc=False)
                .limit(25),
                table="instagram_dm_conversations",
                operation="select",
            )
            dm_engagements = [
                {
                    "engagement_type": "dm",
                    "content_id": r.get("customer_instagram_id", ""),
                    "post_id": "",
                    "timestamp": r.get("first_message_at") or r.get("last_message_at", ""),
                    "metadata": {
                        "message_count": r.get("message_count", 0),
                        "last_preview": (r.get("last_message_preview") or "")[:100],
                        "customer_username": r.get("customer_username"),
                    },
                }
                for r in (result_convs.data or [])
            ]

        except CircuitBreakerError:
            # Fail fast on sustained outage — don't return partial data
            logger.error("Circuit breaker OPEN — customer enrichment failed entirely")
            return {"history": {}, "engagements": []}
        except Exception as e:
            # Partial failure: log what failed, return whatever we collected
            logger.warning(f"Customer enrichment partial failure for {email}: {e}")
            # Continue with whatever was collected above

        # Merge both sources, sorted by timestamp ascending (journey chronology)
        engagements = sorted(
            comment_engagements + dm_engagements,
            key=lambda e: e.get("timestamp", ""),
        )[:100]

        return {"history": history, "engagements": engagements}

    # ─────────────────────────────────────────
    # WRITE: Save Attribution
    # ─────────────────────────────────────────
    @staticmethod
    def save_attribution(data: dict) -> dict:
        """Insert a completed attribution result into sales_attributions."""
        if not supabase:
            return {}

        try:
            result = execute(
                supabase.table("sales_attributions").insert(data),
                table="sales_attributions",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save attribution")
            return {}
        except Exception as e:
            logger.error(f"Failed to save attribution: {e}")
            return {}

    # ─────────────────────────────────────────
    # WRITE: Queue for Review
    # ─────────────────────────────────────────
    @staticmethod
    def queue_for_review(data: dict) -> dict:
        """Insert an attribution that needs manual review.

        Coerces fraud_risk to boolean defensively (DB column is boolean, not text).
        """
        if not supabase:
            return {}

        if "fraud_risk" in data and not isinstance(data["fraud_risk"], bool):
            data = {**data, "fraud_risk": data["fraud_risk"] not in ("low", "none", False, None, "")}

        try:
            result = execute(
                supabase.table("attribution_review_queue").insert(data),
                table="attribution_review_queue",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to queue for review")
            return {}
        except Exception as e:
            logger.error(f"Failed to queue for review: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Attribution Model Weights (L1 + L2 cached)
    # ─────────────────────────────────────────
    @staticmethod
    def get_attribution_model_weights(business_account_id: str) -> dict:
        """Fetch current attribution model weights.

        Caching: L1 in-memory (5 min TTL) → L2 Redis (5 min TTL) → Supabase
        Returns hardcoded defaults if not found.
        """
        default_weights = {
            "last_touch": 0.40,
            "first_touch": 0.20,
            "linear": 0.20,
            "time_decay": 0.20,
        }
        if not supabase or not business_account_id:
            return default_weights

        cache_key = f"attr_model:{business_account_id}"

        if cache_key in attribution_model_cache:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="attribution_model_l1").inc()
            return attribution_model_cache[cache_key]

        cached = cache_get(cache_key)
        if cached:
            from metrics import CACHE_HITS
            CACHE_HITS.labels(key_type="attribution_model_l2").inc()
            attribution_model_cache[cache_key] = cached
            return cached

        from metrics import CACHE_MISSES
        CACHE_MISSES.labels(key_type="attribution_model").inc()

        try:
            result = execute(
                supabase.table("attribution_models")
                .select("weights")
                .eq("business_account_id", business_account_id)
                .limit(1),
                table="attribution_models",
                operation="select",
            )

            if result.data:
                weights = result.data[0].get("weights", default_weights)
                attribution_model_cache[cache_key] = weights
                cache_set(cache_key, weights, ttl=300)
                return weights

            return default_weights

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — using default attribution weights")
            return default_weights
        except Exception as e:
            logger.warning(f"Failed to fetch model weights: {e}")
            return default_weights

    # ─────────────────────────────────────────
    # WRITE: Update Attribution Model Weights
    # ─────────────────────────────────────────
    @staticmethod
    def update_attribution_model_weights(
        business_account_id: str,
        weights: dict,
        metrics: dict,
        notes: str = "",
    ) -> bool:
        """Upsert attribution model weights for a business account.

        Invalidates L1 cache after write. NOTE: L2 Redis cache is NOT
        invalidated here — stale data may persist for up to 5 minutes.
        """
        if not supabase or not business_account_id:
            return False

        from services.validation import AttributionModelWeightsModel

        try:
            AttributionModelWeightsModel(**weights)
        except Exception as e:
            logger.warning(f"Invalid attribution model weights, writing anyway: {e}")

        row = {
            "business_account_id": business_account_id,
            "weights": weights,
            "performance_metrics": metrics,
            "learning_notes": notes,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            execute(
                supabase.table("attribution_models")
                .upsert(row, on_conflict="business_account_id"),
                table="attribution_models",
                operation="upsert",
            )

            # Invalidate L1 cache
            cache_key = f"attr_model:{business_account_id}"
            if cache_key in attribution_model_cache:
                del attribution_model_cache[cache_key]
            # Also update L2 so other processes/threads see fresh weights immediately
            cache_set(cache_key, weights, ttl=300)

            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to update model weights")
            return False
        except Exception as e:
            logger.error(f"Failed to update model weights: {e}")
            return False

    # ─────────────────────────────────────────
    # READ: Last Week Attributions (Weekly Learning)
    # ─────────────────────────────────────────
    @staticmethod
    def get_last_week_attributions(business_account_id: str = None) -> list:
        """Fetch last 7 days of attributions for weekly learning."""
        if not supabase:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        try:
            query = (
                supabase.table("sales_attributions")
                .select(
                    "order_id, order_value, attribution_method, attribution_score, "
                    "model_scores, auto_approved, validation_results, "
                    "business_account_id, processed_at"
                )
                .gte("processed_at", cutoff)
            )
            if business_account_id:
                query = query.eq("business_account_id", business_account_id)

            result = execute(query, table="sales_attributions", operation="select")
            return result.data or []

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping last week attributions fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch last week attributions: {e}")
            return []
