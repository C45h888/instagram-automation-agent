Updated Context Dump for LangChain Agent Development
Version: 2.0 (February 2026)
Scope: This document is the single source of truth for the LangChain agent only. It reflects the current unified architecture: no N8N in production. All automation logic (reply to comment/DM, post scheduling, engagement monitoring) has been migrated into LangChain tools inside the agent. The agent is now the sole execution layer.
Core Principles

Agent Role: The agent is the central brain — it fetches context from Supabase, analyzes data, makes decisions, executes actions (via tools), and logs everything.
DB as Source of Truth: All reads/writes go through Supabase (instagram_media, instagram_business_accounts, audit_log, etc.).
Model: Nemotron-Orchestrator-8B Q5_K_M (optimized for tool calling, agentic workflows, reasoning, and structured outputs).
Hosting: Hetzner CX33 (4 vCPU, 8 GB RAM) – Dockerized, private, cost-effective.
Subdomains: app.888intelligenceautomation.in (frontend), api.888intelligenceautomation.in (backend), agent.888intelligenceautomation.in (LangChain agent).
No N8N in Production: N8N is kept locally only for prototyping. All execution is now inside the agent.
Scalability: Async Python, caching, concurrency control (semaphore), RAM target <7 GB total.

Current Architecture (No N8N)
text┌─────────────────────────────┐
│   User / Client Browser     │
│   (app.888intelligenceautomation.in) │
└─────────────────────────────┘
              │ HTTPS
              ▼
┌─────────────────────────────────────────────────────────────┐
│  Hetzner CX33 VPS - Docker Compose (3 Services)             │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ Frontend (React)     │  │ Backend (Node/Express)│        │
│  │ - UI/Dashboard       │  │ - API Endpoints       │        │
│  │ - Real-time Updates  │  │ - Token Management    │        │
│  │ - Analytics Display  │  │ - Data Sync           │        │
│  └──────────────────────┘  └──────────────────────┘        │
│                   │                 │                       │
│                   ▼                 ▼                       │
│              Common Supabase DB - Source of Truth          │
│              - instagram_media (posts/comments)            │
│              - instagram_business_accounts (IDs)           │
│              - api_usage (metrics)                         │
│              - audit_log (agent decisions/history)         │
│                   │                 │                       │
│                   ▼                 ▼                       │
│  ┌──────────────────────┐                                   │
│  │ LangChain Agent      │                                   │
│  │ agent.domain.in      │                                   │
│  │ - Nemotron-8B        │                                   │
│  │ - Supabase Tools     │                                   │
│  │ - Analysis + Decision│                                   │
│  │ - Direct Execution   │                                   │
│  │ - Logging            │                                   │
│  └──────────────────────┘                                   │
│                   │                                         │
│                   └─────────────→ Direct Actions           │
│                          (Instagram API calls via backend) │
└─────────────────────────────────────────────────────────────┘
Data Flow (Unified, No N8N):

Event (new comment, DM, low engagement) → Backend → Store in Supabase.
Backend/Edge Function → POST to agent /analyze-comment (or similar).
Agent → Queries Supabase tools for context.
Agent → Nemotron-Orchestrator analyzes (sentiment, brand alignment, risk).
Agent → Decides action (reply, ignore, delete, repost).
Agent → Executes directly (calls backend proxy for Instagram API).
Agent → Logs outcome to audit_log.
Frontend polls Supabase for real-time updates.

Key Components (Agent-Focused)
1. Supabase Tools (agent/tools/supabase_tools.py)

get_post_context(post_id)
get_account_context(business_account_id)
log_decision(event, user_id, data)
Async + caching (TTL) + retry (tenacity)
Pydantic validation

2. Agent Service (agent/services/agent_service.py)

Uses create_structured_chat_agent with tools
Handles tool calls, parsing, error propagation
Async support for non-blocking DB/LLM calls

3. Prompts (prompts/ folder)

Tool-aware, with few-shot examples
DB-backed (prompt_templates table) for versioning/A/B testing
System prompt defines role: "You are the Instagram oversight agent"

4. Routes (approve_comment.py, approve_dm.py, approve_post.py)

Use approve_base.py shared pipeline
Hard rules stay in routes (deterministic)
Agent handles context fetching + decision + execution + logging

5. Observability

Prometheus /metrics endpoint
Request ID tracing
Audit logging to Supabase

6. Deployment

Docker Compose (frontend, backend, agent + Ollama)
No N8N in production
RAM target: <7 GB total on CX33




Final Architecture Context Dump (Single Source of Truth)
Core Principle

Agent never holds IG tokens
Backend is the only place that holds IG tokens and makes Graph API calls
Frontend never depends on agent for live IG events
Agent receives only a subset of IG webhooks directly (comments, mentions, story mentions)
All other data comes via Supabase (read) or backend proxy (on-demand)

Data Flow Diagram
textMeta Instagram Graph API
        │
        │ Webhooks (ALL events: comments, mentions, story mentions, DMs, tags, etc.)
        ▼
Backend (port 3000/3001)
   ├── Verify HMAC signature
   ├── Store raw event in Supabase
   ├── Broadcast to frontend via /realtime-updates cache
   └── (Optional: forward specific events to agent via REST if needed in future)

Frontend (Dashboard)
   ├── Reads Supabase for all historical / processed data
   └── Polls /realtime-updates for live IG events (unchanged)

Agent (port 3002)
   ├── Receives direct IG webhooks ONLY for:
   │     - Comments
   │     - Mentions (captions/comments)
   │     - Story mentions
   ├── Reads Supabase directly for all other data (UGC, attributions, reports, audit_log, etc.)
   └── Calls backend proxy REST endpoints for data it cannot get otherwise:
         - search-hashtag
         - tags
         - send-dm
         - publish-post
         - insights
         - (any other Graph API data that requires token)

Execution Flow (Agent wants to act):
Agent → POST /api/instagram/send-dm (or publish-post, search-hashtag, etc.)
   ↓
Backend:
   - Validate X-API-Key
   - Lookup long-lived token
   - Call Graph API
   - logApiCall(...)
   - Return clean JSON only
   ↓
Agent:
   - Process response
   - Write outcome to Supabase
   - log_decision(...)
Locked Rules

Agent direct webhooks → only comments, mentions, story mentions
All other IG data → backend proxy or Supabase read
Frontend live events → backend /realtime-updates (unchanged)
Backend role → execution + proxy + webhook receiver + logging
Agent role → automation + decision making + summaries + Oversight Brain

What This Means for the Plan
The previous plan had one flaw: it assumed the agent would receive all IG webhooks directly.
That is now corrected.
The backend proxy endpoints we planned are still exactly correct:

search-hashtag
tags
send-dm
publish-post
insights

These are the calls the agent must make to the backend because it cannot get that data via webhook or Supabase.

