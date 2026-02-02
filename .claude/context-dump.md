# LangChain Agent Context Dump: Comprehensive Project Guide for Development

**Document Version:** 1.0  
**Date Created:** February 01, 2026  
**Purpose:** This is a detailed, self-contained context dump for developing the LangChain agent as the "oversight brain" for the Instagram Automation Dashboard's N8N workflows. It encapsulates the entire project scope, architecture, data flows, decisions, recent fixes, and implementation details from the conversation history. Use this as the primary reference for agent development – focus on the agent's role, integration with Supabase DB (source of truth), and triggering N8N. The full dashboard (frontend/backend) is already built; the agent extends it with AI intelligence. This document is intentionally long and in-depth for complete clarity.

**Key Principles for Agent Development:**
- **Bounds:** Agent handles analysis, decision-making, and triggering only. No direct modifications to frontend, backend, or N8N unless for integration (e.g., new endpoints).
- **DB as Source of Truth:** All data reads/writes go through Supabase – agent queries tables like `instagram_media` for comments/posts, `instagram_business_accounts` for IDs, `audit_log` for history.
- **Privacy & Local Focus:** Use local Ollama models on Hetzner VPS – no external AI APIs unless specified.
- **Scalability:** Agent designed for high volume (async Python, bounded resources).
- **Testing:** Unit for analysis logic; E2E for DB trigger → agent → N8N.

---

## Project Overview

### Background
The Instagram Automation Dashboard is a full-stack web app for managing Instagram accounts, syncing data (posts, comments, insights), and automating workflows (e.g., DM replies, content posting). It started with mock data and basic OAuth, evolved through fixes for schema mismatches, token validation, and real data wiring, and is now production-ready on Hetzner VPS with Docker.

- **Core Goals:** Pull real Instagram data, display in dashboard (analytics, UGC page), automate via N8N, with AI oversight from the LangChain agent.
- **Current State:** Frontend (React/Vite) + Backend (Node/Express) work; real data flows (post Phase 1–7 fixes); N8N integrated via webhooks.
- **Shift from Render:** Moved from managed hosting (Render) to self-managed Hetzner VPS for cost/control (e.g., run AI locally).
- **LangChain Agent Role:** The "brain" – analyzes DB data (e.g., new comment sentiment), decides actions (reply/ignore), triggers N8N. Starts simple, scales to complex (e.g., campaign suggestions).

### Decisions Made
- **AI Model:** Local Ollama (Llama 3.1 8B base, scalable to 70B) for privacy, zero costs, and VPS compatibility.
- **Language:** Python for agent (efficient for AI, Flask for endpoints).
- **Hosting:** Hetzner CX43/CAX31 (€9.99–€13/month, 8 vCPU/16GB RAM) – Dockerized, private.
- **Integration:** DB events/backend webhooks trigger agent; agent POSTs to N8N webhooks.
- **Subdomains:** app (frontend), api (backend), agent (LangChain), n8n (workflows).
- **Data Pool:** Supabase as central source – all services read/write here (e.g., agent logs to `audit_log`).
- **Scope:** Agent for analysis/oversight only – N8N executes; no direct Instagram API from agent.

---

## Planned System Architecture

The system runs on Hetzner VPS with Docker Compose (4 services: frontend, backend, agent, N8N). Supabase is external (hosted) as the shared DB. Data flows: Events → DB → Agent analysis → N8N action.

**Text-Based Flowchart Diagram:**
```
┌─────────────────────────────┐
│   User / Client Browser     │
│   (app.888intelligenceautomation.in) │
└─────────────────────────────┘
              │
              ▼ HTTPS
┌─────────────────────────────────────────────────────────────┐
│  Hetzner VPS (CX43/CAX31) - Docker Compose                  │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ Frontend (React SPA) │  │ Backend (Node/Express) │        │
│  │ - UI/Dashboard       │  │ - API Endpoints       │        │
│  │ - Real-time Updates  │  │ - Token Management    │        │
│  │ - Analytics Display  │  │ - Data Sync (Instagram)│        │
│  └──────────────────────┘  └──────────────────────┘        │
│                   │                 │                       │
│                   ▼                 ▼                       │
│              Common Supabase DB - Source of Truth          │
│              - instagram_media (posts/comments)            │
│              - instagram_business_accounts (IDs/credentials)│
│              - api_usage (logging/metrics)                 │
│              - audit_log (agent decisions/history)         │
│                   │                 │                       │
│                   ▼                 ▼                       │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ LangChain Agent      │  │ N8N Workflows         │        │
│  │ agent.domain.in      │  │ n8n.domain.in          │        │
│  │ - Ollama AI Model    │  │ - Automation Triggers │        │
│  │ - Data Analysis      │  │ - DM Replies          │        │
│  │ - Decision Making    │  │ - Content Posting     │        │
│  │ - Oversight Logic    │  │ - Notifications       │        │
│  └──────────────────────┘  └──────────────────────┘        │
│                   ▲                 │                       │
│                   └─────────────────▼                       │
│                      Webhooks / API Endpoints               │
│                     (Agent triggers N8N actions)            │
└─────────────────────────────────────────────────────────────┘
```

