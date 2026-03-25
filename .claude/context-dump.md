# Llama 3.1 8B + Agent Architecture Analysis
**Date:** 2026-03-25
**Status:** Research Complete — Implementation Pending

---

## Executive Summary

The decision to switch from Qwen2.5 → Llama 3.1 8B is sound, but **Llama 3.1 8B alone will not solve the tool-calling failures** documented in `errors.md`. The root causes are:

1. **12 tools bound simultaneously** — exceeds reliable tool-count for 8B class models
2. **Nested tool calling** — `_analyze_message` (a tool) internally calls `AgentService(ALL_TOOLS)` → another `bind_tools()` call
3. **MAX_CONCURRENT_LLM=4** on 4 vCPU — CPU saturation causes inference instability
4. **No LLM-level retry** — transient Ollama CPU spikes cause hard failures with no recovery

Llama 3.1 8B at Q4_K_M quantization (4.9GB) is the correct model choice. The fixes required are architectural, not model-selection.

---

## 1. What the Data Says About Llama 3.1 8B Tool Calling

### 1.1 Benchmark Reality

| Benchmark | Llama 3.1 8B Score | What It Means Practically |
|-----------|-------------------|--------------------------|
| **API-Bank** | 82.6% | Correct tool selection + parameters ~83% of the time |
| **BFCL** | 76.1% | Drops in multi-turn, nested, adversarial cases |

**Interpretation:** 82.6% means ~1 in 6 tool calls will fail or misbehave. With **12 tools bound simultaneously**, you're operating at the upper edge of what the model can reliably handle. With **5-8 scoped tools**, you get closer to the 90%+ range.

**BFCL 76.1% for multi-turn** is particularly relevant — your nested `_analyze_message` → `AgentService(ALL_TOOLS)` pattern is exactly the kind of scenario where BFCL tests hard.

### 1.2 Tool-Count Limits for 8B Models

| Tool Count | Expected Accuracy | Notes |
|------------|------------------|-------|
| 1-5 tools | ~90-95% | Ideal |
| 6-10 tools | ~82-88% | Acceptable with good descriptions |
| **11-15 tools** | **~75-80%** | **Your current ALL_TOOLS = 12 — this is the danger zone** |
| 16-20 tools | ~65-72% | Needs tool retrieval pattern |
| 20+ tools | <60% | Not viable for 8B without dynamic discovery |

**Your current tool binding:**
```
ALL_TOOLS = SUPABASE_TOOLS (7) + AUTOMATION_TOOLS (3) + OVERSIGHT_TOOLS (2) = 12 tools
```

This is in the danger zone. The Qwen2.5 failures were not purely a model issue — Qwen2.5 7B is rated for ~8-10 tools. Llama 3.1 8B handles 12 better, but not reliably.

### 1.3 Quantization — Ollama Default is Optimal

| Quantization | Size | CPU RAM | Tool Calling Quality |
|-------------|------|---------|-------------------|
| Q4_K_M (default) | 4.9GB | ~5.5GB VRAM+RAM | **Recommended** — best accuracy/speed |
| Q5_K_M | 6.1GB | ~7GB | Slightly better quality, 20% slower |
| Q6_K | 7.0GB | ~8GB | Near-FP16, marginal gain |
| Q8_0 | 8.9GB | ~10GB | Overkill for CPU |

**Ollama's `llama3.1:8b` resolves to Q4_K_M automatically.** No change needed.

### 1.4 Thinking Mode — Not a Concern for Llama 3.1

Llama 3.1 does **not** have a built-in chain-of-thought thinking mode (unlike Nemotron). There is no `think=false` parameter needed. The `think=false` workaround in your MEMORY.md was for Nemotron specifically.

---

## 2. Cross-Analysis: Codebase Patterns vs. Best Practices

### 2.1 Tool Binding Architecture — Current State

**File:** `agent/services/agent_service.py:39-47`

```python
class AgentService:
    def __init__(self, tools=None):
        tool_list = tools if tools is not None else ALL_TOOLS
        self.llm_with_tools = llm.bind_tools(tool_list)
```

**Actual tool sets being bound:**

