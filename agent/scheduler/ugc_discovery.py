"""
UGC Discovery
==============
Scheduled batch pipeline that discovers user-generated content via
backend-proxied Instagram API calls, scores quality, deduplicates,
and stores results in Supabase.

Replaces the N8N UGC-collection.json workflow entirely.

Flow per cycle:
  1. Fetch all active business accounts
  2. For each account (parallel, semaphore-limited):
     a. Fetch monitored hashtags from Supabase
     b. For each hashtag: fetch recent media via backend proxy
     c. Fetch tagged posts via backend proxy
     d. Merge both streams, deduplicate via Redis + DB
     e. Score each post (pure Python, 0-95)
     f. Route by tier:
        - high (>=70): store in ugc_discovered, create ugc_permission, optionally send DM
        - moderate (41-69): store in ugc_discovered for manual review
        - low (<=40): discard
     g. Log decisions to audit_log
  3. Log batch summary + update Prometheus metrics

Error isolation: Each account is wrapped in try/except so a single
failure never crashes the batch.
"""

import asyncio
import time
import uuid as uuid_mod
from datetime import datetime, timezone

from config import (
    logger,
    UGC_COLLECTION_MAX_CONCURRENT_ACCOUNTS,
    UGC_COLLECTION_MAX_POSTS_PER_HASHTAG,
    UGC_COLLECTION_MAX_TAGGED_POSTS,
    UGC_COLLECTION_AUTO_SEND_DM,
    UGC_COLLECTION_AUTO_REPOST,
)
from services.supabase_service import SupabaseService
from scheduler.ugc_dedup_service import UgcDedupService
from tools.ugc_tools import (
    score_ugc_quality,
    fetch_hashtag_media,
    fetch_tagged_media,
    compose_dm_message,
    send_permission_dm,
)


# ================================
# Entry Point (called by scheduler)
# ================================
async def ugc_discovery_run():
    """Top-level entry point called by APScheduler every N hours."""
    # Lazy import to avoid circular dependency at module load time
    from routes.metrics import (
        UGC_COLLECTION_RUNS,
        UGC_COLLECTION_ITEMS,
        UGC_COLLECTION_DURATION,
    )

    run_id = str(uuid_mod.uuid4())
    start = time.time()
    logger.info(f"[{run_id}] UGC discovery cycle starting")

    stats = {
        "discovered": 0,
        "high_quality": 0,
        "moderate": 0,
        "discarded": 0,
        "duplicates_skipped": 0,
        "dms_queued": 0,
        "dms_sent": 0,
        "errors": 0,
    }

    try:
        accounts = SupabaseService.get_active_business_accounts()
        if not accounts:
            logger.info(f"[{run_id}] No active business accounts found — skipping cycle")
            UGC_COLLECTION_RUNS.labels(status="no_accounts").inc()
            return

        logger.info(f"[{run_id}] Found {len(accounts)} active account(s)")

        semaphore = asyncio.Semaphore(UGC_COLLECTION_MAX_CONCURRENT_ACCOUNTS)

        tasks = [
            _process_account_safe(run_id, account, semaphore)
            for account in accounts
        ]
        results = await asyncio.gather(*tasks)

        # Aggregate stats across all accounts
        for account_stats in results:
            for key in stats:
                stats[key] += account_stats.get(key, 0)

        duration = time.time() - start
        status = "success" if stats["errors"] == 0 else "partial"

        _log_batch_summary(run_id, stats, duration)
        UGC_COLLECTION_RUNS.labels(status=status).inc()
        UGC_COLLECTION_DURATION.observe(duration)

        for action in ("high_quality", "moderate", "discarded", "duplicates_skipped", "dms_sent", "errors"):
            count = stats.get(action, 0)
            if count > 0:
                UGC_COLLECTION_ITEMS.labels(action=action).inc(count)

        logger.info(
            f"[{run_id}] UGC discovery cycle complete "
            f"({duration:.1f}s): {stats}"
        )

    except Exception as e:
        duration = time.time() - start
        logger.error(f"[{run_id}] UGC discovery cycle failed ({duration:.1f}s): {e}")
        UGC_COLLECTION_RUNS.labels(status="error").inc()
        UGC_COLLECTION_DURATION.observe(duration)

        SupabaseService.log_decision(
            event_type="ugc_discovery_cycle_failed",
            action="error",
            resource_type="ugc_discovery",
            resource_id=run_id,
            user_id="system",
            details={
                "run_id": run_id,
                "error": str(e),
                "duration_seconds": round(duration, 2),
            },
        )


# ================================
# Per-Account Processing (Error-Isolated)
# ================================
async def _process_account_safe(
    run_id: str, account: dict, semaphore: asyncio.Semaphore
) -> dict:
    """Wraps _process_account in try/except. NEVER fails the batch."""
    async with semaphore:
        try:
            return await _process_account(run_id, account)
        except Exception as e:
            account_id = account.get("id", "unknown")
            logger.error(f"[{run_id}] Account {account_id} UGC discovery failed: {e}")
            _log_account_error(run_id, account, e)
            return {"errors": 1}


