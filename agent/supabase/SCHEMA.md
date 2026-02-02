# Supabase Database Schema Documentation

**Version:** 1.0
**Date:** February 2, 2026
**Purpose:** Complete reference for all Supabase tables used by the LangChain agent

---

## Overview

Supabase is the **single source of truth** for the Instagram automation system. All services (frontend, backend, agent, N8N) read from and write to this shared database.

**Connection Details:**
- URL: `https://uromexjprcrjfmhkmgxa.supabase.co`
- Authentication: Service role key (env: `SUPABASE_KEY`)
- Client: Python `supabase-py` library

---

## Table Schemas

### 1. `instagram_media`

**Purpose:** Stores Instagram posts, reels, and associated metadata

**Columns:**
| Column | Type | Description | Used By Agent |
|--------|------|-------------|---------------|
| `instagram_media_id` | TEXT (PK) | Instagram's media ID | ✅ Query key |
| `business_account_id` | UUID (FK) | Links to business account | ✅ Filter |
| `caption` | TEXT | Post caption/description | ✅ Context |
| `media_type` | TEXT | IMAGE, VIDEO, CAROUSEL_ALBUM | ✅ Analysis |
| `like_count` | INTEGER | Number of likes | ✅ Engagement |
| `comments_count` | INTEGER | Number of comments | ✅ Engagement |
| `engagement_rate` | DECIMAL | Calculated engagement % | ✅ Benchmarking |
| `reach` | INTEGER | Unique accounts reached | ✅ Performance |
| `impressions` | INTEGER | Total views | ✅ Performance |
| `published_at` | TIMESTAMP | When post went live | ✅ Sorting |
| `permalink` | TEXT | Instagram URL | ❌ |
| `media_url` | TEXT | Image/video URL | ❌ |
| `thumbnail_url` | TEXT | Thumbnail for videos | ❌ |
| `created_at` | TIMESTAMP | DB record creation | ❌ |
| `updated_at` | TIMESTAMP | Last DB update | ❌ |

**Agent Queries:**

```python
# Get post context for comment analysis
supabase.table("instagram_media") \
    .select("caption, like_count, comments_count, media_type, engagement_rate") \
    .eq("instagram_media_id", post_id) \
    .limit(1) \
    .execute()

# Get recent post performance for benchmarking
supabase.table("instagram_media") \
    .select("like_count, comments_count, engagement_rate") \
    .eq("business_account_id", account_id) \
    .order("published_at", desc=True) \
    .limit(10) \
    .execute()
```