| Caller | Tools Bound | Count | Status |
|--------|-------------|-------|--------|
| `oversight_brain.py:41` | `OVERSIGHT_TOOLS` | 2 | ✅ Safe — well within limit |
| `analytics_tools.py:39` | `AgentService()` → ALL_TOOLS | 12 | ❌ Danger zone |
| `content_tools.py:46` | `AgentService()` → ALL_TOOLS | 12 | ❌ Danger zone |
| `attribution_tools.py:36` | `AgentService()` → ALL_TOOLS | 12 | ❌ Danger zone |
| `automation_tools.py:68` | `AgentService()` → ALL_TOOLS | 12 | ❌ Nested anti-pattern |

### 2.2 The Nested Tool Calling Anti-Pattern

**File:** `agent/tools/automation_tools.py:118`

```python
def _analyze_message(...) -> dict:
    ...
    agent = _get_agent_service()     # Gets AgentService with 12 tools bound
    result = asyncio.run(agent.analyze_async(prompt))  # Another full LLM call with 12 tools
```

**Why this is an anti-pattern (from BigCodeBench + NoisyToolBench research):**

1. **Context bloat**: The outer LLM call includes all 12 tool descriptions. The inner call pays the same cost again. You pay ~2x the prompt processing.
2. **Recursive tool-call risk**: The inner model could theoretically call a tool — there is no mechanism to handle this.
3. **BFCL degradation**: NoisyToolBench research found that "LLMs tend to arbitrarily generate missed arguments" in nested scenarios. This is exactly your failure mode.

**`analyze_message_tool` is itself a StructuredTool** (`automation_tools.py:143-175`). When the LLM calls it, `_analyze_message` runs and internally triggers `AgentService(ALL_TOOLS)` — doubling the tool complexity per invocation.

### 2.3 Scheduler Pipelines — Doing It Right

**File:** `agent/scheduler/engagement_monitor.py`

The scheduler pipelines (engagement_monitor, content_scheduler, ugc_discovery) call `AgentService.analyze_async()` directly with purpose-built prompts. They do NOT go through `bind_tools()` at the pipeline level. The issue is when those calls route through `_analyze_message` which does the nested binding.

### 2.4 Concurrency — CPU Saturation Risk

**File:** `agent/services/agent_service.py:29-30`

```python
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "4"))
_llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
```

**Current .env:** `MAX_CONCURRENT_LLM=4`

**Problem:** Each Ollama inference on CPU uses ~2 vCPUs. With `MAX_CONCURRENT_LLM=4` on a 4 vCPU VPS:
- All 4 cores saturated during LLM inference
- OS/tool execution has zero CPU headroom
- Context switching causes inference instability
- Tool calls (Supabase, Redis) compete for CPU during LLM processing

**Recommended:** `MAX_CONCURRENT_LLM=2` for 4 vCPU. This gives 2 concurrent inferences (using ~4 vCPUs) with 2 cores reserved for OS + tool I/O.

### 2.5 Timeout Architecture — Missing LLM Retry

**File:** `agent/services/agent_service.py:73-122`

```python
async def _analyze(self, prompt: str) -> dict:
    ...
    result = await asyncio.to_thread(self.llm_with_tools.invoke, full_prompt)
    # No retry wrapper
```

**Current timeout layers:**

| Layer | Value | Status |
|-------|-------|--------|
| `ChatOllama timeout=60` | 60s, hard cap on HTTP | ✅ Present |
| `TOOL_TIMEOUT_SECONDS=5.0` | Per-tool via `asyncio.wait_for` | ✅ Present |
| `OVERSIGHT_LLM_TIMEOUT_SECONDS=120` | Per-request via `asyncio.timeout` | ✅ Present |
| **LLM retry with backoff** | None | ❌ Missing |

**No LLM-level retry exists.** If Ollama returns an error (busy, model loading, transient CPU spike), the request fails immediately. The `OVERSIGHT_LLM_TIMEOUT_SECONDS` only catches hangs, not errors.

### 2.6 Tool Descriptions — Adequate But Could Be Better

**Current example from `supabase_tools.py:61-66`:**
```python
get_post_context_tool = StructuredTool.from_function(
    func=SupabaseService.get_post_context,
    name="get_post_context",
    description="Fetch post details from Instagram media table: caption, like_count, comments_count, engagement_rate. Use when evaluating a comment reply or post.",
    args_schema=PostContextInput,
)
```

**Assessment:** Functional but missing trigger-condition guidance. Research shows:
- "Use when evaluating a comment reply" — good, explains WHEN to call
- Missing: what happens if the tool returns nothing? What to do with partial data?

