# Instagram Automation Agent — Architecture Report (Updated)

---

## Section 1: Entry Points

Two types: HTTP Routes (31 endpoints) + Schedulers (8 background jobs).

### HTTP Routes

| Path | Auth | Handler |
|------|------|---------|
| POST /webhook/comment | HMAC | webhook_comment.process_comment_webhook() |
| POST /webhook/dm | HMAC | webhook_dm.process_dm_webhook() |
| POST /webhook/order-created | HMAC | webhook_order.process_order_webhook() |
| POST /oversight/chat | API Key | oversight.chat_endpoint() |
| POST /engagement-monitor/trigger | API Key | SchedulerService.trigger_now() |
| POST /content-scheduler/trigger | API Key | SchedulerService.trigger_now() |
| POST /analytics-reports/trigger-daily | API Key | SchedulerService.trigger_now() |
| POST /queue/retry-dlq | API Key | OutboundQueue.retry_dlq() |
| GET /health, GET /metrics | None | health/metrics handlers |

### Schedulers (APScheduler AsyncIOScheduler)

| Job | Schedule | Entry Function |
|-----|----------|----------------|
| DM Monitor | interval | dm_monitor_run() |
| Engagement Monitor | interval | engagement_monitor_run() |
| Content Scheduler | cron 9am/2pm/7pm | content_scheduler_run() |
| UGC Discovery | interval | ugc_discovery_run() |
| Analytics Daily | cron 23:00 | analytics_reports_run("daily") |
| Analytics Weekly | cron Sun 23:00 | analytics_reports_run("weekly") |
| Weekly Attribution Learning | cron Mon 08:00 | weekly_attribution_learning_run() |
| Heartbeat Sender | interval | heartbeat_sender_run() |

---

## Section 2: Middleware

HTTP Request → CORSMiddleware → Request ID → api_key_middleware → SlowAPI Limiter → Route Handler

- CORS whitelist from CORS_ALLOW_ORIGINS
- api_key_middleware: X-API-Key check, bypassed for PUBLIC_PATHS
- SlowAPI Limiter: Redis-backed, 60/min default, per-route overrides

---

## Section 3: Service Layer

### AgentService — Tool-binding orchestration (DEAD IN PRODUCTION)

`AgentService` with scoped tool binding is **never actually used** in any production pipeline. `SCOPED_TOOLS` is defined but uninstantiated.

**Actual callers of AgentService:**
- None in production. All callers use direct `LLMService.invoke()` instead.

**`ENGAGEMENT_SCOPE_TOOLS`** (6 tools: `get_post_context`, `get_account_info`, `get_recent_comments`, `log_decision`, `analyze_message`, `reply_to_comment`, `reply_to_dm`) is defined in `agent_service.py` but **never bound or called**. The engagement monitor imports `_analyze_message` (raw function) directly, not `analyze_message_tool`.

**`CONTENT_SCOPE_TOOLS`** (4 tools) — dead, never used.
**`ATTRIBUTION_SCOPE_TOOLS`** (3 tools) — dead, never used.

### LLMService — Low-level LLM wrapper (LIVE)

Used by: `_analyze_message()`, `generate_and_evaluate()`, `evaluate_attribution()`, `generate_llm_insights()`, and `AgentService._analyze()`.

```
LLMService.invoke(prompt, llm_instance)
    └── asyncio.to_thread(llm_instance.invoke, prompt)  — blocks thread, not event loop
            └── ChatOllama (sync HTTP via httpx)
    └── [on exception] _is_retryable() → exponential backoff → retry
            Attempts: ~1.0s, ~2.5s, ~4.5s (with jitter)
```

**Retry parameters:** `base_delay=1.0`, `JITTER_RANGE=0.5`, `max_retries=3`
**Retryable keywords (string match, not isinstance):** connection, timeout, unavailable, busy, 500, 503, 429, rate limit, model loading, econnreset, eof, broken pipe, network
**Non-retryable:** JSON parse errors, ValidationError — raise immediately through to caller

**Direct `llm.invoke()` callers (NO LLMService retry):**
- `oversight_brain.chat()` — both passes use direct `llm.invoke()` via `asyncio.to_thread()`, NO retry, NO exponential backoff. TimeoutError caught → fallback text. Second-pass failure → falls back to first-pass text.
- `LLMService.analyze()` — deprecated sync path, direct `llm.invoke()`, 1x instant retry only, no backoff.

### SupabaseService — Data access + L1/L2 cache + tenacity retry + pybreaker

```
Method (e.g., get_post_context_by_uuid)
    1. L1 cachetools TTLCache check (per-process singleton, 30s TTL for post_context)
    2. L2 Redis cache_get (shared across workers, 30s TTL, sync redis client BLOCKS event loop)
    3. execute() → tenacity (3 attempts, 0.5s/1s/2s backoff) → pybreaker (5 failures → 30s open)
    4. On success: populate L1 + L2
    5. On CircuitBreakerError: caught at method level, returns {} — does NOT crash pipeline
```

