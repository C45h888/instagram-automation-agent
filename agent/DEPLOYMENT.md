# LangChain Oversight Brain Agent - Deployment Guide

## 🎯 Project Overview

The LangChain Oversight Brain Agent is a production-ready AI approval authority that sits between N8N workflows and Instagram actions. It analyzes proposed content (DM replies, comment replies, posts) using NVIDIA Nemotron 4 8B via Ollama, applies business rules, and returns approve/reject/modify decisions with full audit logging to Supabase.

**Model:** NVIDIA Nemotron 4 8B Q5_K_M (superior agentic performance, +2-5% in benchmarks)
**Endpoints:** 4 endpoints (`/health`, `/approve/comment-reply`, `/approve/dm-reply`, `/approve/post`)
**Security:** API key authentication on all approval endpoints
**Async:** gunicorn + gevent workers for 20+ concurrent requests

---

## 📁 Files Created/Modified

### Phase 1: Infrastructure (7 files)
- ✅ **agent/docker-compose.yml** - Fixed malformed YAML, added separate ollama service with healthcheck
- ✅ **agent/dockerfile** - Removed Ollama installation, use gunicorn + gevent
- ✅ **agent/requirements.txt** - Added gunicorn, gevent, pydantic dependencies
- ✅ **agent/startup.sh** - Script to pull Nemotron model with retry logic
- ✅ **agent/.env.example** - Documents all required environment variables

### Phase 2: Core Agent (10 files)
- ✅ **agent/config.py** - Centralized config with Supabase client, Ollama LLM, constants
- ✅ **agent/prompts.py** - All 3 prompt templates (comment, dm, post) in single dict
- ✅ **agent/services/validation.py** - Pydantic models + API key auth middleware
- ✅ **agent/services/supabase_service.py** - Context fetching + audit logging
- ✅ **agent/services/llm_service.py** - Safe JSON parsing (json.loads, never eval)
- ✅ **agent/routes/health.py** - Enhanced health check (DB + Ollama status)
- ✅ **agent/routes/approve_comment.py** - Comment reply approval endpoint
- ✅ **agent/routes/approve_dm.py** - DM reply approval with escalation logic
- ✅ **agent/routes/approve_post.py** - Post approval with hard rules
- ✅ **agent/agent.py** - Flask app entry point with blueprint registration

### Phase 3: N8N Integration (4 files)
- ✅ **agent/N8N-workflows/AGENT-INTEGRATION-GUIDE.md** - Detailed integration instructions
- ✅ **agent/N8N-workflows/customer-service.json** - Modified with agent approval nodes
- ✅ **agent/N8N-workflows/content-scheduling.json** - Modified with agent approval nodes
- ✅ **agent/N8N-workflows/engangement-monitor.json** - Modified with agent approval nodes

**Total: 21 files created/modified**

---

## 🚀 Deployment Instructions

### Prerequisites
1. Hetzner VPS (CX43/CAX31: 8 vCPU, 16 GB RAM, €9.99–€13/month)
2. Docker & Docker Compose installed
3. Supabase project with required tables
4. N8N instance running

### Step 1: Clone and Setup

```bash
# SSH into VPS
ssh root@agent.888intelligenceautomation.in

# Clone the repository
cd /opt
git clone https://github.com/YOUR_ORG/instagram-automation-agent.git
cd instagram-automation-agent/agent
```

### Step 2: Configure Environment Variables

Create `.env.production` file:

```bash
cp .env.example .env.production
nano .env.production
```

Required variables:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key-here

# Ollama Configuration
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=nemotron:8b-q5_K_M

# Security
AGENT_API_KEY=your-secret-api-key-here  # Generate with: openssl rand -hex 32

# Flask Configuration
FLASK_PORT=3002
FLASK_ENV=production

# Optional: Performance Tuning
MAX_CAPTION_LENGTH=2200
MAX_HASHTAG_COUNT=10
VIP_LIFETIME_VALUE_THRESHOLD=500.0
COMMENT_APPROVAL_THRESHOLD=0.75
DM_APPROVAL_THRESHOLD=0.75
POST_APPROVAL_THRESHOLD=0.72
```

### Step 3: Configure N8N

Add to N8N's `.env.production`:

```bash
AGENT_API_KEY=your-secret-api-key-here  # Must match agent's key
```

### Step 4: Build and Start Services

```bash
# Build the agent and ollama containers
docker compose build langchain-agent ollama

# Start ollama first (downloads model ~5GB)
docker compose up -d ollama

# Wait for model pull (check logs)
docker logs -f ollama

# Once model is ready, start the agent
docker compose up -d langchain-agent

