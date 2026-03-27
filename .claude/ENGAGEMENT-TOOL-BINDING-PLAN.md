# Engagement Tool Binding Plan
## Supabase Tools → AgentService Backbone

---

## Context

The `AgentService` with `llm.bind_tools()` infrastructure exists but is never instantiated in production. Every pipeline calls `LLMService.invoke(llm_instance=llm)` directly — the LLM never sees or calls any tool.

This plan migrates the engagement monitors (comment + DM) to route LLM calls through `AgentService.bind_tools()`.

---

## Architectural Principle

**Read tools go through `bind_tools()` — LLM decides when to fetch more context.**
**Execution tools stay Python-side — deterministic, no double-execution.**

```
engagement_monitor.py
│
├── Python pre-fetches what it already has (fast, reliable)
│   post_ctx = SupabaseService.get_post_context_by_uuid(media_id)
│
├── Prompt goes to AgentService.astream_analyze()
│   └── llm.bind_tools(ENGAGEMENT_SCOPE_TOOLS) — LLM CAN call:
│       get_post_context       ← fetch post details
│       get_account_info       ← fetch account details
│       get_recent_comments    ← fetch account-level patterns
│       get_dm_history         ← fetch DM conversation history
│       get_dm_conversation_context ← fetch conversation metadata
│
├── LLM has two choices:
│   ├── CHOICE A: Enough context → return JSON directly (no tools called)
│   └── CHOICE B: Need more data → call tool → result injected → final JSON
│
├── Python receives JSON → _apply_hard_escalation_rules() (safety override)
├── Route: escalate / auto-reply / skip
└── Execution: _reply_to_comment() → OutboundQueue (Python-side)
```

---

## What Stays the Same

- `_analyze_message()` in `automation_tools.py` — unchanged, webhooks still use it
- `_apply_hard_escalation_rules()` — unchanged, runs after LLM as safety net
- `_reply_to_comment()` / `_reply_to_dm()` — unchanged, called by handlers
- All handler functions: `_handle_escalation()`, `_handle_auto_reply()`, `_handle_skip()`
- All state management: `mark_comment_processed()`, `DedupService.mark_processed()`, `log_decision()`
- Prometheus metrics, batch logging — unchanged

---

## Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | `analyze_message_tool` REMOVED from `ENGAGEMENT_SCOPE_TOOLS` | Recursion loop — tool calls LLM which calls tool |
| D2 | `reply_to_comment_tool` / `reply_to_dm_tool` REMOVED from scope | Execution stays Python-side via OutboundQueue. No double-execution possible. |
| D3 | `log_decision` REMOVED from `ENGAGEMENT_SCOPE_TOOLS` | Python-side audit only. No double-logging. |
| D4 | `get_dm_history`, `get_dm_conversation_context` ADDED to scope | LLM can fetch DM conversation context directly |
| D5 | `_analyze_message()` stays unchanged in `automation_tools.py` | Webhooks still use it during migration. Backward compatible. |
| D6 | `AgentService` instance created once per run, not per comment | Avoids N `bind_tools()` calls to Ollama per batch |

---

## Final `ENGAGEMENT_SCOPE_TOOLS` (5 tools)

```python
ENGAGEMENT_SCOPE_TOOLS = [
    # Read tools — LLM calls via bind_tools() when it needs more context
    get_post_context,               # fetch post details by media ID
    get_account_info,               # fetch brand account info
    get_recent_comments,           # fetch account-level comment patterns
    get_dm_history,               # fetch DM conversation history
    get_dm_conversation_context,   # fetch conversation metadata
    # Execution tools — NOT in scope (Python-side OutboundQueue)
    # log_decision — NOT in scope (Python-side audit only)
]
```

---

## Step 1 — Fix `agent_service.py` Scopes

**File:** `agent/services/agent_service.py`

### Changes:

1. **Update imports** — remove `analyze_message_tool`, `reply_to_comment_tool`, `reply_to_dm_tool` from automation_tools import. Add `get_dm_history`, `get_dm_conversation_context` from supabase_tools import.

2. **Update `ENGAGEMENT_SCOPE_TOOLS`** — final 5-tool scope as above.

3. **`CONTENT_SCOPE_TOOLS`** — unchanged (already correct: `get_post_context`, `get_account_info`, `get_post_performance`, `log_decision`).

4. **`ATTRIBUTION_SCOPE_TOOLS`** — unchanged (already correct: `get_dm_history`, `get_account_info`, `log_decision`).

**Before:**
```python
from tools.automation_tools import (
    analyze_message_tool,
    reply_to_comment_tool,
    reply_to_dm_tool,
)

ENGAGEMENT_SCOPE_TOOLS = [
    get_post_context,
    get_account_info,
    get_recent_comments,
    log_decision,
    analyze_message_tool,       # ← recursion risk
    reply_to_comment_tool,        # ← execution stays Python-side
    reply_to_dm_tool,           # ← execution stays Python-side
]
```

