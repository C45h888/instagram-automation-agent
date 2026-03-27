# Plan: Supabase Tools → AgentService Tool Binding Backbone

## Context

The supabase tools (`get_post_context`, `get_account_info`, `get_recent_comments`, `get_dm_history`, `get_dm_conversation_context`, `get_post_performance`, `log_decision`) are the data backbone of all automations. They are imported into `AgentService`'s scoped tool sets but never invoked through `bind_tools()` in production. Every pipeline calls `LLMService.invoke()` with raw `llm`, pre-fetches data in Python, and feeds it as a fixed prompt. The LLM never decides what data to fetch.

The typed ID coercion bug was already fixed. The `analyze_message` recursion loop must also be resolved.

**Goal:** 6 supabase read tools go through `bind_tools()`. LLM decides when to call them. Execution tools (`reply_*`) and audit logging (`log_decision`) stay Python-side. This is the foundation.

**Out of scope:** content, attribution, analytics, oversight — each is a separate domain.

---

## Decisions Made

| # | Decision |
|---|---|
| Q1 | `analyze_message_tool` removed from scope (recursion). No replacement analysis tool in scope. |
| Q2 | **Split**: Escalation logic embedded in new prompt. `_apply_hard_escalation_rules()` stays in Python as safety override. |
| Q3 | Deferred |
| Q4 | Deferred |
| Q5 | Deferred |
| Q6 | Engagement monitor first, then dm_monitor |
| Q7 | Option C: LLM streams. Call site consumes generator, accumulates, parses, applies hard rules, routes. |
| Q8 | **Revised**: Remove `reply_to_comment_tool` and `reply_to_dm_tool` from scope — LLM executes replies via reasoning, Python executes via `_reply_to_comment()`/`_reply_to_dm()` directly. No duplication. |
| Q9 | Option A: All 6 supabase tools in engagement scope from the start. |
| Webhook | Webhooks write to Supabase only. Engagement monitor's polling run processes them via `AgentService`. Webhooks no longer call `_analyze_message()`. |
| Instance lifecycle | One `AgentService(scope="engagement")` instance per run, shared across all comments. |
| log_decision | Removed from `ENGAGEMENT_SCOPE_TOOLS`. Python logs deterministically. No duplicates. |

---

## Final `ENGAGEMENT_SCOPE_TOOLS` — 6 tools

```python
ENGAGEMENT_SCOPE_TOOLS = [
    get_post_context,              # Post caption, likes, engagement_rate
    get_account_info,             # Username, followers, account_type
    get_recent_comments,           # Account-level comment patterns (NOT thread context)
    get_dm_history,              # Prior DM messages for conversation context
    get_dm_conversation_context,  # 24h reply window status
    # log_decision — Python-only, no duplication
    # analyze_message_tool — removed, recursion loop
    # reply_to_comment_tool — removed, Python executes
    # reply_to_dm_tool — removed, Python executes
]
# Total: 6 tools
```

---

## Step 1 — Strip `_analyze_message()` (fix recursion loop)

**File:** `agent/tools/automation_tools.py`

`analyze_message_tool` wraps `_analyze_message()`. `_analyze_message()` calls `LLMService.invoke()`. If the LLM calls `analyze_message` through `bind_tools()`, it triggers another LLM call inside the tool — recursion loop. No tool in the scope calls `_analyze_message`, so this function is now only used by old callers during migration.

**Changes:**
- Remove `SYSTEM_PROMPT` import
- Remove `llm` import from `config`
- Remove `LLMService.invoke()` call and `AgentService._parse_json_response()` call
- Keep `_apply_hard_escalation_rules()` as a standalone function — safety layer, applied after `AgentService` stream in the new path
- `_analyze_message()` becomes a pure function that returns `None`. It is no longer called by the `AgentService` path. It is also no longer called by webhooks (webhooks write to Supabase only, engagement monitor processes via `AgentService`).

Actually — `_analyze_message()` returning `None` would break the non-bind callers. The cleanest approach: `_analyze_message()` is NOT modified yet. The `AgentService` path does not use `_analyze_message()`. The new `analyze_message_agent` prompt replaces it. Old callers (webhooks) are being removed from calling it in this plan.