async def _process_account(run_id: str, account: dict) -> dict:
    """Full UGC discovery pipeline for a single business account."""
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    stats = {
        "discovered": 0,
        "high_quality": 0,
        "moderate": 0,
        "discarded": 0,
        "duplicates_skipped": 0,
        "dms_queued": 0,
        "dms_sent": 0,
        "errors": 0,
    }

    # Step 1: Fetch monitored hashtags
    hashtags = SupabaseService.get_monitored_hashtags(account_id)
    logger.info(f"[{run_id}] @{account_username}: {len(hashtags)} monitored hashtag(s)")

    # Step 2: Fetch media from all sources
    all_media = []

    # 2a: Hashtag media (sequential per hashtag to respect API rate limits)
    for ht in hashtags:
        hashtag_text = ht.get("hashtag", "")
        if not hashtag_text:
            continue
        media = await asyncio.to_thread(
            fetch_hashtag_media,
            business_account_id=account_id,
            hashtag=hashtag_text,
            limit=UGC_COLLECTION_MAX_POSTS_PER_HASHTAG,
        )
        for m in media:
            m["_source"] = "hashtag"
            m["_source_hashtag"] = hashtag_text
        all_media.extend(media)

    # 2b: Tagged posts
    tagged = await asyncio.to_thread(
        fetch_tagged_media,
        business_account_id=account_id,
        limit=UGC_COLLECTION_MAX_TAGGED_POSTS,
    )
    for m in tagged:
        m["_source"] = "tagged"
        m["_source_hashtag"] = None
    all_media.extend(tagged)

    logger.info(f"[{run_id}] @{account_username}: {len(all_media)} total media fetched")

    if not all_media:
        return stats

    # Step 3: Intra-batch dedup (by instagram media id)
    seen_ids = set()
    unique_media = []
    for post in all_media:
        media_id = post.get("id", "")
        if not media_id or media_id in seen_ids:
            continue
        seen_ids.add(media_id)
        unique_media.append(post)

    logger.info(f"[{run_id}] @{account_username}: {len(unique_media)} unique after intra-batch dedup")

    # Step 4: Cross-cycle dedup (Redis fast-path + DB fallback)
    existing_db_ids = SupabaseService.get_existing_ugc_ids(account_id)
    unprocessed = []
    for post in unique_media:
        media_id = post.get("id", "")
        if UgcDedupService.is_processed(media_id):
            stats["duplicates_skipped"] += 1
            continue
        if media_id in existing_db_ids:
            stats["duplicates_skipped"] += 1
            UgcDedupService.mark_processed(media_id)  # backfill Redis
            continue
        unprocessed.append(post)

    logger.info(
        f"[{run_id}] @{account_username}: {len(unprocessed)} new posts "
        f"({stats['duplicates_skipped']} duplicates skipped)"
    )

    # Step 5: Score and route each post
    for post in unprocessed:
        result = _process_post_safe(run_id, post, account)
        action = result.get("action", "error")
        if action == "high":
            stats["high_quality"] += 1
            stats["discovered"] += 1
            if result.get("dm_sent"):
                stats["dms_sent"] += 1
            elif result.get("dm_queued"):
                stats["dms_queued"] += 1
        elif action == "moderate":
            stats["moderate"] += 1
            stats["discovered"] += 1
        elif action == "discarded":
            stats["discarded"] += 1
        else:
            stats["errors"] += 1

    logger.info(f"[{run_id}] @{account_username}: {stats}")

    # End-of-run: sync tagged posts from Graph API into ugc_discovered via backend
    from tools.live_fetch_tools import trigger_sync_ugc
    sync_result = await trigger_sync_ugc(account_id)
    logger.info(
        f"[{run_id}] @{account_username}: UGC sync complete "
        f"({sync_result.get('synced_count', 0)} records synced)"
    )

    # Auto-repost: check for newly-granted permissions and publish (if enabled)
    if UGC_COLLECTION_AUTO_REPOST:
        from tools.live_fetch_tools import trigger_repost_ugc
        granted_permissions = SupabaseService.get_granted_ugc_permissions(account_id)
        for perm in granted_permissions:
            repost_result = await trigger_repost_ugc(account_id, perm["id"])
            if repost_result.get("success"):
                stats["reposted"] = stats.get("reposted", 0) + 1
                logger.info(
                    f"[{run_id}] @{account_username}: reposted UGC "
                    f"(permission_id={perm['id']}, media_id={repost_result.get('id')})"
                )
            else:
                logger.warning(
                    f"[{run_id}] @{account_username}: repost failed "
                    f"(permission_id={perm['id']}): {repost_result.get('error')}"
                )

    return stats


