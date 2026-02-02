# LangChain Oversight Brain Agent - Comprehensive Integration Context

**Document Version:** 2.0
**Date:** February 2, 2026
**Purpose:** Unified context for developing the LangChain agent as the central oversight brain for N8N automations and Instagram automation system.

---

## Executive Summary

The LangChain oversight brain agent is the **central decision-making authority** for the Instagram automation system. It sits between N8N workflow proposals and execution, analyzing suggestions and either approving or rejecting them with modifications.

### Agent Role
- **Receive**: N8N sends proposed actions (comment replies, DM replies, posts) to agent webhooks
- **Analyze**: Agent uses Ollama + LangChain to evaluate proposals against context (post data, account type, engagement metrics, sentiment)
- **Decide**: Agent approves/rejects/modifies with executive authority
- **Return**: Agent responds to N8N with decision + modifications
- **Log**: Agent logs all decisions to Supabase audit_log for oversight

### Three Core Approval Flows

1. **Comment Reply Approval** - Agent reviews proposed comment responses
2. **DM Reply Approval** - Agent reviews proposed direct message responses
3. **Post Approval** - Agent reviews proposed post captions and content

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         INSTAGRAM META SERVERS                  │
│                  (Comments, DMs, Engagement Events)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
          ┌──────────────────────────────────┐
          │   Backend (Express.js API)       │
          │   api.888intelligenceautomation  │
          │   Webhook Verification (HMAC)    │
          │   Token Management               │
          └──────────────────┬───────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          │                                     │
          ▼                                     ▼
   ┌─────────────────┐              ┌────────────────────┐
   │  SUPABASE DB    │              │  N8N WORKFLOWS     │
   │  (Source of     │              │  (Automation       │
   │   Truth)        │              │   Executors)       │
   │                 │              │                    │
   │ - Comments      │              │ - Comment Router   │
   │ - DMs           │              │ - DM Service       │
   │ - Posts         │              │ - Content Schedule │
   │ - Account Info  │              │ - Analytics        │
   │ - Audit Log     │              └────────┬───────────┘
   └────────┬────────┘                       │
            │                                │
            │        ┌──────────────────────┘
            │        │
            ▼        ▼
   ┌──────────────────────────────────────────────────────────┐
   │   LANGCHAIN OVERSIGHT BRAIN AGENT (Python/Flask/Ollama)  │
   │   agent.888intelligenceautomation (Port 3002)            │
   │                                                          │
   │   Endpoints:                                             │
   │   - POST /approve/comment-reply   (N8N triggers)         │
   │   - POST /approve/dm-reply        (N8N triggers)         │
   │   - POST /approve/post            (N8N triggers)         │
   │   - GET  /health                  (Status check)         │
   │                                                          │
   │   Capabilities:                                          │
   │   - Sentiment analysis (comment/reply)                   │
   │   - Tone/brand alignment checking                        │
   │   - Caption quality scoring                              │
   │   - Context-aware decision making                        │
   │   - Smart modifications (refine replies, improve         │
   │     captions)                                            │
   │   - Comprehensive audit logging                          │
   └──────┬───────────────────────────────────────────────────┘
          │
          │  Approvals + Modifications
          │
          ▼
   ┌──────────────────────────────────────────┐
   │  N8N Execution Decision                  │
   │  - Execute if approved                   │
   │  - Skip if rejected                      │
   │  - Use modified data if updated by agent │
   └──────────────────────────────────────────┘
```

---

## N8N to Agent Data Flow

### Comment Reply Workflow

**N8N → Agent Flow:**

```
1. Comment arrives on Instagram post
   ↓ (Meta webhook)

2. Backend receives webhook → validates signature → forwards to N8N
   ↓

3. N8N Comment Router workflow:
   - Classifies message (intent: sizing, shipping, complaint, etc.)
   - Generates template-based response
   - Prepares approval payload
   ↓

4. N8N POSTs to Agent: /approve/comment-reply

   Payload:
   {
     "comment_id": "meta_comment_id",
     "comment_text": "How do you ship to Canada?",
     "commenter_username": "customer_handle",
     "post_id": "post_456",
     "business_account_id": "account_uuid",
     "proposed_reply": "Thanks for asking! We ship to Canada with tracking.",
     "detected_intent": "shipping",
     "confidence": 0.92,
     "sentiment": "neutral"
   }
   ↓