Wait — webhooks currently call `_analyze_message()`. With the new architecture, webhooks write to Supabase, engagement monitor reads from Supabase via `AgentService`. So webhooks should no longer call `_analyze_message()`.

**Final decision for this step:**
- Remove `analyze_message_tool` from `ENGAGEMENT_SCOPE_TOOLS` (removes recursion risk)
- Remove `_analyze_message()` function entirely — it is replaced by `AgentService` + new prompt
- Remove `_apply_hard_escalation_rules()` from `_process_comment()` in engagement_monitor and dm_monitor — these are applied by the new `_apply_hard_escalation_rules()` standalone function after `AgentService` returns
- Actually `_apply_hard_escalation_rules()` stays — it's applied as a Python safety override in the call site

**Concrete changes in `automation_tools.py`:**
- Remove `_analyze_message()` function entirely (replaced by AgentService path)
- Keep `_apply_hard_escalation_rules()` as a standalone function (imported and used in engagement_monitor and dm_monitor)
- Keep `_reply_to_comment()` and `_reply_to_dm()` as-is (Python-side execution)
- Keep `analyze_message_tool`, `reply_to_comment_tool`, `reply_to_dm_tool` definitions in `AUTOMATION_TOOLS` but they are NOT in `ENGAGEMENT_SCOPE_TOOLS` and NOT used in the new `AgentService` path

---

## Step 2 — Scope definitions

**File:** `agent/services/agent_service.py`

**`ENGAGEMENT_SCOPE_TOOLS`** — 6 tools:
```python
ENGAGEMENT_SCOPE_TOOLS = [
    get_post_context,
    get_account_info,
    get_recent_comments,
    get_dm_history,
    get_dm_conversation_context,
    # log_decision — Python-only
]
```

**Imports:** Keep `get_dm_history` and `get_dm_conversation_context` in the import from `tools.supabase_tools`. Remove `analyze_message_tool`, `reply_to_comment_tool`, `reply_to_dm_tool` from the automation tools import — they are no longer in any scope.

**`CONTENT_SCOPE_TOOLS`** — unchanged:
```python
CONTENT_SCOPE_TOOLS = [
    get_post_context,
    get_account_info,
    get_post_performance,
    log_decision,
]
```

**`ATTRIBUTION_SCOPE_TOOLS`** — unchanged:
```python
ATTRIBUTION_SCOPE_TOOLS = [
    get_dm_history,
    get_account_info,
    log_decision,
]
```

---

## Step 3 — New prompt for bind_tools analysis path

**File:** `agent/prompts.py`

New prompt key: `analyze_message_agent`

The prompt must instruct the LLM precisely on each tool's purpose:

```
You are an Instagram engagement analyzer. You have access to these tools.

TOOL PURPOSE (use in this order):
- get_post_context(post_id) — "Get the post this comment is on: caption, likes, comments, engagement_rate, media_type."
- get_account_info(business_account_id) — "Get the account context: username, name, account_type, followers_count."
- get_recent_comments(business_account_id, limit) — "Get the ACCOUNT's recent comment patterns: typical categories, sentiment, engagement quality. Use limit=5. This tells you what kinds of replies this account usually gets — NOT the thread around this specific comment."
- get_dm_history(business_account_id, customer_instagram_id, limit) — "Get prior DM messages for this sender. Use when analyzing a DM or when you need conversation history."
- get_dm_conversation_context(business_account_id, customer_instagram_id) — "Check if the 24-hour reply window is still open for this DM sender."

TASK: Analyze the message below. Fetch context using tools as needed.

MESSAGE:
{message_text}

Analyze and return JSON with:
{
  "category": "general | product_question | complaint | praise | spam | inquiry | ...",  "sentiment": "positive | neutral | negative",
  "priority": "low | medium | high | urgent",
  "intent": "one-line description of what the sender wants",
  "confidence": 0.0-1.0,
  "needs_human": true/false,  "escalation_reason": "if needs_human=true, explain why",
  "suggested_reply": "if not needs_human, write the reply text"
}

ESCALATION RULES (apply these first):
- If the message contains urgent keywords (refund, cancel, broken, emergency, urgent, help) → needs_human=true
- If the message sentiment is negative AND category is complaint → needs_human=true
- If the message is longer than 300 chars AND contains a question mark → needs_human=true
- If the suggested reply is empty → needs_human=true

After applying escalation rules, output the final JSON.
```

