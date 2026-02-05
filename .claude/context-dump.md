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