5. Agent Analysis:
   - Fetches context: post caption, account type, engagement metrics
   - Analyzes proposed reply against brand voice
   - Checks sentiment/tone alignment
   - Evaluates if reply is relevant to comment
   ↓

6. Agent Response:

   {
     "approved": true,
     "modifications": {
       "reply_text": "Thanks for asking! We ship worldwide 🌍 with free tracking. DM us for Canada rates!"
     },
     "decision_reasoning": "Reply is relevant and improves engagement with emoji + CTA",
     "confidence": 0.88,
     "sentiment": "positive",
     "brand_alignment_score": 0.91,
     "audit_data": {
       "analyzed_at": "2025-02-02T10:45:32Z",
       "agent_model": "llama3.1:8b",
       "analysis_factors": ["sentiment", "tone", "relevance", "brand_voice"]
     }
   }
   ↓

7. N8N executes (approved) or skips (rejected)

8. Agent logs to audit_log:
   {
     "event": "comment_reply_approval",
     "status": "approved",
     "proposed_reply": "...",
     "approved_reply": "...",
     "decision_factors": {...}
   }
```

### DM Reply Workflow

**N8N → Agent Flow:**

```
1. DM received from customer
   ↓

2. N8N DM Service workflow:
   - Checks 24-hour messaging window
   - Classifies message (intent, priority)
   - Detects sentiment (positive/negative/neutral)
   - Generates response from templates
   ↓

3. N8N POSTs to Agent: /approve/dm-reply

   Payload:
   {
     "message_id": "dm_123",
     "dm_text": "Hi! I need to change my order size",
     "sender_username": "customer_ig",
     "sender_id": "user_456",
     "business_account_id": "account_uuid",
     "proposed_reply": "No problem! Contact our support team.",
     "detected_intent": "order_modification",
     "sentiment": "neutral",
     "within_24h_window": true,
     "priority": "high",
     "customer_history": {
       "previous_interactions": 3,
       "sentiment_history": "positive",
       "lifetime_value": 250.00
     }
   }
   ↓

4. Agent Analysis:
   - Evaluates if reply is appropriate for customer (check history/VIP status)
   - Analyzes response tone for DM context (more casual than comments)
   - Checks if reply handles the actual request
   - Determines if escalation to human is needed
   ↓

5. Agent Response:

   {
     "approved": true,
     "modifications": {
       "reply_text": "No problem! I can help you change the size 😊 What size would you like instead?"
     },
     "decision_reasoning": "Customer has positive history. Improvement: more personal tone, asks clarifying question",
     "confidence": 0.89,
     "sentiment_match": "positive",
     "needs_escalation": false,
     "audit_data": {...}
   }
   OR
   {
     "approved": false,
     "modifications": null,
     "decision_reasoning": "Complex order issue detected. Recommend human agent to discuss all options.",
     "needs_escalation": true,
     "escalation_reason": "Potential refund/return case - requires human judgment"
   }
```

### Post Approval Workflow

**N8N → Agent Flow:**

```
1. Content Scheduling triggers (9am, 2pm, 7pm OR manual)
   ↓

2. N8N Content Scheduler workflow:
   - Fetches assets from Cloudinary
   - Smart asset selection based on historical performance
   - Generates caption via GPT-4o-mini
   - Prepares Instagram API payload
   ↓

3. N8N POSTs to Agent: /approve/post

   Payload:
   {
     "scheduled_post_id": "draft_789",
     "asset": {
       "public_id": "ig_asset_001",
       "image_url": "https://cloudinary.../image.jpg",
       "width": 1080,
       "height": 1080,
       "tags": ["product", "lifestyle", "seasonal"]
     },
     "proposed_caption": "Spring is here! 🌸 Discover our new sustainable collection.
       Handpicked from eco-conscious designers. Link in bio for 20% off!

       #EcoFashion #SustainableLiving #SpringStyle #Ethical #ShopSustainable",
     "business_account_id": "account_uuid",
     "hashtags": ["EcoFashion", "SustainableLiving", ...],
     "hashtag_count": 8,
     "caption_length": 187,
     "engagement_prediction": 0.045,
     "post_type": "product_showcase",
     "scheduled_time": "2025-02-02T14:00:00Z"
   }
   ↓