`_apply_hard_escalation_rules()` in Python still runs as a safety override after the LLM response.

---

## Step 4 — Migrate `engagement_monitor`

**File:** `agent/scheduler/engagement_monitor.py`

**New instance lifecycle:** One `AgentService` instance per run, shared across all accounts and all comments:

```python
async def engagement_monitor_run():
    run_id = str(uuid_mod.uuid4())
    start = time.time()
    stats = {"processed": 0, "replied": 0, "escalated": 0, "skipped": 0, "errors": 0}

    # One AgentService instance per run — shared across all accounts
    agent = AgentService(scope="engagement")

    accounts = SupabaseService.get_active_business_accounts()
    for account in accounts:
        account_stats = await _process_account(run_id, account, agent)
        ...
```

**New `_process_comment()` with `AgentService`:**

Current flow:
```
get_post_context_by_uuid(media_id)     ← Python pre-fetch (REMOVED)
get_account_info(account_id)           ← Python pre-fetch (REMOVED)
_analyze_message(...)                  ← LLMService.invoke (REMOVED)
_apply_hard_escalation_rules()        ← Python safety overrides (KEEP)
route: escalate / auto-reply / skip
```

New flow:
```python
async def _process_comment(run_id, comment, account, agent):
    # Build prompt — NO pre-fetched context
    # The LLM will call get_post_context, get_account_info via bind_tools()
    prompt = _build_agent_prompt(comment, account)
    # agent is the shared AgentService instance

    # Accumulate streaming response
    accumulated = ""
    async for chunk in agent.astream_analyze(prompt):
        accumulated += chunk

    # Parse JSON from accumulated text
    from services.agent_service import AgentService
    result = AgentService._parse_json_response(accumulated)

    # Python safety override — run after LLM response
    from tools.automation_tools import _apply_hard_escalation_rules
    result = _apply_hard_escalation_rules(result, comment["text"], 0.0)

    # Route — same logic as before
    if result.get("needs_human"):
        return _handle_escalation(...)
    elif result.get("suggested_reply") and result.get("confidence", 0) >= threshold:
        return _handle_auto_reply(...)
    else:
        return _handle_skip(...)
```

**New `_build_agent_prompt()` helper in `engagement_monitor.py`:**
```python
def _build_agent_prompt(comment: dict, account: dict) -> str:
    return PromptService.get("analyze_message_agent").format(
        message_text=comment.get("text", ""),
        message_type="comment",
        sender_username=comment.get("author_username", ""),
        account_id=account.get("id", ""),
        media_id=comment.get("id", ""),
    )
```

**Handler changes:**
- `_handle_auto_reply()` — stays unchanged, calls `_reply_to_comment()` from `automation_tools`
- `_handle_escalation()` — stays unchanged
- `_handle_skip()` — stays unchanged
- State management (`mark_comment_processed`, `DedupService.mark_processed`) — stays unchanged
- Audit logging (`log_decision`) — stays in Python, NOT via `AgentService` tools

---

## Step 5 — Migrate `dm_monitor`

**File:** `agent/scheduler/dm_monitor.py`

Mirror `engagement_monitor` exactly:

```python
async def dm_monitor_run():
    agent = AgentService(scope="engagement")  # shared per run

    accounts = SupabaseService.get_active_business_accounts()
    for account in accounts:
        account_stats = await _process_account(run_id, account, agent)
        ...

async def _process_message(run_id, msg, account, agent):
    prompt = _build_agent_prompt(msg, account, message_type="dm")

    accumulated = ""
    async for chunk in agent.astream_analyze(prompt):
        accumulated += chunk

    result = AgentService._parse_json_response(accumulated)
    result = _apply_hard_escalation_rules(result, msg["message_text"], 0.0)

    # Route — same logic as before
    if result.get("needs_human"):
        return _handle_escalation(...)
    elif result.get("suggested_reply") and result.get("confidence", 0) >= threshold:
        return _handle_auto_reply(...)
    else:
        return _handle_skip(...)
```