**Cache key fragmentation:** `get_post_context()` uses `post_ctx:{instagram_media_id}`; `get_post_context_by_uuid()` uses `post_ctx_uuid:{uuid}` — same post indexed under two keys.

**NOT cached at L1 or L2:** `get_active_business_accounts()`, `get_unprocessed_comments()`, `get_recent_comments()`, all writes.

**L2 Redis sync client:** `socket_timeout=2` on all Redis ops — Redis outage fails fast, doesn't block indefinitely.

**Known issue:** `redis.Redis` is synchronous — all L2 cache ops block the asyncio event loop. TODO: migrate to `redis.asyncio.Redis` (redis>=5.0.1 already installed).

### OutboundQueue — Durable job queue (LIVE)

```
OutboundQueue.enqueue(job)
    1. Idempotency check via Supabase (NOT Redis) — filters out completed+dlq only
    2. Redis LPUSH (fast path, atomic)
    3. Supabase INSERT (fallback when Redis down)
```

**Idempotency key contract:**
- Return `{success: True, queued: True}` → actually pushed
- Return `{success: True, queued: False, deduplicated: True}` → deduplicated (previous job found in pending/processing/failed/scheduled)
- Return `{success: False}` → both backends failed

**BUG (HIGH):** `was_replied = result.get("success", False)` in `_handle_auto_reply()` evaluates True for deduplicated returns — comments are permanently marked "replied" in DB and audit log even when no reply was sent.

**DLQ idempotency bug (HIGH):** `move_to_dlq()` does NOT clear `idempotency_key`. `retry_dlq()` resets Supabase row to `pending` then calls `enqueue()` with original key → idempotency check finds the pending row → silently returns `deduplicated: True` → retry never happens.

**Supabase fallback for scheduled retries is orphaned:** `schedule_retry()` writes `status='failed'` in Supabase (not 'scheduled'). `_scheduled_retry_loop` only drains Redis `QUEUE_SCHEDULED` ZSET — Supabase fallback retry jobs are never picked up by the drain loop.

### QueueWorker — Background job executor (LIVE)

Three concurrent asyncio loops (independent, no fairness mechanism):

```
_high_priority_loop()    — polls QUEUE_HIGH every 0.5s
_normal_priority_loop()  — polls QUEUE_NORMAL every 0.6s (staggered +0.1s)
_scheduled_retry_loop()  — drains QUEUE_SCHEDULED every 30s
```

**Lock mechanism:** `SET outbound:lock:{job_id} 1 NX EX 120` — atomic mutex with 120s auto-expiry. If worker crashes after acquiring lock: lock expires, job can be re-executed by another worker.

**BUG (MEDIUM):** Only `publish_post` actions get `_is_safe_to_execute()` double-protection. `reply_comment` and `reply_dm` have no guard — if worker crashes mid-execution and lock expires, duplicate HTTP call possible.

**Backend 429 handling:** Respects `retry_after_seconds` from backend JSON body directly (no floor). If absent, floor of 300s applied. Immediate DLQ if `retryable: false` in response.

---

## Section 4: Tool Taxonomy

### LangChain StructuredTools (12 total, ALL DEAD — never bound in production)

**SUPABASE_TOOLS (7):** Pure `SupabaseService` wrappers. Never called via `bind_tools()` in any live path.

**AUTOMATION_TOOLS (3):**
- `_analyze_message()` → `LLMService.invoke()` directly, no `bind_tools()`, no tool calling
- `_reply_to_comment()` → `OutboundQueue.enqueue()` only
- `_reply_to_dm()` → `OutboundQueue.enqueue()` only

**OVERSIGHT_TOOLS (2):** Audit-log queries. Never bound via `AgentService` in live paths.

### Internal Pipeline Functions (NOT LangChain tools, called directly)

`content_tools.py`: `select_asset`, `generate_and_evaluate`, `publish_post`
`attribution_tools.py`: `detect_all_signals`, `classify_signal_strategy`, `evaluate_attribution`, `build_customer_journey`, `calculate_multi_touch_models`
`analytics_tools.py`: `collect_instagram_data`, `aggregate_metrics`, `generate_recommendations`, `generate_llm_insights`
`ugc_tools.py`: `score_ugc_quality`, `fetch_hashtag_media`, `send_permission_dm`
`live_fetch_tools.py`: `fetch_live_comments`, `fetch_live_conversations`, `trigger_repost_ugc`

---

## Section 5: Tool Calling Mechanics

### How `llm.bind_tools()` Works (LangChain)

`ChatOllama.bind_tools(tool_list)` serializes each `StructuredTool` (name + description + Pydantic args_schema) into a JSON object injected into the message history as `{"type": "function", "function": {...}}`. The tool schema is part of the prompt — not a separate API call.