4. Agent Analysis:
   - Evaluates caption quality (hooks, structure, CTAs)
   - Checks brand alignment (voice, values, audience)
   - Analyzes hashtag strategy (relevance, reach, mix)
   - Assesses engagement potential
   - Checks for spam/inappropriate content
   ↓

5. Agent Response:

   {
     "approved": true,
     "modifications": {
       "caption": "Spring is here! 🌸 Discover our new sustainable collection...
         [IMPROVED VERSION with better hook + stronger CTA]",
       "hashtags": ["EcoFashion", "SustainableLiving", "SpringCollection", ...],
       "hashtag_count": 9
     },
     "quality_score": 8.7,
     "decision_reasoning": "Strong caption with good hook and CTA. Minor improvements: added trending hashtag, stronger closing statement.",
     "engagement_prediction": 0.051,
     "brand_alignment_score": 0.94,
     "audit_data": {...}
   }
   OR
   {
     "approved": false,
     "modifications": null,
     "decision_reasoning": "Caption violates posting policy: excessive hashtags (12, max 10). Resubmit with revised hashtag strategy.",
     "quality_score": 5.2,
     "issues": ["too_many_hashtags", "cta_not_clear"]
   }
```

---

## Agent Endpoint Specifications

### 1. POST /approve/comment-reply

**Purpose:** Approve or reject N8N's proposed comment reply

**Request Body:**
```json
{
  "comment_id": "string (Meta comment ID)",
  "comment_text": "string (Original comment from user)",
  "commenter_username": "string (Instagram handle)",
  "post_id": "string (Instagram post ID)",
  "business_account_id": "string (UUID)",
  "proposed_reply": "string (N8N's suggested response)",
  "detected_intent": "string (sizing|shipping|complaint|praise|etc)",
  "sentiment": "string (positive|negative|neutral)",
  "confidence": "number (0-1)"
}
```

**Response (Approved):**
```json
{
  "approved": true,
  "modifications": {
    "reply_text": "string (modified or original reply)"
  },
  "decision_reasoning": "string (why approved, what improved)",
  "confidence": 0.88,
  "sentiment": "string",
  "brand_alignment_score": 0.91,
  "audit_data": {
    "analyzed_at": "ISO timestamp",
    "agent_model": "llama3.1:8b",
    "analysis_factors": ["sentiment", "tone", "relevance", "brand_voice"],
    "context_used": ["post_caption", "engagement_metrics"]
  }
}
```

**Response (Rejected):**
```json
{
  "approved": false,
  "modifications": null,
  "decision_reasoning": "string (why rejected)",
  "confidence": 0.75,
  "issues": ["array of issues found"],
  "audit_data": {...}
}
```

**Status Codes:**
- `200` - Decision made successfully
- `400` - Invalid request payload
- `500` - Agent error (Ollama unavailable, DB error, etc)

---

### 2. POST /approve/dm-reply

**Purpose:** Approve or reject DM reply with escalation awareness

**Request Body:**
```json
{
  "message_id": "string",
  "dm_text": "string (customer's message)",
  "sender_username": "string",
  "sender_id": "string (Instagram user ID)",
  "business_account_id": "string (UUID)",
  "proposed_reply": "string",
  "detected_intent": "string (order|complaint|inquiry|etc)",
  "sentiment": "string",
  "within_24h_window": boolean,
  "priority": "string (low|medium|high|urgent)",
  "customer_history": {
    "previous_interactions": number,
    "sentiment_history": "string",
    "lifetime_value": number
  }
}
```

**Response (Approved):**
```json
{
  "approved": true,
  "modifications": {
    "reply_text": "string (max 150 chars for IG)"
  },
  "decision_reasoning": "string",
  "confidence": 0.89,
  "needs_escalation": false,
  "audit_data": {...}
}
```

**Response (Escalation Needed):**
```json
{
  "approved": false,
  "modifications": null,
  "needs_escalation": true,
  "escalation_reason": "string (why human needed)",
  "suggested_team": "string (support|sales|etc)",
  "audit_data": {...}
}
```

---

### 3. POST /approve/post

**Purpose:** Approve or reject proposed post with caption/hashtag refinements

**Request Body:**
```json
{
  "scheduled_post_id": "string",
  "asset": {
    "public_id": "string",
    "image_url": "string (Cloudinary URL)",
    "width": number,
    "height": number,
    "tags": ["array of content tags"]
  },
  "proposed_caption": "string",
  "business_account_id": "string (UUID)",
  "hashtags": ["array"],
  "hashtag_count": number,
  "caption_length": number,
  "engagement_prediction": number (0-1),
  "post_type": "string (product|story|carousel|etc)",
  "scheduled_time": "ISO timestamp"
}
```

**Response (Approved):**
```json
{
  "approved": true,
  "modifications": {
    "caption": "string (improved caption if changed)",
    "hashtags": ["array of hashtags (if changed)"],
    "hashtag_count": number
  },
  "quality_score": 8.7,
  "decision_reasoning": "string",
  "engagement_prediction": 0.051,
  "brand_alignment_score": 0.94,
  "audit_data": {...}
}
```

**Response (Rejected):**
```json
{
  "approved": false,
  "modifications": null,
  "quality_score": 5.2,
  "decision_reasoning": "string",
  "issues": ["array of specific issues"],
  "recommendations": ["array of suggestions"],
  "audit_data": {...}
}
```

---

## Database Integration Points

### Supabase Tables Agent Reads From

**1. instagram_media**
```sql
SELECT caption, media_type, like_count, comments_count,
       reach, impressions, engagement_rate
