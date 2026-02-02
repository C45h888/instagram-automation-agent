# N8N Workflow Integration Guide: Adding Agent Approval Nodes

This guide shows exactly where to insert HTTP Request nodes in N8N workflows to integrate with the LangChain Oversight Brain Agent.

**Agent Base URL:** `http://langchain-agent:3002` (Docker internal)

---

## 1. customer-service.json Integration

### Where to Insert
**Between:** "Personalize Response" node (GPT-4 generation) → "Is DM?" conditional node

### New Node: "Agent Approval - Customer Service"

**Node Type:** HTTP Request

**Configuration:**
```json
{
  "parameters": {
    "method": "POST",
    "url": "http://langchain-agent:3002/approve/dm-reply",
    "authentication": "none",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {
          "name": "Content-Type",
          "value": "application/json"
        },
        {
          "name": "X-API-Key",
          "value": "={{ $env.AGENT_API_KEY }}"
        }
      ]
    },
    "sendBody": true,
    "bodyParameters": {
      "parameters": []
    },
    "jsonBody": "={{ JSON.stringify({\n  \"message_id\": $('Merge Message Sources').item.json.id,\n  \"dm_text\": $('Merge Message Sources').item.json.text || $('Merge Message Sources').item.json.message,\n  \"sender_username\": $('Merge Message Sources').item.json.from?.username || \"unknown\",\n  \"sender_id\": $('Merge Message Sources').item.json.from?.id || \"unknown\",\n  \"business_account_id\": $credentials.instagram_business_account_id,\n  \"proposed_reply\": $('Personalize Response').item.json.message.content,\n  \"detected_intent\": $('Classify Messages').item.json.category,\n  \"sentiment\": $('Classify Messages').item.json.sentiment || \"neutral\",\n  \"within_24h_window\": true,\n  \"priority\": $('Route by Priority').item.json.priority || \"medium\",\n  \"customer_history\": {\n    \"previous_interactions\": 0,\n    \"sentiment_history\": \"neutral\",\n    \"lifetime_value\": 0\n  }\n}) }}",
    "options": {
      "timeout": 15000,
      "retry": {
        "enabled": true,
        "maxAttempts": 2,
        "waitBetweenAttempts": 1000
      }
    }
  },
  "id": "agent-approval-dm",
  "name": "Agent Approval - Customer Service",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [1100, 450]
}
```

### New Node: "Check Agent Decision"

**Node Type:** IF

**Configuration:**
```json
{
  "parameters": {
    "conditions": {
      "boolean": [
        {
          "value1": "={{ $('Agent Approval - Customer Service').item.json.approved }}",
          "operation": "equal",
          "value2": true
        }
      ]
    }
  },
  "id": "check-agent-decision",
  "name": "Check Agent Decision",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1,
  "position": [1300, 450]
}
```

### Updated Flow

```
Merge Message Sources
         ↓
Classify Messages
         ↓
Route by Priority
         ↓
Personalize Response (GPT-4)
         ↓
[NEW] Agent Approval - Customer Service (POST to agent)
         ↓
[NEW] Check Agent Decision (IF node)
    ├─ TRUE → Is DM? → Send DM Response / Reply to Comment
    └─ FALSE → Log Rejection → Slack Alert → End
```

### Rejection Path (add new nodes)

**Node: "Log Agent Rejection"**
```json
{
  "parameters": {
    "operation": "log",
    "message": "Agent rejected: {{ $('Agent Approval - Customer Service').item.json.decision_reasoning }}"
  },
  "name": "Log Agent Rejection",
  "type": "n8n-nodes-base.noOp",
  "position": [1300, 600]
}
```

**Node: "Notify Slack - Rejection"**
```json
{
  "parameters": {
    "channel": "#instagram-automation",
    "text": "🚫 Agent rejected customer service response\nReason: {{ $('Agent Approval - Customer Service').item.json.decision_reasoning }}\nOriginal: {{ $('Personalize Response').item.json.message.content }}"
  },
  "name": "Notify Slack - Rejection",
  "type": "n8n-nodes-base.slack",
  "position": [1500, 600]
}
```

---

## 2. content-scheduling.json Integration

### Where to Insert
**Between:** "Generate Enhanced Caption" (GPT-4o-mini) → "Parse & Validate Caption"

### New Node: "Agent Approval - Post"