**After:**
```python
# automation_tools imports removed

ENGAGEMENT_SCOPE_TOOLS = [
    get_post_context,
    get_account_info,
    get_recent_comments,
    get_dm_history,
    get_dm_conversation_context,
    # Execution: Python-side OutboundQueue (no tool binding needed)
    # Audit: Python-side log_decision calls (no double-logging)
]
```

---

## Step 2 — Add `analyze_message_agent` Prompt

**File:** `agent/prompts.py`

### New prompt key: `analyze_message_agent`

Added to `PROMPTS` dict. Tells the LLM it has tools available and should use them when pre-injected context is insufficient.

**Structure:**
```
SYSTEM ROLE: You are the customer service brain for an Instagram business account.
You have tools to fetch additional context. Use them if the context below is insufficient.

MESSAGE TO ANALYZE:
- Type: {message_type}
- From: @{sender_username}
- Text: "{message_text}"

TOOLS AVAILABLE (describe name, params, purpose):
- get_post_context(post_id) — fetch post details
- get_account_info(business_account_id) — fetch brand account info
- get_recent_comments(business_account_id, limit) — fetch account's recent comments for pattern context
- get_dm_history(sender_id, business_account_id) — fetch prior DM conversations
- get_dm_conversation_context(sender_id, business_account_id) — fetch conversation metadata

INSTRUCTIONS:
1. If account context is missing, call get_account_info
2. If post context is insufficient, call get_post_context
3. If analyzing a DM with prior history, call get_dm_history or get_dm_conversation_context
4. Classify: category, sentiment, priority, intent, confidence
5. Decide: needs_human? suggested_reply?
6. Output ONLY valid JSON

CLASSIFICATION CATEGORIES — same as existing prompt
PRIORITY RULES — same as existing prompt
ESCALATION TRIGGERS — same as existing prompt
REPLY GUIDELINES — same as existing prompt
FEW-SHOT EXAMPLES — same as existing prompt (4 examples)

OUTPUT FORMAT — same JSON structure as existing prompt
```

**The existing `analyze_message` prompt is kept unchanged** — webhooks still use it during migration.

---

## Step 3 — Migrate `engagement_monitor.py`

**File:** `agent/scheduler/engagement_monitor.py`

### Changes:

**1. Add imports:**
```python
from services.agent_service import AgentService
from services.prompt_service import PromptService
```

**2. Create `AgentService` instance — once per run, not per comment:**

Module-level singleton (lazy initialization):
```python
# At module level, after existing imports
_agent_instance = None

def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentService(scope="engagement")
    return _agent_instance
```

Or create inside `engagement_monitor_run()` and pass to `_process_account()`:
```python
async def engagement_monitor_run():
    agent = AgentService(scope="engagement")  # one per run
    for account in accounts:
        account_stats = await _process_account(run_id, account, agent)
```

Pass `agent` down to `_process_comment()` via semaphore-wrapped task.

**3. In `_process_comment()` — replace `_analyze_message()` call:**

**Before:**
```python
# 1. Fetch post context
post_ctx = SupabaseService.get_post_context_by_uuid(media_id)

# 2. Analyze via _analyze_message (LLM + hard rules)
analysis = await _analyze_message(
    message_text=comment_text,
    message_type="comment",
    sender_username=author,
    account_context=account,
    post_context=post_ctx,
    dm_history=None,
    customer_lifetime_value=0.0,
)
```

**After:**
```python
# 1. Fetch post context (Python — fast, reliable)
post_ctx = SupabaseService.get_post_context_by_uuid(media_id)

# 2. Build analysis prompt with pre-injected context
prompt = PromptService.get("analyze_message_agent").format(
    message_type="comment",
    sender_username=author,
    message_text=comment_text[:500],
    # Pre-inject account context (Python already has it)
    account_username=account.get("username", "unknown"),
    account_type=account.get("account_type", "business"),
    post_caption=(post_ctx.get("caption", "N/A")[:200] if post_ctx else "N/A"),
    post_engagement=(post_ctx.get("engagement_rate", 0) if post_ctx else 0),
    dm_history_summary="N/A for comments",
    customer_value=0.0,
)

# 3. Stream through AgentService (LLM with bind_tools)
# LLM may call get_post_context, get_account_info, etc.
# Or may return JSON directly if pre-injected context is sufficient
accumulated = ""
async for chunk in _get_agent().astream_analyze(prompt):
    accumulated += chunk

# 4. Parse + apply safety overrides
analysis = AgentService._parse_json_response(accumulated)
analysis = _apply_hard_escalation_rules(analysis, comment_text, 0.0)
```

**4. Everything after `analysis` — unchanged:**
```python
if analysis.get("needs_human"):
    return _handle_escalation(run_id, comment, account, analysis)
# ... rest of routing logic unchanged
```

**5. Handler functions — unchanged:**
- `_handle_escalation()` — unchanged
- `_handle_auto_reply()` — `_reply_to_comment()` still called directly
- `_handle_skip()` — unchanged
- `_log_execution_outcome()` — unchanged
- `_log_comment_error()` — unchanged
- `_log_batch_summary()` — unchanged