FROM instagram_media
WHERE instagram_media_id = ?
LIMIT 1
```
Used for: Post context, engagement metrics, understanding audience

**2. instagram_business_accounts**
```sql
SELECT instagram_business_username, industry_type,
       brand_voice_profile, audience_demographics
FROM instagram_business_accounts
WHERE id = ?
LIMIT 1
```
Used for: Brand voice alignment, account context

**3. instagram_comments** (for history/pattern learning)
```sql
SELECT comment_text, status, created_at
FROM instagram_comments
WHERE business_account_id = ? AND created_at > NOW() - INTERVAL '30 days'
ORDER BY created_at DESC
LIMIT 10
```

### Supabase Tables Agent Writes To

**1. audit_log** (Primary logging table)
```json
{
  "event_type": "comment_reply_approval|dm_reply_approval|post_approval",
  "action": "approved|rejected|escalated",
  "resource_type": "comment|dm|post",
  "resource_id": "meta_comment_id|dm_id|post_id",
  "user_id": "business_account_id",
  "details": {
    "proposed_action": "original suggestion",
    "approved_action": "what was actually approved/modified",
    "decision_factors": {
      "sentiment": "score",
      "brand_alignment": "score",
      "quality": "score"
    },
    "reasoning": "agent's explanation",
    "confidence": 0.88
  },
  "ip_address": "agent_container_ip",
  "success": true,
  "created_at": "ISO timestamp"
}
```

---

## Agent Analysis Model Specifications

### LLM Configuration

**Model:** Ollama with Llama 3.1 8B
- Local execution (privacy)
- Low latency (~1-3 seconds per request)
- Zero API costs
- Easily upgradable to 70B

**Prompt Engineering Strategy:**

Each approval endpoint uses a specialized prompt template:

#### Comment Reply Prompt Template:
```
You are an Instagram brand voice expert and community manager.

Brand Profile:
- Brand: {account_type}
- Audience: {audience_demographics}
- Voice: {brand_voice_description}

Context:
- Post Caption: {post_caption}
- Post Engagement: {engagement_metrics}
- Customer Comment: "{comment_text}"

Proposed Reply: "{proposed_reply}"

Analyze the proposed reply for:
1. Relevance: Does it address the comment?
2. Brand Alignment: Does it match the brand voice?
3. Tone: Is it appropriate (friendly, professional, helpful)?
4. Quality: Is it well-written and valuable?
5. Sentiment: Does it create positive engagement?

Provide JSON response:
{
  "approved": true|false,
  "modifications": "improved reply text or null",
  "quality_score": 0-10,
  "reasoning": "brief explanation"
}
```

#### DM Reply Prompt Template:
```
You are a customer service specialist for an Instagram business.

