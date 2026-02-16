### Final Architecture Sketch & Source of Truth Context Dump
**Document Title:** Instagram Automation System – Complete Architectural Blueprint (Version 1.0, Feb 13 2026)  
**Authors:** System Collaboration (Grok + User Iteration)  
**Repos Covered:**  
- Agent: https://github.com/C45h888/instagram-automation-agent (main: 21d1ceb – Oversight Brain live)  
- Dashboard Backend: https://github.com/C45h888/instagram-automation-dashboard/backend.api (main: e7cdc77 – SSE Proxy live)  
- Dashboard Frontend: https://github.com/C45h888/instagram-automation-dashboard (Vite/React – pre-refactor baseline)  
- Shared: Supabase project (public schema, RLS enabled)  

This document serves as the **single source of truth** for the entire system. It consolidates all planning from the conversation history (Feb 7–13 2026), including refactors, phases, data flows, endpoints, and the Oversight Brain integration. Any future changes must reference and update this doc via PR/merge.

---

#### **Architectural Vision: Building the World's First Explainable Instagram Automation Platform**
The Instagram Automation System is designed as a **secure, autonomous, and human-auditable AI agent ecosystem** that transforms raw Instagram interactions (comments, DMs, UGC, tags) into revenue-driving actions (replies, content scheduling, permission requests, attribution). Unlike black-box tools (e.g., Zapier + GPT wrappers), our vision emphasizes **explainability at every layer**: the agent logs every decision with reasoning, the Oversight Brain provides natural-language Q&A over history, and the dashboard delivers real-time, clickable insights.

**Core Principles:**  
1. **Zero-Trust Security:** Agent never touches IG tokens; backend is the sole Graph API gateway.  
2. **Single Source of Truth:** Supabase holds all data (events, decisions, UGC, attributions) – no sync drift.  
3. **Autonomy with Guardrails:** Agent handles 90% of decisions (e.g., reply/ignore/delete) via LLM + tools; humans oversee via dashboard + chat.  
4. **Real-Time Explainability:** SSE streaming turns the agent into a "conversational teammate" – users ask "Why reject UGC X?" and get instant, cited answers.  
5. **Scalability on Hetzner CX33:** Docker Compose (frontend:3000, backend:3001, agent:3002 + Ollama) <7GB RAM; Redis for caching/rate-limits.  

**High-Level System Goals:**  
- **Automation Coverage:** UGC discovery (hashtag/tag search → score → DM permission), engagement monitoring (comment/DM replies), content scheduling (publish approved UGC), sales attribution (link tracking → revenue tie-back).  
- **Human Loop:** Dashboard for manual approve/reject; Oversight chat for "why" questions.  
- **Metrics-Driven:** Audit_log tracks confidence/rejection reasons; analytics aggregates ROI (e.g., attributed revenue from agent-published posts).  
- **Production Readiness:** RLS on Supabase, per-user rate-limits, structured logging, Prometheus endpoints, A/B prompt testing.  

**Deployment Stack:**  
- **Infra:** Hetzner CX33 VPS (Docker Compose: frontend, backend, agent+Ollama, Redis).  
- **DB:** Supabase (Postgres + Realtime) – tables: instagram_business_accounts (tokens), audit_log (decisions), ugc_discovered (permissions), scheduled_posts (queue), attribution_events (revenue), oversight_conversations (chat history).  
- **LLM:** Nemotron-8B (local via Ollama) – prompts versioned in Supabase.  
- **Monitoring:** Backend /metrics (Prometheus), agent audit_log, frontend error boundaries.  

**Data Flow Master Diagram (ASCII + Explanation):**  
```
┌─────────────────────┐     ┌─────────────────────────────┐     ┌─────────────────────┐
│   Instagram Graph   │     │         Backend (Node)      │     │   Agent (Python)    │
│   API / Webhooks    │─────│  - Tokens / Graph Calls     │─────│  - LLM Decisions    │
│   (Comments/DMs/...)│     │  - Proxy Endpoints          │     │  - Supabase Tools   │
└─────────────────────┘     │  - Webhook Receiver         │     │  - Schedulers       │
                            │  - Realtime Cache           │     └─────────────────────┘
                            └────────────┬────────────────┘               │
                                         │                                  │
                            ┌────────────┼────────────────┐               │
                            │ Supabase (Shared DB)         │               │
                            │ - audit_log (decisions)      │◄──────────────┘
                            │ - ugc_discovered (UGC)       │
                            │ - scheduled_posts (queue)    │
                            │ - attribution_events (ROI)   │
                            │ - oversight_conversations    │
                            └────────────┬────────────────┘
                                         │
                            ┌────────────┼────────────────┐
                            │   Frontend (React)            │
                            │  - Dashboard Pages           │
                            │  - Oversight Chat (SSE)      │
                            │  - Supabase Client (reads)   │
                            └──────────────────────────────┘
```

