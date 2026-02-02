LangChain Agent for Instagram Automation
Overview
This repository contains the LangChain agent – the AI "brain" for the Instagram Automation Dashboard. It analyzes data from the shared Supabase database (e.g., comments, posts, insights), makes intelligent decisions (e.g., sentiment analysis, action recommendations), and triggers N8N workflows via webhooks. The agent runs locally on Ollama for privacy and cost-efficiency, hosted on Hetzner VPS with Docker.
Key Features

AI-driven analysis (e.g., "Analyze comment: positive → reply").
Integrates with Supabase DB as source of truth.
Triggers N8N for actions (e.g., DM replies).
HTTP endpoints for calls from backend/Edge Functions.
Dockerized for easy deployment.

Architecture
Text-Based Flowchart (see claude.md for details).
Setup

Clone repo.
Install deps: pip install -r requirements.txt.
Download model: ollama pull llama3.1:8b.
Set .env: SUPABASE_URL, SUPABASE_KEY, N8N_WEBHOOK.
Run: python agent.py.

Docker Deployment (Hetzner)

Build: docker build -t langchain-agent .
Run: Integrate into docker-compose.yml (see claude.md).

Testing

POST /analyze-comment: curl -X POST http://localhost:3002/analyze-comment -d '{"comment": "Great post!"}'
Expected: JSON with action/reason.

Contributing
Focus on agent.py for new analysis logic.
License
MIT.