# Context Dump: UGC Flow — Complete State

## Pipeline Overview

```
ugc_discovery.py (APScheduler, interval 4h)
  │
  ├── UgcDedupService.check_and_add(visitor_post_id)
  │     └── Redis SET ugc_discovery:processed_ids TTL 7d
  │         └─ fallback: UGCService.get_existing_ugc_ids() → Supabase
  │
  ├── UGCService.get_monitored_hashtags(business_account_id)
  │     └── SELECT FROM ugc_monitored_hashtags WHERE is_active=true
  │
  ├── ugc_tools.fetch_hashtag_media(account_id, hashtag, limit)
  │     └── httpx sync POST /api/instagram/search-hashtag (2x tenacity retry)
  │
  ├── ugc_tools.fetch_tagged_media(account_id, limit)
  │     └── httpx sync GET /api/instagram/tags (2x tenacity retry)
  │
  ├── merge + dedup (Python set)
  │
  ├── ugc_tools.score_ugc_quality(post, brand_username)
  │     ├── engagement (30): like_count + comment_count → raw 0-100
  │     ├── media_type (25): VIDEO=100, IMAGE=70, STORY=40, REEL=90
  │     ├── caption_quality (10): brand mention + product keywords
  │     ├── brand_mention (15): exact/partial/cashtag/match
  │     └── product_keywords (15): keyword density
  │     = total 0-95 (deterministic, no LLM)
  │
  ├── route by tier:
  │     ├── HIGH (≥70): store + permission + optional DM
  │     ├── MODERATE (41-69): store only
  │     └── LOW (≤40): discard
  │
  ├── UGCService.create_or_update_ugc(data) → UPSERT ugc_content
  │
  ├── UGCService.create_ugc_permission(data) → INSERT ugc_permissions
  │     └── live_fetch_tools.trigger_repost_ugc() → OutboundQueue → backend → Instagram
  │
  └── ugc_tools.compose_dm_message() + send_permission_dm()
        └── OutboundQueue → backend POST /api/instagram/send-dm

Post-Discovery (triggered by cron or manual):
  ├── UGCService.get_granted_ugc_permissions(business_account_id)
  │     └── SELECT status='granted' FROM ugc_permissions
  ├── UGCService.get_ugc_content_for_repost(business_account_id)
  │     └── JOIN ugc_permissions + ugc_content (recently added)
  ├── live_fetch_tools.trigger_repost_ugc()
  │     └── OutboundQueue → backend → Instagram Graph API
  └── UGCService.mark_ugc_reposted(ugc_content_id, business_account_id)
        └── UPDATE ugc_permissions SET status='reposted'
```

---

## Tool Files and Current State

### `agent/tools/ugc_tools.py` — NOT mounted on AgentService

**Functions (all pure Python or sync httpx):**

| Function | Type | Notes |
|---|---|---|
| `score_ugc_quality(post, brand_username)` | Pure Python | Deterministic 0-95 scoring |
| `fetch_hashtag_media(account_id, hashtag, limit)` | sync httpx | Needs `asyncio.to_thread()` for Agent |
| `fetch_tagged_media(account_id, limit)` | sync httpx | Needs `asyncio.to_thread()` for Agent |
| `compose_dm_message(username, brand_username, permalink)` | Pure Python | String template |
| `send_permission_dm(...)` | OutboundQueue | Queue-first, no LLM |

**Key constraint:** `fetch_hashtag_media` and `fetch_tagged_media` use sync `httpx.Client()` — if mounted as `@tool` functions on AgentService, they MUST be wrapped in `asyncio.to_thread()` to avoid blocking the async event loop.

### `agent/tools/live_fetch_tools.py` — NOT mounted on AgentService

**Functions:**

| Function | Type | Notes |
|---|---|---|
| `fetch_live_comments(...)` | async | Redis L2 + backend proxy + Supabase write-through |
| `fetch_live_conversations(...)` | async | Redis L2 TTL 120s + backend proxy |
| `fetch_live_conversation_messages(...)` | async | Redis L2 TTL 300s + backend proxy |
| `trigger_repost_ugc(business_account_id, permission_id)` | async | OutboundQueue, no cache |
| `trigger_sync_ugc(business_account_id)` | async | OutboundQueue, hourly idempotency |

**Pattern:** Redis cache → backend proxy call → Supabase write-through → return data.

### `agent/services/supabase_service/_ugc.py` — UGCService (NOT @tool-decorated)

All methods are plain Python — no `@tool` decorator, no `StructuredTool` wrapper. These are the DB-layer functions called by `ugc_tools.py` and `ugc_discovery.py` directly.

| Method | DB Operation | Notes |
|---|---|---|
| `get_monitored_hashtags(business_account_id)` | SELECT | Returns list of `{id, hashtag}` |
| `get_existing_ugc_ids(business_account_id)` | SELECT | Returns `set` of `visitor_post_id` strings |
| `create_or_update_ugc(data)` | UPSERT | `on_conflict=(business_account_id, visitor_post_id)` |
| `create_ugc_permission(data)` | INSERT | Returns full row including UUID FK |
| `get_granted_ugc_permissions(business_account_id)` | SELECT | `status='granted'` |
| `get_ugc_content_for_repost(business_account_id)` | SELECT JOIN | Recently added: joins ugc_permissions + ugc_content |
| `mark_ugc_reposted(ugc_content_id, business_account_id)` | UPDATE | Sets `status='reposted'` |

---

## Database Schema

### `ugc_monitored_hashtags`
```
business_account_id  FK → instagram_business_accounts
hashtag              TEXT
is_active            BOOLEAN DEFAULT true
```