When Ollama decides to call a tool, it emits an `AIMessage` with a `tool_calls` attribute (list of `{name, args}` dicts). LangChain deserializes arguments via the tool's Pydantic `args_schema` at `tool.invoke()` time.

### Two-Pass Flow (in AgentService._analyze — DEAD)

```
Pass 1: LLMService.invoke(full_prompt, llm_with_tools)
    ├── No tool_calls → parse content as JSON → return
    └── Has tool_calls → _execute_tool_calls_async() in parallel
                              └── asyncio.wait_for(tool.invoke(), timeout=5s) per tool
                              └── Tool timeout → {"error": "timeout"} dict returned
                              └── Tool exception → {"error": str(e)} dict returned
                         → Pass 2: LLMService.invoke(enriched_prompt, llm_with_tools)
                              └── _build_enriched_prompt() prepends original prompt + appends tool results
                              └── parse final JSON
```

**`_build_enriched_prompt()` injects:** Raw `json.dumps(output, default=str)` for each tool result directly into the prompt. **Prompt injection risk:** Tool outputs (which may contain user-controlled text like comment content) are not sanitized — re-injected verbatim into LLM context.

### Tool Timeout Isolation

`asyncio.gather(*tasks, return_exceptions=True)` — a timeout on one tool does NOT fail the batch. The timeout returns `{"error": "timeout"}` dict, which is passed to the second-pass LLM. The LLM is informed of the failure rather than the call crashing.

---

## Section 6: Engagement Monitor Pipeline (LIVE)

```
engagement_monitor_run()
  └─ _process_account()
       └─ _process_comment_safe() [semaphore-wrapped, error-isolated]
            └─ _process_comment()
                 ├─ get_post_context_by_uuid()        → L1 → L2 → tenacity → Supabase
                 ├─ _analyze_message()                 → LLMService.invoke() direct, no bind_tools
                 │      └─ SYSTEM_PROMPT + analyze_message prompt (pre-injected context)
                 │      └─ LLM → structured JSON
                 │      └─ _apply_hard_escalation_rules() — 4 rules (urgent/VIP/complaint/complex)
                 ├─ route:
                 │    needs_human=True       → _handle_escalation()
                 │    suggested_reply+conf   → _handle_auto_reply()  [BUG: was_replied check]
                 │    else                   → _handle_skip()
                 ├─ mark_comment_processed()         → Supabase write
                 ├─ DedupService.mark_processed()    → Redis SET
                 └─ log_decision()                  → audit_log INSERT
```

**Dedup: Redis SET `engagement_monitor:processed_ids:{account_id}` TTL 24h + `processed_by_automation=True` column.**

**BUG (HIGH):** `_handle_auto_reply()` marks comment processed BEFORE verifying queue enqueue succeeded. If `OutboundQueue.enqueue()` returns `success=False`, the comment is permanently lost — marked processed in DB + Redis, never retried.