# ================================
# Per-Post Processing (Error-Isolated)
# ================================
def _process_post_safe(run_id: str, post: dict, account: dict) -> dict:
    """Wraps _process_post in try/except. NEVER fails the batch."""
    try:
        return _process_post(run_id, post, account)
    except Exception as e:
        media_id = post.get("id", "unknown")
        logger.error(f"[{run_id}] Post {media_id} processing failed: {e}")
        # Mark processed to prevent infinite retry loops
        UgcDedupService.mark_processed(post.get("id", ""))
        SupabaseService.log_decision(
            event_type="ugc_discovery_post_error",
            action="error",
            resource_type="ugc_content",
            resource_id=run_id,
            user_id=account.get("id", ""),
            details={
                "run_id": run_id,
                "instagram_media_id": media_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        return {"action": "error", "media_id": media_id}


def _process_post(run_id: str, post: dict, account: dict) -> dict:
    """Single post pipeline: score -> route -> store -> dedup mark -> audit log."""
    account_id = account.get("id", "unknown")
    account_username = account.get("username", "unknown")
    media_id = post.get("id", "")

    # Score
    scoring = score_ugc_quality(post, account_username)
    score = scoring["score"]
    tier = scoring["tier"]
    factors = scoring["factors"]

    # Route: low tier — discard
    if tier == "low":
        UgcDedupService.mark_processed(media_id)
        return {"action": "discarded", "media_id": media_id, "score": score}

    # Single write to ugc_content (both high and moderate tiers)
    ugc_row = {
        "business_account_id": account_id,
        "visitor_post_id":     media_id,
        "author_id":           post.get("owner_id", "") or "",
        "author_username":     post.get("username", ""),
        "message":             (post.get("caption") or "")[:2000],
        "media_type":          post.get("media_type", "IMAGE"),
        "media_url":           post.get("media_url", ""),
        "permalink_url":       post.get("permalink", ""),
        "like_count":          post.get("like_count", 0) or 0,
        "comment_count":       post.get("comments_count", 0) or 0,
        "created_time":        post.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "source":              post.get("_source", "unknown"),
        "quality_score":       score,
        "quality_tier":        tier,
        "run_id":              run_id,
    }
    ugc_record = SupabaseService.create_or_update_ugc(ugc_row)
    ugc_content_id = ugc_record.get("id", "")

    UgcDedupService.mark_processed(media_id)

    result = {"action": tier, "media_id": media_id, "score": score}

    # High quality: create permission request + optionally send DM
    if tier == "high" and ugc_content_id:
        dm_text = compose_dm_message(
            username=post.get("username", ""),
            brand_username=account_username,
            post_permalink=post.get("permalink", ""),
        )

        permission_row = {
            "ugc_content_id":    ugc_content_id,
            "business_account_id": account_id,
            "request_message":   dm_text,
            "status":            "pending",
            "run_id":            run_id,
        }

        if UGC_COLLECTION_AUTO_SEND_DM:
            recipient_id = post.get("owner_id", "") or ""
            if not recipient_id:
                logger.info(
                    f"DM skipped for @{post.get('username')} — "
                    "no numeric owner_id in post data (backend search-hashtag must include owner{id})"
                )
                permission_row["status"] = "expired"   # send impossible — closest valid status
                result["dm_sent"] = False
                SupabaseService.create_ugc_permission(permission_row)
            else:
                # Create permission row first to get the ID for idempotency key
                permission_row["status"] = "pending"  # DM queued, worker will send
                created = SupabaseService.create_ugc_permission(permission_row)
                permission_id = created.get("id", "") if created else ""
                if permission_id:
                    dm_result = send_permission_dm(
                        business_account_id=account_id,
                        recipient_id=recipient_id,
                        recipient_username=post.get("username", ""),
                        message_text=dm_text,
                        permission_id=permission_id,
                    )
                    result["dm_sent"] = dm_result.get("success", False)
                else:
                    logger.warning(f"Skipping DM enqueue — permission row creation failed for @{post.get('username')}")
                    result["dm_sent"] = False
        else:
            result["dm_queued"] = True
            SupabaseService.create_ugc_permission(permission_row)

    # Audit log
    SupabaseService.log_decision(
        event_type="ugc_discovery_post_processed",
        action=tier,
        resource_type="ugc_content",
        resource_id=ugc_content_id or run_id,
        user_id=account_id,
        details={
            "run_id": run_id,
            "instagram_media_id": media_id,
            "username": post.get("username", ""),
            "source": post.get("_source", "unknown"),
            "quality_score": score,
            "quality_tier": tier,
            "quality_factors": factors,
        },
    )

    return result


# ================================
# Helpers
# ================================
def _log_account_error(run_id: str, account: dict, error: Exception):
    """Log a processing error for a single account."""
    SupabaseService.log_decision(
        event_type="ugc_discovery_account_error",
        action="error",
        resource_type="ugc_discovery",
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
        event_type="ugc_discovery_cycle_complete",
        action="batch_processed",
        resource_type="ugc_discovery",
        resource_id=run_id,
        user_id="system",
        details={
            "run_id": run_id,
            "duration_seconds": round(duration, 2),
            **stats,
        },
    )
