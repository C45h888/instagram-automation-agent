# Supabase Database Schema — Agent Reference

This documents the **real** Supabase schema as queried from the live database.
The agent uses 6 tables. All other tables are used by the frontend/backend only.

> **Source of truth:** The Supabase database. If this file disagrees with the DB, the DB is correct.

---

## Agent-Used Tables

### `instagram_media`
Post/media data synced from Instagram Graph API.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `business_account_id` | uuid | FK → instagram_business_accounts.id |
| `instagram_media_id` | varchar | Unique, Instagram's media ID |
| `media_type` | varchar | IMAGE, VIDEO, CAROUSEL_ALBUM |
| `media_url` | text | Nullable |
| `thumbnail_url` | text | Nullable |
| `permalink` | text | Nullable |
| `caption` | text | Nullable |
| `hashtags` | text[] | Array of hashtag strings |
| `mentions` | text[] | Array of mentioned usernames |
| `like_count` | int4 | Default 0 |
| `comments_count` | int4 | Default 0 |
| `shares_count` | int4 | Default 0 |
| `reach` | int4 | Default 0 |
| `impressions` | int4 | Default 0 |
| `published_at` | timestamptz | Nullable |
| `status` | text | draft / scheduled / published |
| `scheduled_for` | timestamptz | Nullable, for auto-publish |
| `created_at` | timestamptz | Default now() |
| `updated_at` | timestamptz | Default now() |

**Agent notes:**
- `engagement_rate` does NOT exist as a column. Computed in Python: `(like_count + comments_count) / reach`
- Queried by `instagram_media_id` (not `id`) when looking up by Instagram's post ID

---

### `instagram_business_accounts`
Connected Instagram business/creator accounts.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `user_id` | uuid | FK → auth.users.id |
| `instagram_business_id` | varchar | Unique, Instagram's business ID |
| `instagram_user_id` | varchar | Nullable |
| `name` | varchar | Display name |
| `username` | varchar | Instagram @handle |
| `account_type` | enum | personal / business / creator |
| `biography` | text | Nullable |
| `website` | text | Nullable |
| `profile_picture_url` | text | Nullable |
| `followers_count` | int4 | Default 0 |
| `following_count` | int4 | Default 0 |
| `media_count` | int4 | Default 0 |
| `is_connected` | bool | Default true |
| `connection_status` | varchar | Default 'active' |
| `category` | varchar | Nullable, business category |
| `contact_email` | varchar | Nullable |
| `granted_permissions` | jsonb | Default [] |
| `required_permissions` | jsonb | Default [] |
| `created_at` | timestamptz | Default now() |
| `updated_at` | timestamptz | Default now() |

**Agent notes:**
- Use `username` (NOT `instagram_business_username` — that column does not exist)
- Queried by `id` (UUID) which is the `business_account_id` passed from N8N

---

### `instagram_comments`
Comments on Instagram posts.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `media_id` | uuid | FK → instagram_media.id, nullable |
| `business_account_id` | uuid | FK → instagram_business_accounts.id |
| `instagram_comment_id` | varchar | Unique, Instagram's comment ID |
| `parent_comment_id` | varchar | Nullable, for threaded replies |
| `text` | text | Comment body |
| `author_instagram_id` | varchar | Nullable |
| `author_username` | varchar | Nullable |
| `author_name` | varchar | Nullable |
| `like_count` | int4 | Default 0 |
| `reply_count` | int4 | Default 0 |
| `processed_by_automation` | bool | Default false |
| `automated_response_sent` | bool | Default false |
| `response_text` | text | Nullable |
| `response_sent_at` | timestamptz | Nullable |
| `sentiment` | varchar | Nullable (positive/neutral/negative) |
| `category` | varchar | Nullable |
| `priority` | varchar | Default 'normal' |
| `published_at` | timestamptz | Nullable |
| `created_at` | timestamptz | Default now() |

**Agent notes:**
- Column is `text` (NOT `comment_text` — that does not exist)
- `status` column does NOT exist
- Queried by `business_account_id` for recent comments context

---

### `instagram_dm_conversations`
DM thread-level metadata with 24h window tracking.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `instagram_thread_id` | varchar | Unique |
| `business_account_id` | uuid | FK → instagram_business_accounts.id |
| `customer_user_id` | uuid | FK → user_profiles.user_id, nullable |
| `customer_instagram_id` | varchar | Instagram ID of the customer |
| `customer_username` | varchar | Nullable |
| `customer_name` | varchar | Nullable |
| `window_expires_at` | timestamptz | When 24h window expires |
| `within_window` | bool | Default false — can business send? |
| `last_user_message_at` | timestamptz | Triggers window reset |
| `conversation_status` | varchar | active / archived / muted / blocked / pending |
| `last_message_at` | timestamptz | Nullable |
| `last_message_preview` | text | Nullable |
| `message_count` | int4 | Default 0 |
| `unread_count` | int4 | Default 0 |
| `auto_reply_enabled` | bool | Default false |
| `ai_assistant_enabled` | bool | Default false |
| `first_message_at` | timestamptz | Nullable |
| `created_at` | timestamptz | Default now() |