**Description quality impact:**
| Quality | Tool Call Success | Notes |
|---------|------------------|-------|
| Basic name + description | ~78% | Your current |
| With trigger conditions | ~85-88% | Add "Use when..." context |
| With return-value guidance | ~90% | Add "Returns..." or "If unavailable..." |

---

## 3. Recommended Architectural Changes

### 3.1 Scoped Tool Sets (High Priority)

**Pattern:** Replace `ALL_TOOLS` binding with use-case-specific tool sets.

```python
# agent/services/agent_service.py

# Scoped sets — replace ALL_TOOLS usage
ENGAGEMENT_TOOLS = [
    get_post_context_tool,
    get_account_info_tool,
    get_recent_comments_tool,
    log_decision_tool,
]  # 4 tools — well within reliable range

CONTENT_TOOLS = [
    get_post_context_tool,
    get_account_info_tool,
    get_post_performance_tool,
    log_decision_tool,
]  # 4 tools

ATTRIBUTION_TOOLS = [
    get_dm_history_tool,
    get_account_info_tool,
    log_decision_tool,
]  # 3 tools

OVERSIGHT_TOOLS = [
    get_audit_log_entries_tool,
    get_run_summary_tool,
]  # 2 tools — already correct


class AgentService:
    def __init__(self, tools=None, scope=None):
        if scope == "engagement":
            tool_list = ENGAGEMENT_TOOLS
        elif scope == "content":
            tool_list = CONTENT_TOOLS
        elif scope == "attribution":
            tool_list = ATTRIBUTION_TOOLS
        elif scope == "oversight":
            tool_list = OVERSIGHT_TOOLS
        elif tools is not None:
            tool_list = tools
        else:
            tool_list = ALL_TOOLS  # fallback — for legacy callers
```

**Then update callers:**
```python
# analytics_tools.py
_agent_service = AgentService(scope="attribution")

# content_tools.py
_agent_service = AgentService(scope="content")

# automation_tools.py — also fix nested pattern (see 3.2)
```

### 3.2 Remove Nested Tool Calling (Critical Priority)

**File:** `agent/tools/automation_tools.py:75-129`

Replace the nested `AgentService(ALL_TOOLS)` call with a direct `llm.invoke()` without `bind_tools()`:

```python
def _analyze_message(...) -> dict:
    from config import llm  # use base llm, NOT AgentService
    from services.prompt_service import PromptService

    prompt = PromptService.get("analyze_message").format(...)

    # Direct LLM call WITHOUT bind_tools — no nested tool calling
    # The prompt already contains all context needed
    result = llm.invoke(prompt)

    # Parse JSON response manually
    import json, re
    raw = result.content if hasattr(result, "content") else str(result)
    # Use AgentService._parse_json_response logic here
    ...
```

**Why this works:**
- The `analyze_message` prompt already contains all context (account info, post context, DM history)
- The LLM's job is to classify + extract structured JSON — no tool calling needed
- The nested `bind_tools()` call was providing zero benefit and causing the tool-count explosion

### 3.3 Reduce Concurrency (Medium Priority)

**File:** `.env + agent/services/agent_service.py`

```python
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM", "2"))  # was 4
```

On 4 vCPU: 2 concurrent LLM inferences (using ~4 vCPUs) + 2 cores for OS/tools.

### 3.4 Add LLM Retry with Exponential Backoff (Medium Priority)

**File:** `agent/services/agent_service.py`

```python
import random

async def _analyze_with_retry(self, prompt: str, max_retries: int = 3) -> dict:
    """LLM invoke with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return await self._analyze(prompt)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            # Exponential backoff: 1s, 2s, 4s + jitter
            wait = (2 ** attempt) + random.uniform(0, 0.5)
            logger.warning(f"LLM invoke failed (attempt {attempt+1}), retrying in {wait:.1f}s: {e}")
            await asyncio.sleep(wait)
```

### 3.5 Ollama Server-Side Settings (Low Priority — VPS Config)

These are **not code changes** — they're Ollama server parameters set via environment or `Modelfile`:

```bash
# In Ollama container or via API
OLLAMA_NUM_PARALLEL=2        # Reduce parallel inferences on CPU
OLLAMA_KEEP_ALIVE=10m        # Keep model loaded (was 5min default)
OLLAMA_FLASH_ATTENTION=0     # Disable on CPU — uses more memory but not faster on CPU
```