**Node Type:** HTTP Request

**Configuration:**
```json
{
  "parameters": {
    "method": "POST",
    "url": "http://langchain-agent:3002/approve/post",
    "authentication": "none",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {
          "name": "Content-Type",
          "value": "application/json"
        },
        {
          "name": "X-API-Key",
          "value": "={{ $env.AGENT_API_KEY }}"
        }
      ]
    },
    "sendBody": true,
    "jsonBody": "={{ JSON.stringify({\n  \"scheduled_post_id\": \"draft_\" + Date.now(),\n  \"asset\": {\n    \"public_id\": $('Smart Asset Selection').item.json.public_id,\n    \"image_url\": $('Smart Asset Selection').item.json.secure_url,\n    \"width\": $('Smart Asset Selection').item.json.width,\n    \"height\": $('Smart Asset Selection').item.json.height,\n    \"tags\": $('Smart Asset Selection').item.json.tags || []\n  },\n  \"proposed_caption\": $('Generate Enhanced Caption').item.json.message.content,\n  \"business_account_id\": $credentials.instagram_business_account_id,\n  \"hashtags\": $('Parse & Validate Caption').item.json.hashtags || [],\n  \"hashtag_count\": $('Parse & Validate Caption').item.json.hashtag_count || 0,\n  \"caption_length\": $('Generate Enhanced Caption').item.json.message.content.length,\n  \"engagement_prediction\": $('Smart Asset Selection').item.json.predicted_engagement || 0.04,\n  \"post_type\": \"product\",\n  \"scheduled_time\": new Date().toISOString()\n}) }}",
    "options": {
      "timeout": 15000,
      "retry": {
        "enabled": true,
        "maxAttempts": 2,
        "waitBetweenAttempts": 1000
      }
    }
  },
  "id": "agent-approval-post",
  "name": "Agent Approval - Post",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [1200, 400]
}
```

### New Node: "Check Post Approval"

**Node Type:** IF

**Configuration:**
```json
{
  "parameters": {
    "conditions": {
      "boolean": [
        {
          "value1": "={{ $('Agent Approval - Post').item.json.approved }}",
          "operation": "equal",
          "value2": true
        }
      ]
    }
  },
  "id": "check-post-approval",
  "name": "Check Post Approval",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1,
  "position": [1400, 400]
}
```

### New Node: "Apply Agent Modifications"

**Node Type:** Set (only if approved)

**Configuration:**
```json
{
  "parameters": {
    "mode": "manual",
    "values": {
      "string": [
        {
          "name": "final_caption",
          "value": "={{ $('Agent Approval - Post').item.json.modifications?.caption || $('Generate Enhanced Caption').item.json.message.content }}"
        },
        {
          "name": "final_hashtags",
          "value": "={{ JSON.stringify($('Agent Approval - Post').item.json.modifications?.hashtags || $('Parse & Validate Caption').item.json.hashtags) }}"
        }
      ]
    }
  },
  "id": "apply-agent-modifications",
  "name": "Apply Agent Modifications",
  "type": "n8n-nodes-base.set",
  "position": [1600, 350]
}
```

### Updated Flow

```
Generate Enhanced Caption (GPT-4o-mini)
         ↓
[NEW] Agent Approval - Post (POST to agent)
         ↓
[NEW] Check Post Approval (IF node)
    ├─ TRUE → Apply Agent Modifications → Prepare Instagram Data → Create Media → Publish
    └─ FALSE → Skip Publish → Notify Slack → End
```

---

## 3. engagement-monitor.json Integration

### Where to Insert
**Between:** "Generate Response" (GPT-4) → "Post Reply" (Facebook API)

### New Node: "Agent Approval - Comment Reply"

**Node Type:** HTTP Request

