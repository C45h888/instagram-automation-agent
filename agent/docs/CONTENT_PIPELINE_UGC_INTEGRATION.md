# Content Pipeline — UGC Integration: Completed

**Status:** Complete (DB migration pending application)
**Date:** 2026-03-28
**Supabase Migration Required:** `agent/supabase/migrations/002_scheduled_posts_ugc_content_id.sql`

---

## What Was Built

The content scheduler (`content_scheduler.py`) was refactored from a single monolithic LLM call into a **4-stage agentic pipeline** that mirrors the engagement scope architecture. A **parallel UGC repost track** was added on top, enabling granted UGC content to be automatically repurposed as scheduled posts.

---

## UGC Repost Path — Full Flow

```
content_scheduler_run()
  └─ _process_account(run_id, account)
       ├─ get_posts_today_count()             [daily cap check]
       │
       ├─ _process_ugc_repost(run_id, account)  ← NEW PARALLEL TRACK
       │   1. get_ugc_content_for_repost()    → granted UGC items
       │   2. _check_ugc_permission()         → verify still granted
       │   3. Build synthetic "asset" dict     → normalizes UGC into asset shape
       │   4. _generate_ugc_caption()         → tool_generate_caption.invoke()
       │   5. AgentService + evaluate_caption → Stage 3 equivalent
       │   6. create_scheduled_post(ugc_content_id=...)
       │   7. _handle_publish()               → UGC gate before enqueue
       │   8. mark_ugc_reposted()             → permission consumed
       │
       └─ _generate_post(run_id, account)     ← 4-STAGE PIPELINE
            ├─ select_asset()                 → Python weighted random
            ├─ Stage 1: AgentService + evaluate_asset
            ├─ Stage 2: tool_generate_caption.invoke()
            ├─ Stage 3: AgentService + evaluate_caption
            ├─ create_scheduled_post()
            └─ Stage 4: AgentService + publish_content
```

---

## Files Changed

| File | Changes |
|---|---|
| `agent/scheduler/content_scheduler.py` | Full rewrite — 4-stage pipeline + UGC repost path |
| `agent/tools/content_tools.py` | 4 new `@tool` functions, UGC fallback in `_fetch_asset_context()`, UGC helpers |
| `agent/services/supabase_service/_ugc.py` | 3 new methods |
| `agent/services/supabase_service/_content.py` | `get_asset_by_id()`, `create_scheduled_post()` updated for UGC |
| `agent/services/supabase_service/__init__.py` | New method exports |
| `agent/services/agent_service.py` | `CONTENT_SCOPE_TOOLS` with 8 tools |
| `agent/prompts.py` | 3 new prompts + UGC template variables |
| `agent/ugc_field_map.py` | `map_ugc_to_scheduled_post()` |
| `agent/tools/supabase_tools.py` | New tools registered |
| `agent/supabase/migrations/002_scheduled_posts_ugc_content_id.sql` | **DB migration (not yet applied)** |

---

## DB Schema Change

```sql
-- Migration: 002_scheduled_posts_ugc_content_id.sql
ALTER TABLE scheduled_posts ADD COLUMN ugc_content_id UUID REFERENCES ugc_content(id);
CREATE INDEX idx_scheduled_posts_ugc_content_id ON scheduled_posts(ugc_content_id) WHERE ugc_content_id IS NOT NULL;
```

---

## Key Design Decisions

1. **UGC is not a separate scope** — UGC repost runs as a parallel track within the content scheduler, before the regular asset path. No new agent scope needed.

2. **Python-side data fetch for UGC** — `get_ugc_content_for_repost()` is called directly by the scheduler (not exposed as a tool), keeping UGC tools out of the agent's tool set.

3. **Synthetic asset dict** — UGC content is normalized into the same dict shape as `instagram_assets` so it flows through `create_scheduled_post()` without special-casing the store logic.

4. **caption_variant drives behavior** — `"standard"` vs `"ugc_attributed"` is set at caption generation time and carries through all 4 stages. The `publish_content` tool sets `action_type="repost_ugc"` for UGC variants.

5. **Permission gate at publish** — `_check_ugc_permission()` is called twice: once after UGC selection (before caption gen) and again before enqueue (in case permission was revoked between eval and publish).

6. **`_fetch_asset_context()` UGC fallback** — If `asset_id` lookup in `instagram_assets` returns empty, the context fetcher falls back to `ugc_content` lookup, enabling the `generate_caption` tool to work for both asset types.

---

## Pending Items

| Item | Status |
|---|---|
| DB migration `002_scheduled_posts_ugc_content_id.sql` | **Must run in Supabase SQL Editor** |

## Phase 7 — Queue Worker `repost_ugc` Support — ✅ COMPLETE

### `queue_worker.py` — 5 places updated

| Method | Change |
|---|---|
| `_is_safe_to_execute()` | Added `repost_ugc` to the status-check guard (same `scheduled_posts.status == 'publishing'` check as `publish_post`) |
| `_on_success()` | Added `repost_ugc` to `if action_type in (...)` before calling settle |
| `_settle_publish_post_success()` | Added `repost_ugc` branch: after updating `scheduled_posts → published`, calls `SupabaseService.mark_ugc_reposted(ugc_content_id, business_account_id)` to consume the permission |
| `_on_failure()` (non-retryable) | Added `repost_ugc` alongside `publish_post` in failure settlement call |
| `_on_failure()` (max retries) | Added `repost_ugc` alongside `publish_post` in failure settlement call |

### `outbound_queue.py` — No changes needed

Already schema-aware (`repost_ugc` listed in `QUEUE_NORMAL` comment since the beginning). The `publish_content` tool already builds the correctly-shaped job envelope:

```python
# When caption_variant == "ugc_attributed":
action_type = "repost_ugc"
endpoint = "/api/instagram/repost-ugc"
payload = {
    "scheduled_post_id": ...,
    "business_account_id": ...,
    "image_url": ...,          # From ugc_content.media_url
    "caption": ...,
    "media_type": ...,
    "caption_variant": "ugc_attributed",
    "ugc_content_id": ...,     # For attribution
    "author_username": ...,    # For "@username" credit
    "permalink_url": ...,      # Link back to original post
}
```