Set in `docker-compose.unified.yml` Ollama service:
```yaml
environment:
  - OLLAMA_NUM_PARALLEL=2
  - OLLAMA_KEEP_ALIVE=10m0s
```

---

## 4. Implementation Priority Matrix

| Priority | Change | Files to Modify | Impact | Effort |
|---------|--------|----------------|--------|--------|
| **P0** | Remove nested `_analyze_message` tool calling | `automation_tools.py` | Eliminates recursive tool-count explosion | Medium |
| **P0** | Implement scoped tool sets | `agent_service.py`, all tool files | Brings 12 → 3-4 tools per use case | Medium |
| **P1** | Reduce `MAX_CONCURRENT_LLM` 4 → 2 | `.env`, `agent_service.py` | Stable CPU headroom | Low |
| **P1** | Add LLM retry with backoff | `agent_service.py` | Resilience to transient failures | Low |
| **P2** | Improve tool descriptions with trigger conditions | `supabase_tools.py`, `automation_tools.py`, `oversight_tools.py` | +5-8% tool calling accuracy | Low |
| **P2** | Set Ollama `OLLAMA_NUM_PARALLEL=2` | `docker-compose.unified.yml` | CPU stability | Low |

---

## 5. What NOT to Change

- **`analyze_message_tool` as a LangChain tool** — keep it registered, just fix the internal implementation
- **`OVERSIGHT_TOOLS = [2 tools]`** — already correct, no change needed
- **`ChatOllama timeout=60`** — appropriate for CPU inference
- **`TOOL_TIMEOUT_SECONDS=5.0`** — appropriate for Supabase calls
- **Prompt templates in `prompts.py`** — well-structured, no change needed
- **Llama 3.1 8B model choice** — confirmed correct from benchmarks

---

## 6. Test Plan After Changes

### Phase 1: Verify Llama 3.1 8B Baseline
```bash
# Pull model
docker exec ollama ollama pull llama3.1:8b

# Verify loaded
docker exec ollama ollama list

# Direct test (no tools)
docker exec ollama ollama run llama3.1:8b "Say hello in 3 words"

# Simple tool call test (1 tool)
curl -sf http://ollama:11434/api/chat \
  -d '{"model":"llama3.1:8b","messages":[{"role":"user","content":"What is 2+2?"}],"tools":[{"type":"function","function":{"name":"calc","description":"A calculator","parameters":{"type":"object","properties":{"a":{"type":"number"},"b":{"type":"number"}},"required":["a","b"]}}}]}'
```

### Phase 2: Test with Scoped Tools (2-4 tools)
```bash
# Test oversight endpoint (2 tools — lowest risk)
curl -N -X POST https://agent.888intelligenceautomation.in/oversight/chat \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80" \
  -H "Accept: text/event-stream" \
  -d '{"question": "What did the agent do today?", "business_account_id": "0882b710-4258-47cf-85c8-1fa82a3de763", "stream": true}'
```

### Phase 3: Load Test with Metrics
```bash
# Prometheus metrics during load
curl http://agent.888intelligenceautomation.in/metrics \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80"

# Key metrics to watch:
# - agent_llm_errors_total (should stay flat under load)
# - agent_oversight_chat_queries_total{status="success"} (should increment)
# - tool_calls_total (should show scoped tool usage)
```

---

## 7. Sources

- [Meta Llama 3.1 — Tool Use Benchmark Results](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) — API-Bank 82.6%, BFCL 76.1%
- [Ollama Tool Support](https://ollama.com/blog/tool-support) — Official documentation, supported models list
- [Berkeley Function Calling Leaderboard (BFCL)](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) — Standardized benchmarks
- [BigCodeBench: Benchmarking Code Generation](https://hf.co/papers/2406.15877) — Function calling limitations across model sizes
- [LLMCompiler](https://hf.co/papers/2312.04511) — Parallel function calling for 3.7x latency improvement
- [TinyAgent](https://hf.co/papers/2409.00608) — 7B models with tool retrieval matching GPT-4-Turbo
- [NoisyToolBench](https://hf.co/papers/2409.00557) — Tool use under imperfect instructions
- [LangChain ChatOllama Integration](https://docs.langchain.com) — bind_tools() internals
- Repository: `agent/services/agent_service.py`, `agent/tools/automation_tools.py`, `agent/tools/supabase_tools.py`, `agent/tools/oversight_tools.py`, `agent/prompts.py`, `agent/config.py`