Customer Context:
- Message: "{dm_text}"
- Intent: {detected_intent}
- History: {customer_history}
- Window Status: {24h_window_status}

Proposed Response: "{proposed_reply}"

Evaluate for:
1. Appropriateness: Does it handle the request?
2. Personalization: Does it feel personal for this customer?
3. Tone: Is it appropriate for DM (more casual than comments)?
4. Escalation Need: Does this need human attention?

Provide JSON:
{
  "approved": true|false,
  "modifications": "improved response or null",
  "needs_escalation": true|false,
  "reasoning": "explanation"
}
```

#### Post Caption Prompt Template:
```
You are an Instagram content strategist and caption expert.

Brand Profile:
{brand_details}

Proposed Caption Analysis:
- Caption: "{proposed_caption}"
- Hashtags: {hashtags}
- Post Type: {post_type}
- Asset: {asset_description}

Evaluate for:
1. Hook: Does it grab attention in first line?
2. Structure: Is there clear hook→body→CTA?
3. Brand Voice: Matches brand tone and values?
4. Hashtag Strategy: Relevant, not spammy?
5. Engagement: Will it drive likes, comments, saves?

Return JSON:
{
  "approved": true|false,
  "modifications": {
    "caption": "improved caption or null",
    "hashtags": ["revised tags or null"]
  },
  "quality_score": 0-10,
  "engagement_prediction": 0-1,
  "reasoning": "detailed explanation"
}
```

---

## Decision Factors & Scoring

### Comment Reply Decision Factors

1. **Sentiment Alignment (Weight: 30%)**
   - Proposed reply sentiment matches comment intent
   - Positive replies to positive comments
   - Helpful tone to questions

2. **Relevance (Weight: 25%)**
   - Reply addresses the actual comment
   - Doesn't go off-topic
   - Specific to the customer's concern

3. **Brand Voice (Weight: 25%)**
   - Tone matches brand personality
   - Language is consistent with other replies
   - Appropriate level of formality

4. **Quality (Weight: 20%)**
   - Well-written, no grammar errors
   - Appropriate length (not too long for comments)
   - Includes relevant emojis if brand uses them

**Approval Threshold:** Score ≥ 0.75 (75%)

### DM Reply Decision Factors

1. **Appropriateness (Weight: 35%)**
   - Addresses customer's actual request
   - Doesn't make false promises
   - Handles edge cases properly

2. **Personalization (Weight: 25%)**
   - Uses customer's name if available
   - References customer history if relevant
   - Tone matches customer relationship level

3. **Escalation Need (Weight: 25%)**
   - Complexity of request
   - Customer sentiment (angry customers need humans)
   - VIP/high-value customer status

4. **Format (Weight: 15%)**
   - Under 150 character limit
   - Clear and concise for mobile reading
   - Appropriate emoji usage

**Escalation Triggers:**
- Customer sentiment: Negative/angry
- Request type: Refund/return/complaint
- VIP customer: Lifetime value > $500
- Complexity: Topic requires domain knowledge

### Post Approval Decision Factors

1. **Caption Quality (Weight: 30%)**
   - Strong hook in first 1-2 lines
   - Clear body with value/story
   - Strong CTA (call-to-action)

2. **Brand Alignment (Weight: 25%)**
   - Matches brand voice and values
   - Audience resonance
   - Content theme consistency

3. **Hashtag Strategy (Weight: 20%)**
   - Relevant tags (not spammy)
   - Mix of popular + niche tags
   - Under 10 tags (IG optimal)

4. **Engagement Potential (Weight: 15%)**
   - Historical performance of similar posts
   - Timing optimization
   - Content type effectiveness

5. **Compliance (Weight: 10%)**
   - No prohibited content
   - Proper disclosures if sponsored
   - Character limit (max 2200)

**Approval Threshold:** Score ≥ 0.72 (72%)

---

## Error Handling & Edge Cases

### Agent Error Responses

**Ollama Model Unavailable:**
```json
{
  "error": "model_unavailable",
  "message": "AI model is initializing. Please retry in 30 seconds.",
  "status": 503
}
```

**Database Connection Error:**
```json
{
  "error": "db_error",
  "message": "Unable to fetch context from database",
  "status": 500,
  "fallback": {
    "approved": "pending_manual_review",
    "reason": "Agent cannot fetch required context"
  }
}
```

**Invalid Request Payload:**
```json
{
  "error": "validation_error",
  "message": "Missing required field: business_account_id",
  "status": 400
}
```

**N8N Webhook Timeout:**
- If agent takes >10 seconds, N8N will timeout
- Agent should process within 3-5 seconds
- Implement caching for frequently accessed data

---

## Testing & Validation

### Unit Test Cases

**Comment Reply Tests:**
- [ ] Approve relevant, on-brand replies
- [ ] Reject off-topic replies
- [ ] Modify short replies to add value
- [ ] Handle sentiment mismatches
- [ ] Test with different brand voices

**DM Reply Tests:**
- [ ] Approve straightforward questions
- [ ] Escalate complaints
- [ ] Reject VIP customer automated responses
- [ ] Handle 24h window expiration
- [ ] Test priority-based routing

**Post Tests:**
- [ ] Approve well-structured captions
- [ ] Improve weak hooks
- [ ] Validate hashtag counts
- [ ] Reject policy violations
- [ ] Test seasonal/trending content

### E2E Integration Tests

```
1. N8N sends comment approval request
   ↓