# Verify all services running
docker ps
```

### Step 5: Import N8N Workflows

1. Open N8N UI (`https://n8n.888intelligenceautomation.in`)
2. Go to Workflows → Import from File
3. Import the modified JSON files:
   - `agent/N8N-workflows/customer-service.json`
   - `agent/N8N-workflows/content-scheduling.json`
   - `agent/N8N-workflows/engangement-monitor.json`
4. Activate each workflow

---

## 🧪 Testing

### 1. Health Check

```bash
curl http://langchain-agent:3002/health
```

Expected response:
```json
{
  "status": "healthy",
  "model": "nemotron:8b-q5_K_M",
  "model_loaded": true,
  "db_connection": true,
  "uptime": 123.45,
  "requests_processed": 0,
  "avg_response_time_ms": 0
}
```

### 2. Test Comment Approval

```bash
curl -X POST http://langchain-agent:3002/approve/comment-reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "comment_id": "test_1",
    "comment_text": "Love this! Where can I buy it?",
    "post_id": "post_1",
    "business_account_id": "acc_1",
    "proposed_reply": "Thanks! Check our website at [link] 💕",
    "detected_intent": "praise",
    "sentiment": "positive",
    "confidence": 0.9
  }'
```

Expected response:
```json
{
  "approved": true,
  "modifications": null,
  "quality_score": 8.5,
  "decision_reasoning": "Appropriate, friendly tone, includes CTA",
  "audit_data": {
    "analyzed_at": "2026-02-02T23:30:00Z",
    "agent_model": "nemotron:8b-q5_K_M",
    "latency_ms": 1200
  }
}
```

### 3. Test DM Approval (with Escalation)

```bash
curl -X POST http://langchain-agent:3002/approve/dm-reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "message_id": "dm_1",
    "dm_text": "This product broke after 2 days! I want a refund NOW!",
    "sender_username": "angry_customer",
    "sender_id": "u1",
    "business_account_id": "acc_1",
    "proposed_reply": "Sorry to hear that! Please email support@...",
    "detected_intent": "complaint",
    "sentiment": "negative",
    "within_24h_window": true,
    "priority": "urgent",
    "customer_history": {
      "previous_interactions": 3,
      "sentiment_history": "negative",
      "lifetime_value": 150
    }
  }'
```

Expected response (escalated):
```json
{
  "approved": false,
  "modifications": null,
  "needs_escalation": true,
  "escalation_reason": "Negative sentiment with complaint intent - requires human support",
  "suggested_team": "support",
  "decision_reasoning": "Negative sentiment with complaint intent - requires human support"
}
```

### 4. Test Post Approval (with Hard Rule Rejection)

```bash
curl -X POST http://langchain-agent:3002/approve/post \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "scheduled_post_id": "draft_1",
    "asset": {
      "public_id": "img_1",
      "image_url": "https://example.com/img.jpg",
      "width": 1080,
      "height": 1080,
      "tags": ["product", "sale"]
    },
    "proposed_caption": "Check out our new collection!",
    "business_account_id": "acc_1",
    "hashtags": ["Fashion", "Style", "OOTD", "Sustainable", "SlowFashion", "EthicalStyle", "Summer", "Sale", "NewCollection", "BrandName", "ExtraTag"],
    "hashtag_count": 11,
    "caption_length": 30,
    "engagement_prediction": 0.04,
    "post_type": "product",
    "scheduled_time": "2026-02-03T14:00:00Z"
  }'
```

Expected response (rejected due to hard rule):
```json
{
  "approved": false,
  "modifications": null,
  "quality_score": 0,
  "decision_reasoning": "Hard rule violation: Too many hashtags (11, max 10)",
  "issues": ["Too many hashtags (11, max 10)"],
  "recommendations": ["Reduce hashtags to 8-9 relevant tags"],
  "audit_data": {
    "analyzed_at": "2026-02-02T23:35:00Z",
    "agent_model": "nemotron:8b-q5_K_M",
    "rule_triggered": "hard_rule_violation"
  }
}
```

### 5. Test N8N End-to-End

1. **Customer Service Workflow**:
   - Manually trigger webhook with test DM
   - Check N8N execution log for agent approval step
   - Verify Supabase `audit_log` has decision entry

2. **Content Scheduling Workflow**:
   - Manually trigger workflow
   - Check agent approves/modifies caption
   - Verify post publishes with agent-approved content

3. **Engagement Monitor Workflow**:
   - Wait for scheduled trigger (5 min)
   - Check agent reviews comment replies
   - Verify only approved replies are posted

---

## 📊 Monitoring

### Check Agent Logs

```bash
# View real-time logs
docker logs -f langchain-agent

# View Ollama logs
docker logs -f ollama

# Check all container status
docker compose ps
```

### Key Metrics to Monitor

