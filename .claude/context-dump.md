Instagram Automation Agent — Layer-by-Layer Architecture Report

  Layer 1: Entry Points

  Two types of entry points hit the system:

  1A. HTTP Routes (31 endpoints across 10 route files)

  All registered in agent.py via FastAPI include_router().

  Layer: Webhooks
  Path: POST /webhook/comment
  Auth: HMAC
  Handler: webhook_comment.process_comment_webhook()
  ────────────────────────────────────────
  Layer:
  Path: POST /webhook/dm
  Auth: HMAC
  Handler: webhook_dm.process_dm_webhook()
  ────────────────────────────────────────
  Layer:
  Path: POST /webhook/order-created
  Auth: HMAC
  Handler: webhook_order.process_order_webhook()
  ────────────────────────────────────────
  Layer: Oversight
  Path: POST /oversight/chat
  Auth: API Key + 20/min per user
  Handler: oversight.chat_endpoint()
  ────────────────────────────────────────
  Layer: Scheduler Control
  Path: POST /engagement-monitor/trigger
  Auth: API Key
  Handler: SchedulerService.trigger_now()
  ────────────────────────────────────────
  Layer:
  Path: POST /content-scheduler/trigger
  Auth: API Key
  Handler: SchedulerService.trigger_now()
  ────────────────────────────────────────
  Layer:
  Path: POST /analytics-reports/trigger-daily
  Auth: API Key
  Handler: SchedulerService.trigger_now()
  ────────────────────────────────────────
  Layer: Queue
  Path: POST /queue/retry-dlq
  Auth: API Key
  Handler: OutboundQueue.retry_dlq()
  ────────────────────────────────────────
  Layer: Status (public)
  Path: GET /health, GET /metrics
  Auth: None
  Handler: health/metrics handlers

  1B. Schedulers (8 background jobs via APScheduler AsyncIOScheduler)

  ┌──────────┬────────┬──────────────────────────────┬────────────────────────────┐
  │   Job    │  Type  │           Schedule           │       Entry Function       │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ DM       │ interv │ DM_MONITOR_INTERVAL_MINUTES  │ dm_monitor_run()           │
  │ Monitor  │ al     │                              │                            │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Engageme │ interv │ ENGAGEMENT_MONITOR_INTERVAL_ │                            │
  │ nt       │ al     │ MINUTES                      │ engagement_monitor_run()   │
  │ Monitor  │        │                              │                            │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Content  │        │                              │                            │
  │ Schedule │ cron   │ 09:00, 14:00, 19:00          │ content_scheduler_run()    │
  │ r        │        │                              │                            │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ UGC Disc │ interv │ UGC_COLLECTION_INTERVAL_HOUR │ ugc_discovery_run()        │
  │ overy    │ al     │ S                            │                            │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Analytic │ cron   │ Daily 23:00                  │ analytics_reports_run("dai │
  │ s Daily  │        │                              │ ly")                       │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Analytic │ cron   │ Weekly Sunday 23:00          │ analytics_reports_run("wee │
  │ s Weekly │        │                              │ kly")                      │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Weekly   │        │                              │                            │
  │ Attribut │ cron   │ Monday 08:00                 │ weekly_attribution_learnin │
  │ ion      │        │                              │ g_run()                    │
  │ Learning │        │                              │                            │
  ├──────────┼────────┼──────────────────────────────┼────────────────────────────┤
  │ Heartbea │ interv │ HEARTBEAT_INTERVAL_MINUTES   │ heartbeat_sender_run()     │
  │ t Sender │ al     │                              │                            │
  └──────────┴────────┴──────────────────────────────┴────────────────────────────┘

  ---
  Layer 2: Middleware (global, applied in agent.py)

  HTTP Request → CORSMiddleware → Request ID → api_key_middleware → SlowAPI Limiter →
  Route Handler

  - CORSMiddleware: Whitelist from CORS_ALLOW_ORIGINS
  - api_key_middleware: X-API-Key header check. Bypassed for PUBLIC_PATHS (health,
  metrics, webhooks, status endpoints)
  - SlowAPI Limiter: Redis-backed, global default 60/min, per-route overrides

  ---
  Layer 3: Service Layer

  3A. AgentService — Tool-binding orchestration

  Used by: Webhook handlers (comment, dm, order)

  _llm_semaphore (MAX_CONCURRENT_LLM=2)
      ↓
  _analyze(prompt)
      ├── LLMService.invoke(full_prompt, llm_with_tools)  ← Pass 1 (retry via
  LLMService)
      │       ↓
      │   ChatOllama.bind_tools(scope_tools)  → 3-7 tools bound
      │       ↓
      │   LLM may emit tool_calls[]
      │
      ├── [if tools called] _execute_tool_calls_async()  ← Parallel via
  asyncio.gather()
      │       └── asyncio.wait_for(tool.invoke(), timeout=5s) × N tools
      │               ↓
      │           SupabaseService (static methods)
      │               ├── L1 cache (TTLCache)
      │               ├── L2 cache (Redis)
      │               ├── tenacity retry (3x, backoff 0.5-4s)
      │               └── pybreaker circuit breaker (5 failures → 30s open)
      │
      ├── [if tool outputs] LLMService.invoke(enriched_prompt, llm_with_tools)  ← Pass
  2
      │
      └── LLMService._parse_json_response(raw)  → structured dict

  Scopes:

  ┌─────────────┬─────────┬──────────────────────────────────────────┐
  │    Scope    │  Tools  │                 Used By                  │
  ├─────────────┼─────────┼──────────────────────────────────────────┤
  │ engagement  │ 7 tools │ Engagement monitor, DM monitor, webhooks │
  ├─────────────┼─────────┼──────────────────────────────────────────┤
  │ content     │ 4 tools │ Content scheduler pipelines              │
  ├─────────────┼─────────┼──────────────────────────────────────────┤
  │ attribution │ 3 tools │ Sales attribution pipelines              │
  └─────────────┴─────────┴──────────────────────────────────────────┘

  3B. LLMService — Low-level LLM wrapper

  Used by: AgentService, content_tools.generate_and_evaluate(),
  attribution_tools.evaluate_attribution(), analytics_tools.generate_llm_insights(),
  automation_tools._analyze_message()

  LLMService.invoke(prompt, llm_instance)
      ├── asyncio.to_thread(llm_instance.invoke, prompt)
      │       ↓
      │   ChatOllama (base_url=OLLAMA_HOST, model=llama3.1:8b, temperature=0.3,
  timeout=60s)
      │
      └── [on transient error] retry with exponential backoff
              Attempt 1: ~1.0s delay
              Attempt 2: ~2.5s delay
              Attempt 3: ~5.5s delay
              (base_delay × 2^attempt + random(0, 0.5s) jitter)

  Transient errors retryable: connection, timeout, unavailable, busy, 500, 503, 429,
  rate limit, model loading, econnreset, eof, broken pipe, network

  Non-retryable (immediate raise): JSON parse errors, validation errors, bad prompts

  3C. SupabaseService — Data access + caching + resilience

  All methods are static. Used by every pipeline that touches the database.

  SupabaseService.method(args)
      ├── L1 cache check (cachetools TTLCache, per-instance)
      ├── L2 cache check (Redis GET)
      ├── tenacity._execute_query()     ← 3 retries, backoff 0.5-4s
      │       └── pybreaker CircuitBreaker  ← opens after 5 consecutive failures
      └── supabase.table(...).execute()
              ↓
          [on write] _cache_set() → Redis SETEX (cache invalidation)

  3D. OutboundQueue — Durable job queue

  Redis-first, Supabase fallback. All 5 outbound Instagram actions go through here:

  Pipeline code
      └── OutboundQueue.enqueue(job)
              ├── [Redis available] LPUSH to queue:{high|normal}
              ├── [Redis down] SupabaseService.create_outbound_job()
              └── [idempotency check]
  SupabaseService.get_outbound_job_by_idempotency_key()

  Queues:
  - outbound:queue:high — reply_comment, reply_dm (commented/DMed within 24h)
  - outbound:queue:normal — publish_post, send_permission_dm, repost_ugc, sync_ugc
  - outbound:queue:scheduled ZSET — delayed retries (score = next_retry_at timestamp)
  - outbound:dlq ZSET — dead letter queue

  Retry delays: 60s → 120s → 240s → 480s → 960s (5 levels)

  3E. QueueWorker — Background job executor

  Three concurrent asyncio loops:

  QueueWorker
      ├── _high_priority_loop()     → polls QUEUE_HIGH every 0.5s
      ├── _normal_priority_loop()    → polls QUEUE_NORMAL every 0.5s
      └── _scheduled_retry_loop()   → drains SCHEDULED ZSET every 30s
              ↓
          _execute_job(job)
              ├── SETNX lock (120s TTL)
              ├── httpx.AsyncClient POST → {BACKEND_API_URL}{endpoint}
              │
              ├── [success] → mark completed, release lock
              ├── [retryable failure] → ZADD to SCHEDULED with delay
              └── [auth failure] → DLQ + mark_account_disconnected() +
  create_system_alert()

  3F. PromptService — Dynamic prompt loader

  PromptService.get(key)
      ├── [DB has prompt] → use DB version (overrides static default)
      └── [fallback] → prompts.DEFAULT_PROMPTS[key]

  Loads all is_active=True rows at startup. Allows runtime prompt updates without
  redeployment.

  3G. OversightBrain — Custom explainability layer

  Does NOT use AgentService. Uses direct llm.invoke() with <<TOOL_CALL:tool|args>> text
   markers parsed via regex.

  chat(question, chat_history)
      ├── [cache hit? L1 TTLCache + L2 Redis] → return cached
      ├── _fetch_auto_context()  → 12 most recent audit_log entries
      ├── PromptService.get("oversight_brain")
      ├── llm.invoke(prompt)     ← Pass 1 (direct, no tool binding)
      │       ↓
      │   LLM may emit <<TOOL_CALL:tool_name|args>> markers
      │       ↓
      ├── [if markers] _execute_oversight_tool() → Pass 2
      │       └── tools.oversight_tools._get_audit_log_entries()
      │       └── tools.oversight_tools._get_run_summary()
      └── LLMService._parse_json_response(raw)

  Separate semaphore: _llm_semaphore = asyncio.Semaphore(2) (independent from
  AgentService's semaphore).

  ---
  Layer 4: Tools

  4A. LangChain StructuredTools (12 total — bound via llm.bind_tools())

  SUPABASE_TOOLS (7) — all route through SupabaseService:

  ┌─────────────────────────────┬───────────────────────────────┬──────────────────┐
  │            Tool             │        Supabase Method        │      Cache       │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_post_context            │ instagram_media SELECT        │ L1 30s + L2 30s  │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_account_info            │ instagram_business_accounts   │ L1 60s + L2 60s  │
  │                             │ SELECT                        │                  │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_recent_comments         │ instagram_comments SELECT     │ L1 + L2          │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_dm_history              │ instagram_dm_messages JOIN    │ L1 + L2          │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_dm_conversation_context │ instagram_dm_conversations    │ L1 + L2          │
  │                             │ SELECT                        │                  │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ get_post_performance        │ instagram_media aggregated    │ L1 + L2          │
  ├─────────────────────────────┼───────────────────────────────┼──────────────────┤
  │ log_agent_decision          │ audit_log INSERT              │ None             │
  │                             │                               │ (write-through)  │
  └─────────────────────────────┴───────────────────────────────┴──────────────────┘

  AUTOMATION_TOOLS (3):

  ┌──────────────────┬────────────────────────────────────────────────┬────────────┐
  │       Tool       │                 Implementation                 │  Backend   │
  │                  │                                                │    Call    │
  ├──────────────────┼────────────────────────────────────────────────┼────────────┤
  │ analyze_message  │ _analyze_message() → LLMService.invoke() →     │ None       │
  │                  │ _apply_hard_escalation_rules()                 │            │
  ├──────────────────┼────────────────────────────────────────────────┼────────────┤
  │ reply_to_comment │ _reply_to_comment() → OutboundQueue.enqueue()  │ Queue-only │
  ├──────────────────┼────────────────────────────────────────────────┼────────────┤
  │ reply_to_dm      │ _reply_to_dm() → OutboundQueue.enqueue()       │ Queue-only │
  └──────────────────┴────────────────────────────────────────────────┴────────────┘

  OVERSIGHT_TOOLS (2):

  ┌───────────────────────┬─────────────────────────────────────────────────────────┐
  │         Tool          │                     Implementation                      │
  ├───────────────────────┼─────────────────────────────────────────────────────────┤
  │ get_audit_log_entries │ _get_audit_log_entries() →                              │
  │                       │ SupabaseService._execute_query()                        │
  ├───────────────────────┼─────────────────────────────────────────────────────────┤
  │ get_run_summary       │ _get_run_summary() → SupabaseService._execute_query()   │
  └───────────────────────┴─────────────────────────────────────────────────────────┘

  4B. Internal Pipeline Functions (NOT registered as LangChain tools)

  These are called directly by scheduler/orchestrator code — the LLM never sees them:

  File: content_tools.py
  Functions: select_asset, generate_and_evaluate, publish_post
  Kind: Async + pure Python
  ────────────────────────────────────────
  File: attribution_tools.py
  Functions: detect_all_signals, classify_signal_strategy, evaluate_attribution,
    build_customer_journey, calculate_multi_touch_models
  Kind: Async + pure Python
  ────────────────────────────────────────
  File: analytics_tools.py
  Functions: collect_instagram_data, aggregate_metrics, generate_recommendations,
    generate_llm_insights
  Kind: Async + pure Python
  ────────────────────────────────────────
  File: ugc_tools.py
  Functions: score_ugc_quality, fetch_hashtag_media, send_permission_dm
  Kind: Sync
  ────────────────────────────────────────
  File: live_fetch_tools.py
  Functions: fetch_live_comments, fetch_live_conversations, trigger_repost_ugc
  Kind: Async

  ---
  Layer 5: External Dependencies

  Agent
      ├── Supabase (Postgres + Redis)
      │       ├── PostgreSQL: instagram_media, instagram_comments, instagram_dm_*,
  audit_log, scheduled_posts, ugc_*, sales_attributions, analytics_reports,
  outbound_queue_jobs, system_alerts, prompt_templates
      │       └── Redis: L2 cache, job queue (LIST/ZSET), locks, dedup sets
      │
      ├── Ollama (llama3.1:8b, Q4_K_M)
      │       └── HTTP: model inference, health check
      │
      ├── Backend API (agent.888intelligenceautomation.in → nginx → localhost:3001)
      │       ├── POST /api/instagram/reply-comment
      │       ├── POST /api/instagram/reply-dm
      │       ├── POST /api/instagram/publish-post
      │       ├── POST /api/instagram/send-dm
      │       ├── POST /api/instagram/repost-ugc
      │       ├── GET  /api/instagram/insights (account + media)
      │       ├── POST /api/instagram/search-hashtag
      │       ├── GET  /api/instagram/tags
      │       └── POST /api/instagram/agent/heartbeat
      │
      └── Instagram Graph API (via backend proxy only — agent never calls IG directly)

  ---
  Critical Path Diagram (engagement pipeline as example)

  Instagram Webhook (new comment)
      ↓ [HMAC verified]
  POST /webhook/comment → webhook_comment.process_comment_webhook()
      ↓
  SupabaseService.upsert_webhook_comment()       ← write-through
      ↓
  engagement_monitor_run() [scheduler]
      ↓ per account (semaphore-limited)
  SupabaseService.get_unprocessed_comments()
      ↓ per comment (semaphore-limited)
  get_post_context() [LangChain tool, bound 7 tools]
      → SupabaseService.get_post_context()
          → L1 cache → L2 cache → tenacity → Supabase
      ↓
  _analyze_message() [automation_tools, direct llm.invoke]
      → LLMService.invoke(full_prompt, llm)      ← retry/backoff ✅
      → SYSTEM_PROMPT + analyze_message prompt
      → LLM → structured JSON response
      → _apply_hard_escalation_rules()
      ↓
  [if auto-reply] _reply_to_comment() [automation_tools]
      → OutboundQueue.enqueue(job)
          → Redis LPUSH (fast path)
          OR Supabase INSERT (fallback)
      ↓
  [QueueWorker background]
      → OutboundQueue.dequeue()
      → httpx POST /api/instagram/reply-comment
      → Backend → Instagram Graph API
      ↓
  SupabaseService.mark_comment_processed()       ← write-through
  SupabaseService.log_decision()                 ← audit log

  ---
  Summary: Two LLM Invocation Patterns

  Pattern: AgentService.analyze_async()
  Route: _analyze()
  Retry via: LLMService.invoke()
  Tool Binding: llm.bind_tools(scope_tools)
  Used For: Webhook handlers
  ────────────────────────────────────────
  Pattern: LLMService.invoke() directly
  Route: _analyze_message(), generate_and_evaluate(), evaluate_attribution(),
    generate_llm_insights()
  Retry via: LLMService.invoke()
  Tool Binding: None (pure inference)
  Used For: Pipeline LLM calls
  ────────────────────────────────────────
  Pattern: OversightBrain
  Route: chat()
  Retry via: None (own retry loop)
  Tool Binding: None (custom <<TOOL_CALL>> markers)
  Used For: Explainability