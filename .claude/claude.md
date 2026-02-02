Context for LangChain Agent Development
Project Overview
This document provides focused context for developing the LangChain agent as the "oversight brain" for Instagram automation workflows. The agent will analyze data from the shared Supabase database (source of truth), make intelligent decisions (e.g., sentiment analysis, action recommendations), and trigger N8N automations via webhooks or endpoints. The full Instagram dashboard (frontend/backend) is already built and working; this agent extends it by adding AI-driven intelligence. Development bounds: Focus solely on the agent's capabilities, integration with DB/N8N, and Docker deployment on Hetzner VPS. Do not modify the existing IG dashboard unless explicitly needed for agent integration.
Decisions Made

AI Model: Local Ollama (Llama 3.1 8B initially, scalable to 70B) for privacy, zero API costs, and full control. No external APIs like OpenAI unless needed for advanced features.
Language/Framework: Python for the agent (simple, efficient for AI), with Flask for HTTP endpoints (webhooks from backend/Edge Functions).
Hosting: Hetzner CX43/CAX31 VPS (8 vCPU, 16 GB RAM, €9.99–€13/month) – Dockerized for easy scaling. Subdomain: agent.888intelligenceautomation.in.
Integration:
DB: Supabase as common data pool – agent reads/writes to tables like instagram_media, instagram_business_accounts, audit_log.
Triggers: From backend (webhooks on new data) or Supabase Edge Functions (DB events, e.g., new comment insert).
Outputs: Agent decides actions → triggers N8N webhooks (e.g., if "reply", POST to N8N_DM_WEBHOOK).

Scope Bounds: Agent handles analysis/decision-making only (e.g., "analyze comment → suggest reply"). N8N executes actions. No direct Instagram API calls from agent – use backend proxies.
Security/Privacy: All on private VPS; no cloud AI – data stays local.

Planned Architecture
The agent runs as a Docker service on Hetzner, connected to the shared Supabase DB. It receives inputs via HTTP from the backend/Edge Functions, processes with LangChain/Ollama, and outputs decisions to N8N.
Text-Based Flowchart:
text┌─────────────────────────────┐
│   User / Frontend Dashboard │
└─────────────────────────────┘
              │
              ▼ (New Data Event)
┌─────────────────────────────────────────────────────────────┐
│  Hetzner VPS (CX43/CAX31) - Docker Compose                  │
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ Backend API          │  │ Supabase Edge Funcs  │        │
│  │ api.domain.in        │  │ (Light Triggers)     │        │
│  │ - Detect New Comment │  │ - DB Insert Event    │        │
│  └──────────────────────┘  └──────────────────────┘        │
│                   │                 │                       │
│                   ▼                 ▼                       │
│              Common Supabase DB - Source of Truth          │
│              - instagram_media (posts/comments)            │
│              - instagram_business_accounts (IDs)           │
│              - audit_log (decisions/history)               │
│                   │                 │                       │
│                   ▼                 ▼                       │
│  ┌──────────────────────┐                                   │
│  │ LangChain Agent      │                                   │
│  │ agent.domain.in      │                                   │
│  │ - Ollama AI Model    │                                   │
│  │ - Analyze Data       │                                   │
│  │ - Decide Action      │                                   │
│  └──────────────────────┘                                   │
│                   │                                         │
│                   ▼ (Decision Made)                         │
│  ┌──────────────────────┐                                   │
│  │ N8N Workflows        │                                   │
│  │ n8n.domain.in         │                                   │
│  │ - Execute Action      │                                   │
│  │ - e.g., Send DM       │                                   │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
Development Guidelines for Claude (the Agent):

Bounds: Focus on agent code in /agent folder (agent.py, Dockerfile, etc.). Do not touch frontend/backend unless for integration points (e.g., new endpoints).
DB as Source of Truth: All decisions based on Supabase queries – agent reads real-time data (e.g., new comments from instagram_media), analyzes, logs to audit_log, then triggers.
Scalability: Use async Python for high volume; Ollama on CPU (8 vCPU handles ~10–20 concurrent analyses).
Testing: Unit tests for analysis logic; E2E: DB insert → agent call → N8N trigger.
Future-Proof: Start with 8B model; easy swap to 70B