2. Agent fetches context from Supabase
   ↓
3. Agent analyzes with Ollama
   ↓
4. Agent logs decision to audit_log
   ↓
5. Agent returns response to N8N
   ↓
6. N8N executes/skips based on response
   ↓
7. Verify decision logged in audit_log
```

---

## Deployment & Operations

### Environment Variables Required

```bash
# Supabase
SUPABASE_URL=https://uromexjprcrjfmhkmgxa.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Ollama
OLLAMA_HOST=http://ollama:11434  # Docker internal
OLLAMA_MODEL=llama3.1:8b

# N8N Callback (optional - for agent to trigger N8N)
N8N_BASE_URL=https://n8n.888intelligenceautomation.in
N8N_APPROVAL_WEBHOOK=https://...

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=3002
FLASK_ENV=production
```

### Health Check Endpoint

**GET /health**

Response:
```json
{
  "status": "healthy|unhealthy",
  "model": "llama3.1:8b",
  "model_loaded": true|false,
  "db_connection": "connected|disconnected",
  "uptime_seconds": 3600,
  "requests_processed": 145,
  "average_response_time_ms": 2400
}
```

### Monitoring & Logging

Log all decisions to Supabase audit_log for oversight:

```sql
SELECT
  event_type,
  action,
  details->>'quality_score' as quality,
  details->>'confidence' as confidence,
  COUNT(*) as count,
  DATE(created_at) as date
FROM audit_log
WHERE event_type LIKE '%approval'
GROUP BY 1, 2, 5, 6
ORDER BY date DESC, count DESC
```

---

## Integration Checklist

- [ ] Agent Flask app running on port 3002
- [ ] Ollama model loaded and responding
- [ ] Supabase connection verified
- [ ] /health endpoint returning healthy
- [ ] Comment approval endpoint tested with N8N
- [ ] DM approval endpoint tested with N8N
- [ ] Post approval endpoint tested with N8N
- [ ] Audit logging working (check audit_log table)
- [ ] Error handling for Ollama unavailable
- [ ] Error handling for database errors
- [ ] Response time < 5 seconds per request
- [ ] All three approval workflows integrated

---

## Next Steps for Development

1. **Refactor agent.py** with 3 approval endpoints
2. **Implement context fetching** from Supabase
3. **Engineer specialized prompts** for each approval type
4. **Add modification logic** for suggestion improvements
5. **Implement comprehensive audit logging**
6. **Add error handling & resilience**
7. **Performance optimization** (caching, parallelization)
8. **Integration testing** with N8N workflows
9. **Deployment & monitoring setup**
10. **Documentation & runbooks**

---

## Key Contacts & Integration

- **N8N Webhooks:** Send POST requests to `/approve/*` endpoints
- **Supabase DB:** Query tables via service key (env var)
- **Ollama:** Local model at `http://ollama:11434`
- **Slack Notifications:** Optional error alerts (to be configured)
- **Backend API:** Can extend agent endpoints if needed

---

This comprehensive context enables building the LangChain oversight brain as the central decision authority for Instagram automation.