**How the System Works (Data Flow):**
1. **User Action/Data Event:** User logs in (OAuth) or new Instagram data syncs (e.g., new comment via webhook to backend).
2. **Backend Processing:** Validates token, stores in Supabase (e.g., instagram_media table).
3. **DB as Source of Truth:** All data lands here – agent queries it for analysis (e.g., SELECT from instagram_media for comments).
4. **Agent Trigger:** Backend or Edge Function calls agent's endpoint (e.g., POST /analyze-comment with data from DB).
5. **Agent Brain:** Ollama + LangChain analyzes (e.g., "Comment sentiment: positive – suggest reply 'Thanks!'").
6. **Decision & Trigger:** Agent POSTs to N8N webhook if action needed (e.g., "reply" → N8N_DM_WEBHOOK with text).
7. **N8N Execution:** Performs the action (e.g., send DM via Instagram API).
8. **Logging/Feedback:** Agent logs decision to audit_log; frontend polls DB for updates (real-time via realtimeService.ts).

**Key Benefits:** Private (local AI on VPS), scalable (Docker), intelligent (AI decisions over rigid N8N rules).

---

## Components Breakdown

### 1. Frontend (React/Vite – app.domain.in)
- Role: UI for login, dashboard, analytics, UGC (User-Generated Content).
- Key Files: src/pages (Dashboard.tsx, Analytics.tsx), src/hooks (useInstagramAccount.ts, useTokenValidation.ts), src/services (realtimeService.ts, tokenRefreshService.ts), src/stores (authStore.ts).
- Integration with Agent: Calls backend endpoints that trigger agent (e.g., on new data sync).
- Status: Working with real data (post recent fixes).

### 2. Backend (Node/Express – api.domain.in)
- Role: Handles API calls, token exchange/validation, Instagram data sync, webhooks.
- Key Files: backend.api/routes (instagram-api.js for validation, webhook.js), backend.api/services (instagram-sync.js, instagram-tokens.js), backend.api/config (supabase.js for DB).
- Integration with Agent: On events (e.g., new comment), POST to agent /analyze → get decision → trigger N8N.
- Status: Stable post-fixes (no 500s).

### 3. Supabase DB (Hosted – External)
- Role: Source of truth – all services read/write here.
- Key Tables: instagram_business_accounts (IDs/credentials), instagram_media (posts/comments), api_usage (logging), audit_log (agent decisions/history).
- Integration: Agent uses Supabase client to query (e.g., new comments), write logs.
- Status: Schema fixed; real-time subscriptions for events.

### 4. LangChain Agent (Python/Flask/Ollama – agent.domain.in)
- Role: AI brain – analyzes DB data, decides actions, triggers N8N.
- Key Files: agent/agent.py (main logic), agent/Dockerfile, agent/requirements.txt.
- Capabilities: Sentiment analysis, action decisions (reply/ignore/delete), custom prompts.
- Integration: HTTP endpoints (e.g., /analyze-comment); reads DB for context; POSTs to N8N.
- Status: To be built – start with basic analysis, expand to complex.

### 5. N8N Workflows (n8n.domain.in)
- Role: Executes actions (DM replies, posting, notifications).
- Key: Triggered by agent via webhooks.
- Integration: Receives JSON from agent (e.g., { action: "reply", text: "Thanks!" }).
- Status: Existing – keep for MVP, migrate to Python later.

### 6. Deployment (Hetzner VPS with Docker Compose)
- Hardware: CX43/CAX31 (8 vCPU, 16GB RAM, €9.99–€13/month).
- Services: Frontend, Backend, Agent, N8N in containers.
- Networks: Bridge for internal comms.
- Subdomains: Via DNS A records + Nginx proxy.

---

## Data Flows & Integrations

1. **New Data Event Flow:**
   - Instagram webhook → Backend → Store in Supabase (instagram_media).
   - Backend/Edge Function → POST to agent /analyze with data ID.
   - Agent → Query Supabase for context → Ollama analysis → Decision.
   - Agent → POST to N8N webhook if action needed.
   - N8N → Execute (e.g., reply via Instagram API).
   - Agent → Log to audit_log.

2. **Agent Decision Examples:**
   - Input: Comment "Great post!" → Output: { action: "reply", reply_text: "Thanks!" } → N8N sends DM.
   - Input: Low engagement post → Output: { action: "repost", suggestion: "Better caption" } → N8N schedules.

3. **DB as Source of Truth:**
   - All reads: Agent queries for latest data (no stale caches).
   - All writes: Agent logs decisions/audits – backend/frontend read them for UI.

---

## Recent Fixes & Changes
- OAuth/Schema Mismatches: Fixed column names, cache issues (commits like 0566911c).
- Token Validation: Updated queries/decryption (500 errors resolved).
- Real Data Wiring: Hooks now pull from Instagram API (Jan 6 commit).
- UI Polish: Modals, null guards for crashes.
- Deployment Prep: Dockerfiles, compose, nginx.conf for Hetzner.

---

## Future Plans & Scalability
- **MVP:** Use N8N for actions; agent for decisions.
- **Scale:** Migrate N8N flows to Python in agent (faster, no external service).
- **Enhancements:** Bigger Ollama models (70B on 16GB RAM), multi-agent (e.g., separate for sentiment/content).
- **Monitoring:** Add Prometheus/Docker logs to Supabase or external.

This dump provides all needed context – use it to guide agent development. Focus on building `agent.py` capabilities first.