**DM-specific prompt additions:**
The `_build_agent_prompt()` function for DM should include `customer_instagram_id` so the LLM can call `get_dm_history(customer_instagram_id)` and `get_dm_conversation_context(customer_instagram_id)`.

---

## Step 6 — Webhook cleanup

**Files:** `agent/routes/webhook_comment.py`, `agent/routes/webhook_dm.py`

Current behavior: webhooks write to Supabase, then call `_analyze_message()` directly.

New behavior: webhooks write to Supabase only. The engagement monitor (which polls Supabase) processes the records via `AgentService`.

**Changes in `webhook_comment.py` and `webhook_dm.py`:**
- Remove import of `_analyze_message` from `automation_tools`
- Remove the `_analyze_message()` call from the webhook pipeline
- Webhook pipeline becomes: write to Supabase → return response → done
- The engagement monitor's next poll picks up the new records

This simplifies the webhook routes significantly — they are pure DB write operations now.

---

## Files to Modify

| File | Changes |
|------|---------|
| `agent/services/agent_service.py` | Update `ENGAGEMENT_SCOPE_TOOLS` to 6 tools. Remove `analyze_message_tool`, `reply_to_comment_tool`, `reply_to_dm_tool` from imports. |
| `agent/tools/automation_tools.py` | Remove `_analyze_message()` function entirely. Keep `_apply_hard_escalation_rules()`, `_reply_to_comment()`, `_reply_to_dm()` as standalone functions. |
| `agent/scheduler/engagement_monitor.py` | Add `AgentService` import. Create one `agent = AgentService(scope="engagement")` per run. New `_build_agent_prompt()` helper. Replace `_process_comment()` to use `agent.astream_analyze()`, accumulate, parse, apply hard rules, route. Keep handlers and state management. |
| `agent/scheduler/dm_monitor.py` | Same pattern as engagement_monitor. |
| `agent/routes/webhook_comment.py` | Remove `_analyze_message()` call. Pipeline writes to Supabase only. |
| `agent/routes/webhook_dm.py` | Remove `_analyze_message()` call. Pipeline writes to Supabase only. |
| `agent/prompts.py` | New prompt `analyze_message_agent` with explicit tool purpose instructions and escalation rules. |

---

## Files NOT Modified

| File | Reason |
|------|--------|
| `agent/tools/supabase_tools.py` | No changes needed |
| `agent/tools/content_tools.py` | Separate migration |
| `agent/tools/attribution_tools.py` | Separate migration |
| `agent/tools/analytics_tools.py` | Separate migration |
| `agent/services/oversight_brain.py` | Separate domain |
| `agent/tools/oversight_tools.py` | Separate domain |

---

## Verification

1. **Scope check:** `python -c "from services.agent_service import AgentService; a = AgentService(scope='engagement'); print(list(a._tool_map.keys()))"` → shows 6 tool names
2. **No analyze_message in scope:** `python -c "from services.agent_service import AgentService; a = AgentService(scope='engagement'); assert 'analyze_message' not in a._tool_map"` → passes
3. **No recursion:** `python -c "from tools.automation_tools import _reply_to_comment; print('ok')"` → `_reply_to_comment` is standalone, no LLM call
4. **Stream accumulation:** Post a test comment → engagement monitor calls `agent.astream_analyze()`, accumulates tokens, parses JSON, applies `_apply_hard_escalation_rules()`, routes
5. **One instance per run:** Logs show `AgentService initialized (scope=engagement, tools=6)` once per engagement_monitor_run cycle, not once per comment
6. **Webhook simplification:** Webhook writes to Supabase, returns immediately, engagement monitor picks it up on next poll
7. **Dedup preserved:** `DedupService.mark_processed()` still called after each comment — unchanged
8. **Metrics:** `TOOL_CALLS` increments for `get_post_context`, `get_account_info`, `get_recent_comments`, `get_dm_history`, `get_dm_conversation_context` when called through `bind_tools()`