**Agent notes:**
- The table `instagram_dms` does NOT exist. DMs use two tables: conversations + messages.
- Queried by `business_account_id` + `customer_instagram_id` to find conversation thread

---

### `instagram_dm_messages`
Individual DM messages within conversations.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `instagram_message_id` | varchar | Unique |
| `conversation_id` | uuid | FK → instagram_dm_conversations.id |
| `sent_by_user_id` | uuid | FK → user_profiles.user_id, nullable |
| `is_from_business` | bool | TRUE = business sent, FALSE = customer |
| `sender_instagram_id` | varchar | |
| `sender_username` | varchar | Nullable |
| `message_type` | varchar | text / media / story_reply / story_mention / post_share / voice_note / reel_share / icebreaker |
| `message_text` | text | Nullable |
| `media_url` | text | Nullable |
| `media_type` | varchar | Nullable |
| `sent_at` | timestamptz | |
| `delivered_at` | timestamptz | Nullable |
| `read_at` | timestamptz | Nullable |
| `is_read` | bool | Default false |
| `was_automated` | bool | Default false |
| `ai_generated` | bool | Default false |
| `send_status` | varchar | pending / sent / delivered / failed / rejected |
| `error_message` | text | Nullable |
| `created_at` | timestamptz | Default now() |

**Agent notes:**
- `is_from_business` maps to direction: true → "outbound", false → "inbound"
- Queried by `conversation_id` after finding conversation from `instagram_dm_conversations`

---

### `audit_log`
Agent decision audit trail. RLS enabled, 56 existing rows.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | PK, auto-generated |
| `user_id` | uuid | FK → auth.users.id, nullable |
| `event_type` | varchar | Required (e.g. comment_reply_approval) |
| `resource_type` | varchar | Nullable (comment / dm / post) |
| `resource_id` | uuid | Nullable — must be valid UUID or NULL |
| `action` | varchar | Required, top-level (approved / rejected / escalated) |
| `details` | jsonb | Default {} — free-form context |
| `ip_address` | inet | Nullable |
| `user_agent` | text | Nullable |
| `success` | bool | Default true |
| `error_message` | text | Nullable |
| `created_at` | timestamptz | Default now() |

**Agent notes:**
- Column is `event_type` (NOT `event`)
- Column is `details` (NOT `data`)
- `action` is a top-level column (NOT nested inside details/data)
- `resource_id` must be a valid UUID — non-UUID IDs are stored in `details.original_resource_id`
- `user_id` must be a valid UUID — non-UUID IDs stored in `details.original_user_id`
- Agent operation: INSERT only (no UPDATE/DELETE)

---

## Tables NOT Used by Agent

These tables exist in the DB but are used by the frontend/backend only:

- `user_profiles` — User account profiles
- `admin_users` — Admin access control
- `instagram_credentials` — OAuth tokens (encrypted)
- `automation_workflows` — N8N workflow configs
- `workflow_executions` — Workflow run history
- `daily_analytics` — Aggregated daily metrics
- `notifications` — User notifications
- `api_usage` — API call tracking
- `data_deletion_requests` — GDPR deletion requests
- `user_consents` — GDPR consent tracking
- `ugc_content` — User-generated content
- `ugc_permissions` — UGC repost permissions
- `ugc_campaigns` — UGC campaign tracking

---

## RLS Policy Recommendations

The agent uses a **service role key** (bypasses RLS). For defense-in-depth, add these policies:

```sql
-- Agent can SELECT from content tables
CREATE POLICY "agent_read_media" ON instagram_media FOR SELECT USING (true);
CREATE POLICY "agent_read_accounts" ON instagram_business_accounts FOR SELECT USING (true);
CREATE POLICY "agent_read_comments" ON instagram_comments FOR SELECT USING (true);
CREATE POLICY "agent_read_dm_conversations" ON instagram_dm_conversations FOR SELECT USING (true);
CREATE POLICY "agent_read_dm_messages" ON instagram_dm_messages FOR SELECT USING (true);

-- Agent can only INSERT to audit_log (no update/delete)
CREATE POLICY "agent_write_audit" ON audit_log FOR INSERT WITH CHECK (true);
```