**BUG (MEDIUM):** `execution_id` field in audit log always null — field name wrong (`job_id` is the actual identifier, but true execution tracking requires querying the QueueWorker's in-flight state).

---

## Section 7: Engagement Monitor vs Webhook Pipeline Differences

| Aspect | Comment Webhook | Engagement Monitor |
|--------|----------------|-------------------|
| Dedup write-through | `processed_by_automation=True` set BEFORE log_decision (correct) | Set AFTER routing in action handlers (race window) |
| Execution outcome logging | None | `_log_execution_outcome()` per reply |
| Error events | Propagates to 503 | `engagement_monitor_comment_error` logged |
| Event types | `webhook_comment_processed` | `engagement_monitor_escalation` / `engagement_monitor_comment_processed` |
| Comment ID to audit | Instagram numeric ID | Supabase UUID |

---

## Section 8: Known Issues Ranked by Severity

### CRITICAL

1. **DLQ Retry Silently Dropped** (`outbound_queue.py` + `queue_routes.py`)
   `move_to_dlq()` does not clear `idempotency_key`. `retry_dlq()` resets to `pending` then calls `enqueue()` with same key. Idempotency check finds the `pending` row → returns `deduplicated: True` → retry never happens.
   **Fix:** Clear `idempotency_key` in `move_to_dlq()` OR change deduplication query to `status == 'pending'` as the active guard.

2. **Comment Permanently Lost on Queue Failure** (`engagement_monitor.py`)
   `_handle_auto_reply()` calls `mark_comment_processed()` + `DedupService.mark_processed()` regardless of queue enqueue result. `OutboundQueue.enqueue()` returning `success=False` → comment permanently unretried.
   **Fix:** Only mark processed if `result.get("success") and result.get("queued")`.

### HIGH

3. **Deduplication Misclassified as Success** (`engagement_monitor.py` + `automation_tools.py`)
   `was_replied = result.get("success", False)` is True for deduplicated returns. DB `was_replied` column and audit log permanently wrong for deduplicated comments.
   **Fix:** Check `result.get("queued") == True` as authoritative flag.

4. **Oversight Brain Has No Retry Protection** (`oversight_brain.py`)
   Both passes use direct `llm.invoke()` via `asyncio.to_thread()`. No `LLMService.invoke()` wrapping. No exponential backoff. A transient Ollama timeout falls back to text without retry. Second-pass failure falls back to first-pass text.
   **Fix:** Route through `LLMService.invoke()` for both passes.

### MEDIUM

5. **Reply Comment/DM Race Condition** (`queue_worker.py`)
   No `_is_safe_to_execute()` guard for `reply_comment`/`reply_dm`. Worker crash mid-execution + 120s lock expiry → duplicate HTTP call possible.
   **Fix:** Add `_is_safe_to_execute()` guard for all action types, or use job state machine.

6. **Supabase Scheduled Retry Jobs Orphaned** (`outbound_queue.py`)
   `schedule_retry()` writes `status='failed'` in Supabase. `_scheduled_retry_loop` only drains Redis ZSET. Jobs enqueued during Redis outage and later retried via Supabase path are never drained back to Redis.
   **Fix:** Add a `drain_supabase_scheduled()` that queries `status='failed'` AND `next_retry_at < now()` and re-enqueues them.

7. **Post Context Cache Fragmentation** (`supabase_service/_engagement.py`)
   `get_post_context()` and `get_post_context_by_uuid()` cache the same data under different keys. Engagement monitor only uses `get_post_context_by_uuid()` — misses any cache entries from other callers using `get_post_context()`.
   **Fix:** Unify to single cache key scheme using `instagram_media_id` as canonical key.

8. **Sync Redis Client Blocks Event Loop** (`supabase_service/_infra.py`)
   `redis.Redis` is synchronous — all L2 cache operations (get, set, setex) block the asyncio event loop. With up to 3 concurrent engagement analyses, L2 cache misses cause event loop stalls.
   **Fix:** Migrate to `redis.asyncio.Redis` (already in requirements as redis>=5.0.1).

### LOW

9. **`SCOPED_TOOLS` Is Dead Infrastructure** (`agent_service.py`)
   `ENGAGEMENT_SCOPE_TOOLS`, `CONTENT_SCOPE_TOOLS`, `ATTRIBUTION_SCOPE_TOOLS` defined but never instantiated in production. All engagement/content/attribution pipelines use direct `LLMService.invoke()` without `bind_tools()`.
   **Fix:** Either remove (if not planning to use) or wire up actual `AgentService(scope="engagement")` paths.

10. **`_is_retryable` String Matching Risks** (`llm_service.py`)
    Pure string match on `str(error)`. `"connection"` and `"network"` are broad — any exception whose message contains these substrings (even indirectly) triggers retry. No `isinstance()` dispatch.
    **Fix:** Add exception-type dispatch for specific known exception types before falling back to string match.

11. **Prompt Injection Vector via Tool Output** (`agent_service.py`)
    `_build_enriched_prompt()` injects raw `json.dumps(output)` into LLM prompt without sanitization. User-controlled text (comment text, usernames) re-injected verbatim. A carefully crafted comment could influence JSON output format.
    **Fix:** Escape or structure tool outputs before injection, or use a separate tool-result schema that constrains output format.

12. **Dedup Circuit Breaker Gap** (`outbound_queue.py`)
    If circuit breaker is OPEN during idempotency check, `get_outbound_job_by_idempotency_key()` returns `{}`. Enqueue proceeds without deduplication check — potential duplicate.
    **Fix:** On `CircuitBreakerError` in idempotency check, fail-safe: return `success=False` (don't enqueue) rather than bypassing the check.

13. **Confusing Metric Label Transform** (`engagement_monitor.py`)
    `"error"` → `"errors"` dict key transform in Prometheus metric loop is obfuscated.
    **Fix:** Use consistent naming throughout.

---

## Section 9: LLM Invocation Patterns — Summary

| Pattern | Used By | Retry | Tool Binding |
|---------|---------|-------|-------------|
| `LLMService.invoke()` direct | `_analyze_message()`, content_tools, attribution_tools, analytics_tools | Yes (exponential backoff) | None |
| `AgentService._analyze()` | None (dead) | Yes (via LLMService) | Yes (7-3 tools) |
| `AgentService._astream()` | None (dead) | Yes (inline retry in `_stream_pass`) | Yes |
| `OversightBrain.chat()` | None (oversight_brain.py uses direct `llm.invoke()`) | **No** | Custom `<<TOOL_CALL>>` markers |
| `LLMService.analyze()` | None (deprecated) | 1x instant retry | None |