**Configuration:**
```json
{
  "parameters": {
    "method": "POST",
    "url": "http://langchain-agent:3002/approve/comment-reply",
    "authentication": "none",
    "sendHeaders": true,
    "headerParameters": {
      "parameters": [
        {
          "name": "Content-Type",
          "value": "application/json"
        },
        {
          "name": "X-API-Key",
          "value": "={{ $env.AGENT_API_KEY }}"
        }
      ]
    },
    "sendBody": true,
    "jsonBody": "={{ JSON.stringify({\n  \"comment_id\": $('Split Comments').item.json.id,\n  \"comment_text\": $('Split Comments').item.json.text,\n  \"commenter_username\": $('Split Comments').item.json.from?.username || \"unknown\",\n  \"post_id\": $('Get Posts').item.json.id,\n  \"business_account_id\": $credentials.instagram_business_account_id,\n  \"proposed_reply\": $('Generate Response').item.json.message.content,\n  \"detected_intent\": $('Analyze Comment').item.json.detected_intent || \"general\",\n  \"sentiment\": $('Analyze Comment').item.json.sentiment || \"neutral\",\n  \"confidence\": $('Analyze Comment').item.json.confidence || 0.5\n}) }}",
    "options": {
      "timeout": 15000,
      "retry": {
        "enabled": true,
        "maxAttempts": 2,
        "waitBetweenAttempts": 1000
      }
    }
  },
  "id": "agent-approval-comment",
  "name": "Agent Approval - Comment Reply",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.1,
  "position": [1300, 450]
}
```

### New Node: "Check Reply Approval"

**Node Type:** IF

**Configuration:**
```json
{
  "parameters": {
    "conditions": {
      "boolean": [
        {
          "value1": "={{ $('Agent Approval - Comment Reply').item.json.approved }}",
          "operation": "equal",
          "value2": true
        }
      ]
    }
  },
  "id": "check-reply-approval",
  "name": "Check Reply Approval",
  "type": "n8n-nodes-base.if",
  "typeVersion": 1,
  "position": [1500, 450]
}
```

### Updated Flow

```
Analyze Comment (intent detection)
         ↓
Needs Human? (conditional)
    ├─ True → Alert Human Team (Slack)
    └─ False ↓
Generate Response (GPT-4)
         ↓
[NEW] Agent Approval - Comment Reply (POST to agent)
         ↓
[NEW] Check Reply Approval (IF node)
    ├─ TRUE → Post Reply (Facebook API) → Mark as Responded → Log
    └─ FALSE → Skip Reply → Mark as Reviewed → Log
```

---

## Environment Variables Required

Add to `.env.production` (N8N container):

```bash
AGENT_API_KEY=your-secret-api-key-here
```

This key must match the key configured in the agent's `.env.production`.

---

## Testing Integration

### 1. Test Health Check
```bash
curl http://langchain-agent:3002/health
```

Should return `{"status":"healthy","model":"nemotron:8b-q5_K_M",...}`

### 2. Test Comment Approval
```bash
curl -X POST http://langchain-agent:3002/approve/comment-reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "comment_id": "test_1",
    "comment_text": "Love this!",
    "post_id": "post_1",
    "business_account_id": "acc_1",
    "proposed_reply": "Thanks!",
    "detected_intent": "praise",
    "sentiment": "positive",
    "confidence": 0.9
  }'
```

Should return `{"approved":true,"modifications":{...},...}`

### 3. Test in N8N Workflow
1. Manually trigger the workflow
2. Check N8N execution log for agent approval step
3. Verify decision is logged in Supabase `audit_log` table

---

## Fallback Behavior

If agent is unreachable (down/timeout):
- N8N retry kicks in (2 attempts, 1s apart)
- If still fails → route to "Agent Down" error path
- Options:
  1. **Conservative:** Skip action, alert Slack
  2. **Aggressive:** Proceed with original (unmodified) action
  3. **Queue:** Store for manual review

Recommended: **Conservative** for DMs/posts, **Aggressive** for low-risk comment replies.

---

## Implementation Checklist

- [ ] Add `AGENT_API_KEY` to N8N `.env.production`
- [ ] Import modified workflow JSONs to N8N
- [ ] Test each approval endpoint with curl
- [ ] Trigger each workflow manually and verify agent is called
- [ ] Check Supabase `audit_log` for decision entries
- [ ] Test rejection paths (use bad proposed_reply)
- [ ] Test escalation (use VIP customer data or complaint intent)
- [ ] Verify modification logic (agent improves caption/reply)
- [ ] Monitor N8N + agent logs for errors
- [ ] Set up Slack alerts for agent rejections

---

## Next Steps

1. **Manual Editing:** Open each workflow JSON in N8N UI and add the nodes using the configurations above
2. **OR Programmatic:** Use N8N API to inject nodes (requires JSON manipulation)
3. **Test thoroughly** before production deployment
4. **Monitor performance:** Track agent latency (target < 5s per request)