### `ugc_content` (discovered UGC posts)
```
business_account_id  FK → instagram_business_accounts
visitor_post_id      TEXT (unique with business_account_id)
author_id            TEXT
author_username      TEXT
message              TEXT (caption)
media_type           TEXT (IMAGE/VIDEO/REEL/etc.)
media_url            TEXT
permalink_url        TEXT
like_count           INTEGER
comment_count       INTEGER
created_time         TIMESTAMPTZ
source               TEXT (hashtag/tagged/both)
quality_score        INTEGER (0-95)
quality_tier         TEXT (high/moderate/low)
run_id               TEXT
```

**Unique constraint:** `(business_account_id, visitor_post_id)` — enforced at DB level.

### `ugc_permissions`
```
ugc_content_id       FK → ugc_content.id
business_account_id  FK → instagram_business_accounts
request_message      TEXT
status               TEXT (pending_send/sent/send_failed/granted/denied/expired/reposted)
run_id               TEXT
```

---

## Tool Mounting Gap

**Current state:** Zero UGC tools are mounted on AgentService.

- `UGC_TOOLS` does not exist — nothing imports from `ugc_tools.py` or `live_fetch_tools.py`
- No `UGC_SCOPE_TOOLS` defined in `agent_service.py`
- `tools/__init__.py` only aggregates: `SUPABASE_TOOLS` (9) + `AUTOMATION_TOOLS` (2) + `OVERSIGHT_TOOLS` (2) = 13 total
- `_ugc.py` methods are plain Python — no `@tool` decorator

**What needs to be mounted (if UGC scope is added to AgentService):**

1. `UGCService` methods wrapped as `@tool` functions in a new `_ugc_tools.py`:
   - `get_monitored_hashtags` → `@tool` returning `list`
   - `get_existing_ugc_ids` → `@tool` returning `list`
   - `create_or_update_ugc` → `@tool` returning `dict`
   - `create_ugc_permission` → `@tool` returning `dict`
   - `get_granted_ugc_permissions` → `@tool` returning `list`
   - `get_ugc_content_for_repost` → `@tool` returning `list`
   - `mark_ugc_reposted` → `@tool` returning `bool`

2. `fetch_hashtag_media` and `fetch_tagged_media` from `ugc_tools.py` — these need `asyncio.to_thread()` wrapper inside the `@tool` function body since they use sync httpx.

3. `trigger_repost_ugc` and `trigger_sync_ugc` from `live_fetch_tools.py` — already async, can be direct `@tool` wrappers.

---

## Dedup Architecture

```
Redis (L1): SET ugc_discovery:processed_ids
  └─ TTL 7 days
  └─ key = visitor_post_id

Supabase (authoritative fallback):
  └─ UGCService.get_existing_ugc_ids() → SELECT visitor_post_id FROM ugc_content
  └─ DB unique constraint on (business_account_id, visitor_post_id)

Python in-process:
  └─ ugc_discovery.py: local `seen_ids` set per run
```

---

## Scoring Details (Deterministic, No LLM)

```
engagement (30 pts max):
  raw = like_count + (comment_count * 3)
  → normalized: min(raw / avg_for_account * 1.5, 100) * 0.30

media_type (25 pts max):
  REEL > VIDEO > IMAGE > STORY
  REEL=90, VIDEO=75, IMAGE=70, STORY=40, CAROUSEL=60, DEFAULT=50

caption_quality (10 pts max):
  brand mention in caption → +10
  product keyword in caption → +5
  link in caption → +3 (capped at 10)

brand_mention (15 pts max):
  exact match → 15
  @-mention → 12
  cashtag → 10
  partial match → 5

product_keywords (15 pts max):
  keyword density × 15 (capped at 15)
```

---

## Recent Additions (Post Original Build)

- `UGCService.get_ugc_content_for_repost()` — JOIN query joining `ugc_permissions` + `ugc_content` for granted UGC posts ready to repost. Replaces need for separate permission + content lookups.
- `UGCService.mark_ugc_reposted()` — Updates `ugc_permissions.status = 'reposted'` after successful publish. Used by backend/repost-ugc worker.
- `trigger_repost_ugc()` in `live_fetch_tools.py` — Queue-first pattern via OutboundQueue. Worker calls backend which verifies `permission.status == 'granted'`, publishes to Instagram, then calls `mark_ugc_reposted()`.
- `trigger_sync_ugc()` in `live_fetch_tools.py` — Hourly idempotency bucket (`YYYYMMDDHH`), enqueues sync job to fetch tagged posts from Graph API.

---

## Next Steps (For Core Dev Agent)

1. **Create `_ugc_tools.py`** in `agent/services/supabase_service/`
   - Wrap `UGCService` methods as `@tool`-decorated functions following the established pattern
   - Use `@enforce_return(type)` decorator on each
   - Return types: `list`, `dict`, `bool` per method

2. **Handle async httpx wrappers**
   - `fetch_hashtag_media` and `fetch_tagged_media` in `ugc_tools.py` are sync httpx
   - When these become `@tool` functions, wrap body with `asyncio.to_thread()`

3. **Mount on AgentService**
   - Add `UGC_SCOPE_TOOLS` to `agent_service.py`
   - Add `UGC_TOOLS` to `tools/__init__.py`
   - Expose via `OVERSIGHT_TOOLS` pattern in `services/supabase_service/__init__.py`

4. **Content Scheduler UGC integration**
   - `content_scheduler.py` uses `UGCService.get_granted_ugc_permissions()` + `get_ugc_content_for_repost()` + `trigger_repost_ugc()` already
   - These are Python-direct calls, not via AgentService — intentional (pure automation pipeline, no LLM needed)

---

*Last updated: 2026-03-27*