---

## Step 4 — Migrate `dm_monitor.py`

**File:** `agent/scheduler/dm_monitor.py`

### Changes:

**1. Add imports:**
```python
from services.agent_service import AgentService
from services.prompt_service import PromptService
```

**2. Create `AgentService` instance — once per run, passed to `_process_message()`**

**3. In `_process_message()` — replace `_analyze_message()` call:**

**Before:**
```python
dm_history = SupabaseService.get_dm_history(customer_ig_id, account.get("id", ""))

analysis = await _analyze_message(
    message_text=message_text,
    message_type="dm",
    sender_username=sender_username,
    account_context=account,
    post_context=None,
    dm_history=dm_history,
    customer_lifetime_value=0.0,
)
```

**After:**
```python
dm_history = SupabaseService.get_dm_history(customer_ig_id, account.get("id", ""))

# Format DM history for prompt
dm_history_summary = "No prior messages"
if dm_history:
    lines = []
    for msg in dm_history[:5]:
        direction = msg.get("direction", "?")
        text = msg.get("message_text", "")[:80]
        lines.append(f"[{direction}] {text}")
    dm_history_summary = "\n".join(lines)

prompt = PromptService.get("analyze_message_agent").format(
    message_type="dm",
    sender_username=sender_username,
    message_text=message_text[:500],
    account_username=account.get("username", "unknown"),
    account_type=account.get("account_type", "business"),
    post_caption="N/A for DMs",
    post_engagement=0,
    dm_history_summary=dm_history_summary,
    customer_value=0.0,
)

accumulated = ""
async for chunk in _get_agent().astream_analyze(prompt):
    accumulated += chunk

analysis = AgentService._parse_json_response(accumulated)
analysis = _apply_hard_escalation_rules(analysis, message_text, 0.0)
```

**4. `_reply_to_dm()` still called by `_handle_auto_reply()` — unchanged.**

---

## Step 5 — Verification

**1. Import check:**
```bash
python -c "from services.agent_service import AgentService; a = AgentService(scope='engagement'); print(sorted(a._tool_map.keys()))"
```
Expected output (5 tool names, alphabetically):
```
['get_account_info', 'get_dm_conversation_context', 'get_dm_history', 'get_post_context', 'get_recent_comments']
```

**2. No recursion in `_analyze_message`:**
```bash
python -c "from tools.automation_tools import _analyze_message; import inspect; src = inspect.getsource(_analyze_message); assert 'LLMService' not in src, 'LLMService still referenced'; print('clean')"
```
Expected: `clean` (no LLMService reference — it should still be there for backward compat with webhooks actually, so this check is wrong — just verify the function still works)

**3. Engagement monitor dry run** (with test comment):
- Logs show `AgentService initialized (scope=engagement, tools=5)`
- LLM calls `get_post_context` or `get_account_info` via tool call (if it needs them)
- OR: LLM returns JSON directly (if pre-injected context is sufficient)
- `TOOL_CALLS` Prometheus metric increments for called tools

**4. Hard rules still fire:**
- Post a comment with VIP indicator → `_apply_hard_escalation_rules()` still overrides in Python after LLM response

**5. Dedup still works:**
- Redis dedup keys still set via `DedupService.mark_processed()`

**6. No double-logging:**
- `log_decision()` called only from Python handlers, not from LLM tool call

---

## Files to Modify

| File | Changes |
|------|---------|
| `agent/services/agent_service.py` | Update `ENGAGEMENT_SCOPE_TOOLS` to 5 tools. Remove `analyze_message_tool`, `reply_to_comment_tool`, `reply_to_dm_tool`, `log_decision`. Add `get_dm_history`, `get_dm_conversation_context`. |
| `agent/prompts.py` | Add `analyze_message_agent` prompt key. Keep `analyze_message` unchanged for webhooks. |
| `agent/scheduler/engagement_monitor.py` | Add `AgentService` + `PromptService` imports. Create instance once per run. Replace `_analyze_message()` call with `AgentService.astream_analyze()` → accumulate → parse → apply hard rules. Keep all handlers + state management. |
| `agent/scheduler/dm_monitor.py` | Same pattern as engagement_monitor. |

## Files NOT Modified

| File | Reason |
|------|--------|
| `agent/tools/automation_tools.py` | `_analyze_message()` unchanged for webhook backward compat. `_apply_hard_escalation_rules()` unchanged. `_reply_to_comment()` / `_reply_to_dm()` unchanged. |
| `agent/tools/supabase_tools.py` | No changes needed. |
| `agent/services/oversight_brain.py` | Separate domain. |
| `agent/routes/webhook_*.py` | Still use old `_analyze_message()` path during migration. |

---

## Rollback Plan

If something breaks:
1. Revert `engagement_monitor.py` and `dm_monitor.py` to call `_analyze_message()` directly
2. Revert `agent_service.py` `ENGAGEMENT_SCOPE_TOOLS` to previous state
3. `prompts.py` `analyze_message_agent` can stay (unused) until cleanup