1. **Response Time**: Target < 5s per approval request
2. **Approval Rate**: Track in Supabase `audit_log`
3. **Escalation Rate**: Monitor `needs_escalation` = true entries
4. **Error Rate**: Watch for 503 (Ollama down) or 500 errors

### Supabase Audit Queries

```sql
-- Total decisions today
SELECT COUNT(*) FROM audit_log
WHERE event_type LIKE '%_approval'
AND created_at >= CURRENT_DATE;

-- Approval breakdown
SELECT
  event_type,
  action,
  COUNT(*) as count
FROM audit_log
WHERE event_type LIKE '%_approval'
GROUP BY event_type, action;

-- Average agent latency
SELECT
  event_type,
  AVG((details->>'latency_ms')::numeric) as avg_latency_ms
FROM audit_log
WHERE event_type LIKE '%_approval'
AND details ? 'latency_ms'
GROUP BY event_type;
```

---

## 🛡️ Security

1. **API Key**: Rotate `AGENT_API_KEY` quarterly
2. **Supabase Service Key**: Use service role key (full access needed for audit logs)
3. **Network**: Agent runs on Docker internal network, only N8N can reach it
4. **Rate Limiting**: Implement in N8N (max 60 requests/min per workflow)

---

## 🔧 Troubleshooting

### Issue: Agent returns 503 "model_unavailable"

**Cause**: Ollama service down or model not loaded

**Fix**:
```bash
docker compose restart ollama
docker logs -f ollama  # Wait for "Llama server listening..."
docker compose restart langchain-agent
```

### Issue: Agent returns 401 "unauthorized"

**Cause**: API key mismatch

**Fix**:
1. Check agent's `.env.production` has `AGENT_API_KEY`
2. Check N8N's `.env.production` has matching key
3. Verify N8N HTTP Request node uses `X-API-Key` header with `={{ $env.AGENT_API_KEY }}`

### Issue: Supabase connection errors

**Cause**: Invalid credentials or network issue

**Fix**:
```bash
# Test Supabase connection
curl https://your-project.supabase.co/rest/v1/ \
  -H "apikey: your-service-key" \
  -H "Authorization: Bearer your-service-key"

# Check agent environment
docker exec langchain-agent env | grep SUPABASE
```

### Issue: Agent slow (> 10s per request)

**Cause**: High concurrent load or under-resourced VPS

**Fix**:
1. Check CPU/RAM usage: `docker stats`
2. Increase gunicorn workers in `Dockerfile` CMD (default: 4)
3. Consider upgrading VPS (CX43 → CX53 for 16 vCPU)

---

## 📈 Performance Optimization

### Current Configuration
- **Workers**: 4 gevent workers (1 per 2 vCPU)
- **Model**: Nemotron 4 8B Q5_K_M (~5GB RAM, ~1-3s inference)
- **Timeout**: 10s per LLM call, 15s total per HTTP request
- **Expected Throughput**: 20+ concurrent approvals

### Scaling Options

**Horizontal Scaling** (if load exceeds 100 req/min):
1. Add load balancer (nginx)
2. Run 2+ agent containers
3. Share Ollama service (or run 1 Ollama per agent)

**Vertical Scaling** (if single requests are slow):
1. Upgrade to CX53 (16 vCPU, 32GB RAM)
2. Use Nemotron Q8 (higher quality, +500ms latency)
3. Increase gunicorn workers to 8

---

## 🎯 Next Steps

1. **Monitor for 1 week**: Track approval rates, latency, errors
2. **Tune prompts**: Adjust `prompts.py` based on rejection patterns
3. **Refine thresholds**: Update `config.py` constants if too strict/lenient
4. **Add advanced features**:
   - Multi-step analysis (sentiment → simulate impact → decide)
   - Competitor benchmarking integration
   - A/B test suggested modifications
5. **Scale**: Add more N8N workflows for Stories, Reels approval

---

## 📝 Change Log

### 2026-02-02 - v1.0 Initial Deployment
- ✅ All 21 files created/modified
- ✅ 3 N8N workflows integrated with agent approval
- ✅ Production-ready with Docker Compose
- ✅ Full audit logging to Supabase
- ✅ Hard business rules implemented (VIP escalation, 24h window, hashtag limits)

---

## 🙏 Support

- **Issues**: Check [agent/README.md](README.md) for architecture details
- **Integration Guide**: See [agent/N8N-workflows/AGENT-INTEGRATION-GUIDE.md](N8N-workflows/AGENT-INTEGRATION-GUIDE.md)
- **Agent Context**: See [AGENT-CONTEXT.md](AGENT-CONTEXT.md) for decision framework

**Status**: ✅ Ready for Production Deployment