**Referenced In:**
- [supabase_service.py:10-23](../services/supabase_service.py#L10-L23) - `get_post_context()`
- [supabase_service.py:77-105](../services/supabase_service.py#L77-L105) - `get_recent_post_performance()`

---

### 2. `instagram_business_accounts`

**Purpose:** Stores Instagram business account profiles and credentials

**Columns:**
| Column | Type | Description | Used By Agent |
|--------|------|-------------|---------------|
| `id` | UUID (PK) | Internal account ID | ✅ Query key |
| `instagram_business_username` | TEXT | @username | ✅ Context |
| `name` | TEXT | Display name | ✅ Brand identity |
| `username` | TEXT | Alternative username field | ✅ Fallback |
| `followers_count` | INTEGER | Follower count | ✅ Audience size |
| `industry_type` | TEXT | Business category | ✅ Brand voice |
| `brand_voice_profile` | TEXT | Brand personality description | ✅ Analysis |
| `audience_demographics` | JSONB | Audience data | ✅ Context |
| `instagram_business_id` | TEXT | Meta's account ID | ❌ |
| `access_token` | TEXT (encrypted) | OAuth token | ❌ |
| `token_expires_at` | TIMESTAMP | Token expiry | ❌ |
| `profile_picture_url` | TEXT | Profile image | ❌ |
| `website` | TEXT | Business website | ❌ |
| `biography` | TEXT | Bio text | ❌ |
| `created_at` | TIMESTAMP | DB record creation | ❌ |
| `updated_at` | TIMESTAMP | Last update | ❌ |

**Agent Queries:**

```python
# Get account info for brand voice alignment
supabase.table("instagram_business_accounts") \
    .select("instagram_business_username, name, username, followers_count") \
    .eq("id", business_account_id) \
    .limit(1) \
    .execute()
```

**Referenced In:**
- [supabase_service.py:26-39](../services/supabase_service.py#L26-L39) - `get_account_info()`
- All approval endpoints use this for brand context

---

### 3. `instagram_comments`

**Purpose:** Stores comments on Instagram posts

**Columns:**
| Column | Type | Description | Used By Agent |
|--------|------|-------------|---------------|
| `id` | UUID (PK) | Internal comment ID | ❌ |
| `instagram_comment_id` | TEXT | Meta's comment ID | ❌ |
| `business_account_id` | UUID (FK) | Account that received comment | ✅ Filter |
| `post_id` | TEXT (FK) | Related post ID | ❌ |
| `commenter_username` | TEXT | Who commented | ❌ |
| `commenter_id` | TEXT | Commenter's Instagram ID | ❌ |
| `comment_text` | TEXT | Comment content | ✅ Pattern learning |
| `status` | TEXT | active, hidden, deleted | ✅ Filter |
| `parent_comment_id` | TEXT | For threaded comments | ❌ |
| `like_count` | INTEGER | Likes on comment | ❌ |
| `created_at` | TIMESTAMP | When comment posted | ✅ Sorting |
| `updated_at` | TIMESTAMP | Last update | ❌ |

**Agent Queries:**

```python
# Get recent comments for pattern analysis
supabase.table("instagram_comments") \
    .select("comment_text, status, created_at") \
    .eq("business_account_id", business_account_id) \
    .order("created_at", desc=True) \
    .limit(10) \
    .execute()
```

**Referenced In:**
- [supabase_service.py:42-56](../services/supabase_service.py#L42-L56) - `get_recent_comments()`

---

### 4. `instagram_dms`

**Purpose:** Stores Instagram direct messages

**Columns:**
| Column | Type | Description | Used By Agent |
|--------|------|-------------|---------------|
| `id` | UUID (PK) | Internal message ID | ❌ |
| `instagram_message_id` | TEXT | Meta's message ID | ❌ |
| `business_account_id` | UUID (FK) | Business account | ✅ Filter |
| `recipient_id` | TEXT | Customer's Instagram ID | ✅ Query key |
| `sender_id` | TEXT | Who sent the message | ❌ |
| `message_text` | TEXT | Message content | ✅ History context |
| `direction` | TEXT | inbound, outbound | ✅ Conversation flow |
| `status` | TEXT | sent, delivered, read | ✅ Filter |
| `attachments` | JSONB | Media/stickers | ❌ |
| `created_at` | TIMESTAMP | When sent | ✅ Sorting |
| `updated_at` | TIMESTAMP | Last update | ❌ |

**Agent Queries:**

```python
# Get DM conversation history
supabase.table("instagram_dms") \
    .select("message_text, direction, status, created_at") \
    .eq("business_account_id", business_account_id) \
    .eq("recipient_id", sender_id) \
    .order("created_at", desc=True) \
    .limit(5) \
    .execute()
```

**Referenced In:**
- [supabase_service.py:59-74](../services/supabase_service.py#L59-L74) - `get_dm_history()`

---

### 5. `audit_log`

**Purpose:** Comprehensive logging of all agent decisions and system events

**Columns:**
| Column | Type | Description | Used By Agent |
|--------|------|-------------|---------------|
| `id` | UUID (PK) | Log entry ID | ❌ |
| `event` | TEXT | Event type (see below) | ✅ Write |
| `user_id` | UUID | Business account ID | ✅ Write |
| `ip_address` | TEXT | Request origin | ✅ Write |
| `data` | JSONB | Event-specific payload | ✅ Write |
| `success` | BOOLEAN | Operation success | ✅ Write |
| `error_message` | TEXT | Error if failed | ✅ Write |
| `created_at` | TIMESTAMP | When logged | ✅ Auto |

**Event Types:**
- `comment_reply_approval` - Comment approval decision
- `dm_reply_approval` - DM approval decision
- `post_approval` - Post caption approval decision
- `agent_error` - System errors
- `escalation_triggered` - Human escalation needed

**Data Payload Structure:**

```json
{
  "action": "approved|rejected|escalated",
  "resource_type": "comment|dm|post",
  "resource_id": "instagram_comment_id|message_id|post_id",
  "proposed_action": "Original N8N suggestion",
  "approved_action": "What agent approved/modified",
  "quality_score": 8.7,
  "confidence": 0.88,
  "reasoning": "Agent's explanation for decision",
  "latency_ms": 2400,
  "analysis_factors": ["sentiment", "tone", "relevance"],
  "context_used": ["post_caption", "engagement_metrics"]
}
```

**Agent Queries:**

```python
# Log every decision
supabase.table("audit_log").insert({
    "event": event_type,
    "user_id": user_id or None,
    "ip_address": ip_address or None,
    "data": {
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        **details
    }
}).execute()
```

**Referenced In:**
- [supabase_service.py:108-136](../services/supabase_service.py#L108-L136) - `log_decision()`
- [approve_comment.py:85-100](../routes/approve_comment.py#L85-L100)
- [approve_dm.py:165-180](../routes/approve_dm.py#L165-L180)
- [approve_post.py:129-144](../routes/approve_post.py#L129-L144)

---

## Database Relationships

```
instagram_business_accounts (1)
    ├── instagram_media (Many)
    │   └── instagram_comments (Many)
    ├── instagram_dms (Many)
    └── audit_log (Many)
```

**Foreign Key Relationships:**
- `instagram_media.business_account_id` → `instagram_business_accounts.id`
- `instagram_comments.business_account_id` → `instagram_business_accounts.id`
- `instagram_dms.business_account_id` → `instagram_business_accounts.id`
- `audit_log.user_id` → `instagram_business_accounts.id`

---

## Agent Integration Patterns

### Read Pattern: Context Fetching

```python
from services.supabase_service import SupabaseService

# 1. Get post context for comment analysis
post_ctx = SupabaseService.get_post_context("post_id_123")
# Returns: {caption, like_count, comments_count, engagement_rate}

# 2. Get account info for brand voice
account = SupabaseService.get_account_info("uuid-account-id")
# Returns: {instagram_business_username, name, followers_count}

# 3. Get DM history for personalization
history = SupabaseService.get_dm_history("sender_123", "account_uuid")
# Returns: [{message_text, direction, status, created_at}, ...]

# 4. Get performance benchmarks
perf = SupabaseService.get_recent_post_performance("account_uuid")
# Returns: {avg_likes, avg_comments, avg_engagement_rate, sample_size}
```

### Write Pattern: Audit Logging

```python
from services.supabase_service import SupabaseService

# Log every approval decision
SupabaseService.log_decision(
    event_type="comment_reply_approval",
    action="approved",
    resource_type="comment",
    resource_id="meta_comment_id",
    user_id="business_account_uuid",
    details={
        "proposed_reply": "Thanks for asking!",
        "approved_reply": "Thanks for asking! 🙏",
        "quality_score": 8.5,
        "reasoning": "Added emoji for brand voice alignment",
        "latency_ms": 2300
    },
    ip_address="172.18.0.5"
)
```

---

## Performance Considerations

### Indexing Strategy

**Critical Indexes (assume these exist):**
- `instagram_media(instagram_media_id)` - Primary lookup
- `instagram_media(business_account_id, published_at DESC)` - Performance queries
- `instagram_business_accounts(id)` - Account lookups
- `instagram_comments(business_account_id, created_at DESC)` - Recent comments
- `instagram_dms(business_account_id, recipient_id, created_at DESC)` - Conversation history
- `audit_log(user_id, created_at DESC)` - Decision history

### Query Optimization

1. **Always use `.limit()`** - Prevent large result sets
2. **Select only needed columns** - Reduce network transfer
3. **Order by indexed columns** - Faster sorting
4. **Use `.eq()` for exact matches** - Index utilization
5. **Cache frequently accessed data** - Future enhancement

---

## Error Handling

### Connection Failures

```python
# All SupabaseService methods include try/catch
if not supabase or not post_id:
    return {}

try:
    result = supabase.table("instagram_media").select(...).execute()
    return result.data[0] if result.data else {}
except Exception as e:
    logger.warning(f"Failed to fetch post context for {post_id}: {e}")
    return {}
```

### Graceful Degradation

- **Missing data:** Return empty dict `{}`
- **DB error:** Log warning, continue with partial context
- **Audit log failure:** Log error, don't block approval flow

---

## Security Considerations

1. **Service Role Key:** Used for all agent DB access (bypasses RLS)
2. **Row Level Security (RLS):** Applied for frontend/backend (not agent)
3. **Encrypted Tokens:** `access_token` field is encrypted at rest
4. **IP Logging:** All decisions log request IP for audit trail
5. **No PII in Logs:** Comments/DMs truncated in audit_log details

---

## Future Enhancements

### Planned Tables

- `customer_profiles` - VIP status, lifetime value, preferences
- `engagement_patterns` - ML training data for better predictions
- `escalation_queue` - Human review queue for flagged items

### Planned Columns

- `instagram_business_accounts.brand_voice_profile` - Structured brand guidelines
- `instagram_media.ai_caption_suggestions` - Store caption variants
- `audit_log.human_override` - Track when humans override agent

---

## Migration Notes

**Schema Version:** Current (as of Feb 2, 2026)

No migrations currently needed. All tables exist and are in production use.

**If schema changes are needed:**
1. Update this documentation
2. Update `SupabaseService` methods
3. Test queries in isolation
4. Deploy with backward compatibility

---

## References

- **Supabase Project:** https://uromexjprcrjfmhkmgxa.supabase.co
- **Python Client Docs:** https://supabase.com/docs/reference/python
- **Agent Service Layer:** [../services/supabase_service.py](../services/supabase_service.py)
- **Config:** [../config.py](../config.py)
- **Integration Guide:** [../.claude/AGENT-CONTEXT.md](../../.claude/AGENT-CONTEXT.md)