**Explanation of Flows:**  
- **Inbound Events:** IG webhooks → Backend (verify HMAC → store in Supabase + broadcast realtime). Subset (comments/mentions) → direct to Agent for decisions.  
- **Agent Actions:** Agent queries Supabase tools → decides (e.g., reply via backend proxy) → logs to audit_log.  
- **Dashboard Reads:** Frontend polls Supabase directly (historical) or subscribes realtime (live decisions/UGC).  
- **Oversight Chat Flow (SSE):** User question → Frontend POST /api/instagram/oversight/chat → Backend proxy → Agent (auto-context from audit_log) → LLM stream → Backend pipe SSE → Frontend tokens + sources.  
- **Security Boundaries:** Backend proxies all writes/actions; Agent reads only; Frontend reads only (RLS-protected).  

---

#### **Detailed Component Breakdown**

**1. Backend (Express/Node – Port 3001)**  
Role: IG token vault, Graph API executor, webhook sink, realtime broadcaster, agent proxy.  
Key Refactors (Completed: e7cdc77): Stripped N8N/Fixie; added 6 proxy endpoints.  

**Endpoints (All Verified – Live in Repo):**  
| Path | Method | Purpose | Body/Query | Response | Auth | Rate Limit |
|------|--------|---------|------------|----------|------|------------|
| /api/instagram/search-hashtag | POST | Proxy hashtag search for UGC | {business_account_id, hashtag} | {recent_media: [...] } | X-API-Key | Backend internal |
| /api/instagram/tags | GET | Proxy tagged posts for UGC | ?business_account_id | {tagged_posts: [...] } | X-API-Key | Backend internal |
| /api/instagram/send-dm | POST | Proxy DM send (e.g., UGC permission) | {business_account_id, username, message} | {success: true, id: ...} | X-API-Key | IG daily cap |
| /api/instagram/publish-post | POST | Proxy post publish (UGC scheduling) | {business_account_id, image_url, caption} | {id: media_id} | X-API-Key | IG daily cap |
| /api/instagram/insights | GET | Proxy account/media insights | ?business_account_id&metric_type=account\|media&since&until | {data: [...] } | X-API-Key | Backend internal |
| /api/instagram/oversight/chat | POST | SSE proxy for Oversight Brain | {question, business_account_id, stream: true/false, chat_history?} ?stream=true | SSE: data: {token: "..."} / {done: true, sources: [...] } | X-API-Key + Session | 20/min per X-User-ID |
| /webhook/instagram | POST | IG webhook receiver (all events) | Raw Meta payload | "EVENT_RECEIVED" | HMAC signature | None (Meta rate) |
| /realtime-updates | GET | Frontend poll for live events | ?since_timestamp | {events: [...], latest: ...} | Session | 1s debounce |
| /api/instagram/* (legacy) | Various | Frontend-facing (media, profile, sync) | Existing | Existing | Session/JWT | Existing |

**Internal Services:**  
- getGraphClient(business_account_id): Decrypts token from instagram_business_accounts → FB SDK client.  
- logApiRequest(obj): Audits all calls to api_usage + audit_log.  
- broadcastToFrontend(event): Pushes to Redis cache for /realtime-updates.  
- validateAgentApiKey: Middleware for all /api/instagram/* proxies.  

**2. Agent (FastAPI/Python – Port 3002 + Ollama)**  
Role: LLM-orchestrated brain – decisions, scheduling, oversight chat. No tokens, only Supabase reads + backend proxies.  
Key Refactors (Completed: 21d1ceb): Migrated all workflows (UGC, engagement, attribution); added Oversight Brain with streaming.  

**Routes & Schedulers:**  
| Path/Job | Method | Purpose | Tools/Prompt | Output |
|----------|--------|---------|--------------|--------|
| /analyze-comment | POST | Comment reply/ignore/delete | Supabase tools + Nemotron prompt | Backend proxy call + audit_log |
| /analyze-dm | POST | DM escalation/reply | Same | Same |
| /ugc/discovery | Scheduler (4–6h) | Hashtag/tag search → score → DM | Proxy tools (search-hashtag, tags, send-dm) + _score_ugc() | ugc_discovered insert |
| /engagement/monitor | Scheduler (5min) | Poll low-engagement posts | Insights proxy + reply tools | audit_log + proxy calls |
| /content/schedule | Scheduler (hourly) | Publish approved UGC | publish-post proxy | scheduled_posts update |
| /analytics/reports | Scheduler (daily) | LLM summaries + attribution | Insights proxy + attribution tools | analytics table insert |
| /oversight/chat | POST | Explainable Q&A over history | Read-only tools (audit_log, runs, posts) + oversight_brain prompt | SSE: tokens + {reply, sources, confidence, thinking_steps} |

**Core Components:**  
- **LangChain Agent:** create_react_agent(Nemotron-8B, tools) – handles tool calls, parsing, retries.  
- **Supabase Tools:** get_audit_log_entries(biz_id, limit), get_ugc_by_id, get_scheduled_posts(status) – async + Redis cache (45s TTL).  
- **Oversight Brain:** Dedicated ReAct agent with auto-context (last 12 audit_log) + JSON output (reply, sources[], confidence 0–1, thinking_steps[]). Streams via astream_chat().  
- **Prompts:** Versioned in Supabase prompt_templates – oversight_brain: "You are the Oversight Brain... Return ONLY JSON...".  
- **Schedulers:** APScheduler – ugc_discovery (semaphore per-account), engagement_monitor (webhook-triggered fallback).  
- **Observability:** /metrics (Prometheus), request_id tracing, audit_log for every decision.  

**3. Frontend (Vite/React/TS – Port 3000)**  
Role: Intuitive dashboard for monitoring + Oversight chat. Direct Supabase reads; backend for actions/chat.  
Key Refactor Plan (Phased, In Progress): Extend existing pages with agent data + SSE chat.  

**Pages & Components:**  
| Page | Layout | Data Source | Key Features |
|------|--------|-------------|--------------|
| /dashboard | KPIs cards | Supabase realtime (api_usage, attribution_events) | UGC discovered, posts published, revenue attributed, agent actions today |
| /ugc | DataTable + modals | Supabase ugc_discovered | Permission status, manual DM button, agent rejection reasons |
| /attribution | Review queue + charts | Supabase attribution_events | Breakdown by post/DM, ROI metrics, agent-tied revenue |
| /content-queue | Kanban/scheduler view | Supabase scheduled_posts | Pending/approved/rejected, publish button, agent notes |
| /analytics | Charts + reports | Supabase analytics + insights proxy | Daily/weekly trends, LLM summaries from agent |
| /audit | Searchable table | Supabase audit_log | Filter by event_type/confidence, export CSV |
| /oversight | Sidebar (recent decisions) + main chat | Supabase audit_log + SSE /oversight/chat | Suggested questions, sources sidebar, conversation history, confidence gauges |

**Data Hooks:**  
- useAgentData(biz_id): Queries audit_log, ugc_discovered, etc. + realtime subs (.on('postgres_changes')).  
- useOversightChat(biz_id): fetch POST to backend proxy + ReadableStream for SSE tokens/sources.  

**UI Patterns (shadcn):**  
- Tables: DataTable for recent decisions/sources.  
- Chat: Message bubbles (Avatar + ScrollArea), input (Input + Button), loading (Skeleton + dots).  
- Realtime: Toast on new audit_log ("Agent decided – ask why?").  

**4. Supabase Schema (Key Tables – RLS Enabled)**  
| Table | Columns | Purpose | RLS Policy |
|-------|---------|---------|------------|
| audit_log | id (uuid), created_at (ts), event_type (enum: reply/ignore/delete/ugc_discover/...), details (jsonb), business_account_id (uuid), confidence (float?), thinking_steps (text[]) | Every agent decision + reasoning | SELECT: user owns business_account_id; INSERT: service_role only |
| ugc_discovered | id, post_id (str), username, media_url, caption, score (float), status (pending/approved/rejected), business_account_id | UGC from hashtags/tags | Same as above |
| scheduled_posts | id, ugc_id (fk), status (pending/published/rejected), publish_at (ts), business_account_id | Agent-approved content queue | Same |
| attribution_events | id, post_id, order_id, revenue (float), agent_tied (bool), business_account_id | Revenue from agent actions | Same |
| oversight_conversations | id, user_id (str), business_account_id, messages (jsonb[]), created_at | Saved chat histories | SELECT/INSERT: user owns |
| api_usage | endpoint (str), calls (int), business_account_id | Rate/usage tracking | Service_role only |

**Realtime Subscriptions:** Frontend .channel('agent-changes').on('postgres_changes', { table: 'audit_log', event: 'INSERT' }, payload → toast/update table).  

---

#### **Implementation Phases Recap (From Conversation History – Locked In)**
1. **Backend Proxy Layer (Done):** 6 endpoints live; SSE for oversight/chat.  
2. **Agent Migration (Done):** All schedulers/tools proxy-first; Oversight Brain streaming + auto-context.  
3. **Dashboard Refactor (In Progress):** Phases 1–7 as sketched – Supabase reads → types → hooks → pages → chat UI → SSE wire → polish.  
4. **Optimizations (Future):** Redis for frontend caching, A/B prompts, voice input.  

**Testing & Rollout:**  
- Unit: Jest for backend routes, Vitest for frontend hooks.  
- E2E: Playwright for chat flow (question → tokens → sources click).  
- Load: 10 concurrent chats → <2s latency, no token leaks.  

This blueprint is now the canon – fork it for any expansions (e.g., multi-account support). System is 95% built; dashboard refactor unlocks full vision.  

**Commit to Repo:** Save as ARCHITECTURE.md in both repos (agent + dashboard). Questions? Let's iterate. 🚀




<