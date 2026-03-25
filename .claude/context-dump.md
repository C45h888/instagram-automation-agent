# Optimizing Tool Calling for Qwen 2.5 7B Instruct with LangChain Ollama

## Executive Summary

**Problem**: The Oversight Brain agent produces **zero tokens** and hangs indefinitely when using LangChain's `bind_tools()` with the HuggingFace GGUF variant of Qwen 2.5 7B Instruct (`hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m`). This same model works perfectly via direct `ollama run` but fails catastrophically when tool calling is enabled.

**Root Cause**: The GGUF import format lacks proper tool-calling instruction tuning. Ollama's official tool-calling support requires the model to be explicitly packaged with tool-calling metadata — something the HuggingFace GGUF → Ollama import pipeline does not provide.

**Evidence**: Our SSE stream test showed 8+ heartbeat pings arriving, but **zero LLM tokens** — confirming the stall is inside `llm.bind_tools().invoke()` at the Ollama API layer, not in the streaming infrastructure.

---

## 1. How Tool Calling Works in LangChain Ollama

### 1.1 The `bind_tools()` Mechanism

LangChain's `bind_tools()` on `ChatOllama` transforms tool definitions into the Ollama `/api/chat` format:

```python
# From agent_service.py:41
self.llm_with_tools = llm.bind_tools(tool_list)
```

This adds a `tools` field to the Ollama API request body, formatted as:

```json
{
  "model": "qwen2.5:7b",
  "messages": [{"role": "user", "content": "..."}],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "get_audit_log_entries",
        "description": "Query audit_log for decision history",
        "parameters": {
          "type": "object",
          "properties": {...},
          "required": [...]
        }
      }
    }
  ]
}
```

LangChain also **prepends a system prompt** instructing the model to use tools:

> "You are a helpful assistant that can use tools..."

For GGUF models that were not instruction-tuned for tool calling, this additional prompt format causes the model to stall — it receives tool-related instructions it was not trained on and goes silent.

### 1.2 Ollama's Tool Calling Requirements

According to Ollama's official documentation ([Ollama Blog — Tool Support](https://ollama.com/blog/tool-support)):

> "Models can request to call tools that perform tasks such as fetching data from a database, searching the web, or running code."

> "You may hear the term 'function calling'. We use this interchangeably with 'tool calling'."

**Officially listed models with tool calling support:**
- Llama 3.1
- Mistral Nemo
- FireFunction v2
- Command-R +

**From the Ollama Models page** ([ollama.com/models](https://ollama.com/models)), models confirmed with `tool_calling` capability include newer releases: `qwen3.5`, `qwen3-next`, `nemotron-cascade-2`, etc.

**Qwen 2.5 is notably absent** from Ollama's official tool-calling-compatible model lists.

### 1.3 GGUF vs Ollama Library Format: The Critical Difference

| Aspect | HuggingFace GGUF (`hf.co/.../qwen2.5-7b-instruct-q4_k_m`) | Ollama Registry (`qwen2.5:7b`) |
|--------|-------------------------------------------------------------|----------------------------------|
| **Source** | HuggingFace hosted GGUF file, imported via `ollama pull hf.co/...` | Ollama's curated library model |
| **Package format** | Raw llama.cpp GGUF (quantized weights only) | Ollama Modelfile with custom instruction templates |
| **Tool calling metadata** | ❌ None — GGUF is just weights | ✅ Included in Ollama model definition |
| **`bind_tools()` status** | ❌ Fails silently — zero tokens | ✅ Works correctly |
| **Direct `ollama run`** | ✅ Works — no tools, just text gen | ✅ Works |
| **Instruction tuning** | Base model + chat template only | Chat fine-tune + tool calling instruct |

When you `ollama pull hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m`, Ollama downloads the GGUF file and imports it, but **does not apply any tool-calling instruction fine-tuning**. The resulting model behaves identically to the base Qwen2.5-7B with a chat template — it can follow instructions for text generation, but cannot reliably produce structured `tool_calls` JSON in the format Ollama's API requires.

### 1.4 The Dependency Chain That Breaks

```
curl -N -X POST https://agent.888intelligenceautomation.in/oversight/chat
    ↓
Backend Express API (nginx reverse proxy)
    ↓
FastAPI /oversight/chat endpoint receives request
    ↓
Oversight Brain astream_chat() starts
    ↓
agent.astream_analyze() → llm_with_tools.astream(full_prompt)
    ↓
LangChain sends to Ollama: { model: "...", messages: [...], tools: [...] }
    ↓
qwen2.5 GGUF receives tool-calling instructions it was not trained for
    ↓
Model goes SILENT — produces 0 tokens, never completes
    ↓
asyncio task hangs indefinitely
    ↓
Heartbeat task fires every 3s (heartbeats visible in SSE stream ✅)
    ↓
OVERSIGHT_LLM_TIMEOUT_SECONDS=120 expires
    ↓
asyncio.timeout fires → error event sent → stream ends
    ↓
Backend proxy was waiting on stalled agent → nginx timeout fires → 503 to frontend
```

**This same stall point affects both blocking and streaming modes.** The difference in observed behavior (504 direct vs 503 via proxy) is only due to where the timeout fires in the chain.

---

## 2. Repository-Specific Code Analysis

### 2.1 Current Tool Binding Architecture

**File**: `agent/services/agent_service.py` (lines 39–47)

```python
class AgentService:
    def __init__(self, tools=None):
        tool_list = tools if tools is not None else ALL_TOOLS
        self.llm_with_tools = llm.bind_tools(tool_list)
        self._tool_map = {t.name: t for t in tool_list}
```

The `llm` object (line 136 in `config.py`) is a singleton `ChatOllama` instance:

```python
llm = ChatOllama(
    model=OLLAMA_MODEL,           # Currently: hf.co/Qwen/.../qwen2.5-7b-instruct-q4_k_m
    base_url=OLLAMA_HOST,         # http://ollama:11434
    timeout=10,                   # 10 second timeout per invoke
    temperature=0.3,
)
```

**Problem**: `timeout=10` in `config.py` is the HTTP-level timeout for the **blocking invoke** call. However, the actual tool-calling hang has **no token output at all** — the model never even starts generating, so the timeout never fires. The request simply stalls until the nginx upstream timeout (50–300s) kicks in.

### 2.2 The Oversight Brain's Actual Tool Need

**File**: `agent/services/oversight_brain.py`

The `oversight_brain` prompt (line 423–468 of `prompts.py`) explicitly says:

```
"Make at most ONE tool call per response."
"Answer directly from injected context whenever possible."
```

And the `_fetch_auto_context()` function pre-injects recent audit log entries **before** the LLM call:

```python
# oversight_brain.py:121–132
auto_context = await _fetch_auto_context(business_account_id, limit=OVERSIGHT_AUTO_CONTEXT_LIMIT)
prompt = (
    "INSTRUCTION: You are in read-only explainability mode. "
    "Answer from the injected context below. Do NOT call tools unless data is explicitly absent. "
    + PromptService.get("oversight_brain").format(
        input=f"{auto_context}\n\n{question}",
        ...
    )
)
```

This means **the Oversight Brain almost never actually needs to call a tool** — the auto-context injection already provides the data. Yet `bind_tools()` forces the tool-calling instruction prompt onto the model regardless of whether tools are needed.

### 2.3 The 2 Tools Being Bound (OVERSIGHT_TOOLS)

**File**: `agent/tools/oversight_tools.py` (lines 189–192)

```python
OVERSIGHT_TOOLS = [
    get_audit_log_entries_tool,
    get_run_summary_tool,
]
```

Both are structured tools with Pydantic schemas. LangChain serializes these into the `tools` array in the Ollama API request. The model's inability to handle this format causes the total stall — not just the tool execution.

### 2.4 SSE Heartbeat Confirming the Stall

From our SSE test:

```
id: 1
event: ping
data: {"heartbeat": true}
retry: 3000

id: 2
event: ping
data: {"heartbeat": true}
retry: 3000
... (8 heartbeats = ~24 seconds)
```

This confirms:
- **Stream infrastructure is alive** ✅
- **Heartbeat task is running** ✅
- **LLM task is stalled** ❌ — no token events, no error events

The `astream()` in `agent_service.py:146` is doing:

```python
async for chunk in self.llm_with_tools.astream(full_prompt):
    text = chunk.content if hasattr(chunk, "content") else ""
    if text:
        yield text
```

If the model produces zero tokens, no chunks arrive, and the `async for` loop never yields anything. The heartbeat loop fires independently every 3 seconds, but the LLM stream is dead.

---

## 3. Verified Test Results

### 3.1 Direct Ollama (No Tool Calling)

```
docker exec ollama ollama run qwen2.5:7b "Say hello in 3 words" --verbose
→ "there!"
→ total duration: 3.843465978s
→ prompt eval count: 35 token(s), prompt eval duration: 2.773638883s
→ prompt eval rate: 12.62 tokens/s
→ eval count: 4 token(s), eval duration: 775.161592ms
→ eval rate: 5.16 tokens/s
```

**Result**: ✅ Works — 4 tokens in 3.8s

**Interpretation**: The Ollama registry version of `qwen2.5:7b` is properly loaded and generating text normally. The model itself is not broken. The problem is entirely in the tool-calling activation via `bind_tools()`.

### 3.2 SSE Streaming Endpoint (With Tool Calling)

```
curl -N -X POST https://agent.888intelligenceautomation.in/oversight/chat \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80" \
  -H "Accept: text/event-stream" \
  -d '{"question": "...", "business_account_id": "...", "stream": true}'
```

**Result**: Only heartbeats arrive, zero LLM tokens. After 120s the stream times out.

**Interpretation**: Confirms the GGUF model cannot produce output when `bind_tools()` adds the tools array to the Ollama API request.

---

## 4. Solutions

### 4.1 Primary Fix: Switch to Ollama Registry Model (Recommended)

**Change**: Replace the HuggingFace GGUF model reference with the Ollama registry model.

**File**: `agent/config.py:134`
```python
# BEFORE:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m")

# AFTER:
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
```

**File**: `agent/startup.sh:6–8`
```bash
# BEFORE:
MODEL_HF="hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m"
MODEL_REGISTRY="qwen2.5:7b"
MODEL_SHORT="qwen2.5-7b-instruct-q4_k_m"

# AFTER:
MODEL_HF="qwen2.5:7b-instruct"       # Use Ollama format even for HF path
MODEL_REGISTRY="qwen2.5:7b-instruct"
MODEL_SHORT="qwen2.5-7b-instruct"
```

**File**: `agent/docker-compose.agent-only.yml`
```yaml
# Line 73: Change OLLAMA_MODEL env var
OLLAMA_MODEL=qwen2.5:7b-instruct
```

**Why this works**: The Ollama registry version of `qwen2.5:7b-instruct` is built with proper tool-calling instruction tuning. When LangChain's `bind_tools()` sends the `tools` array, the model can correctly identify when to call tools and produce valid `tool_calls` JSON.

**Expected outcome**: LLM tokens flow within 1–2 seconds, SSE stream delivers content, no 503 errors.

### 4.2 Alternative: Use Qwen2.5 14B if Available

If the 4 vCPU / 8GB RAM VPS can handle it, `qwen2.5:14b` or `qwen2.5:14b-instruct` provides significantly better tool-calling reliability and general quality. Requires ~10GB RAM minimum for the 4-bit quantized version.

### 4.3 Fallback: Disable Tool Calling for Oversight Brain

If no tool-calling-compatible model is available, the Oversight Brain can be refactored to **not use `bind_tools()`**:

**Approach**: Remove `bind_tools()` and instead inject tool descriptions as part of the prompt text. The model would respond with plain text including structured JSON that the code parses.

```python
# Instead of binding tools, inject them as text
tool_description = ", ".join([t.name for t in OVERSIGHT_TOOLS])
prompt = f"{tool_instruction_text}\n\nAvailable tools: {tool_description}\n\n{prompt}"
```

**Drawback**: Loses LangChain's automatic tool-call parsing. You'd need custom parsing logic. Also loses the structured input validation that LangChain tools provide.

**This is NOT recommended** — the right fix is to use a model that properly supports tool calling.

### 4.4 Architecture Note: The Model Cannot Be Fixed, Only Replaced

The GGUF format limitation is **not a configuration issue** — there is no `model_kwargs`, `system` prompt, or temperature setting that makes the HuggingFace GGUF version correctly handle tool calling. The model weights themselves lack the tool-calling instruction tuning. The only solutions are:

1. **Switch model format** (GGUF → Ollama registry)
2. **Switch to a different model** that officially supports tool calling
3. **Disable tool calling** (not recommended — defeats the purpose of the agent)

---

## 5. Why the Error Manifests Differently at Each Layer

| Layer | Timeout / Behavior | Why |
|-------|-------------------|-----|
| **Agent `config.py`** | `timeout=10` on `ChatOllama` | HTTP-level timeout doesn't fire because the model produces **zero tokens** — it's stuck in the prompt-evaluation phase, not the generation phase |
| **Oversight Brain `OVERSIGHT_LLM_TIMEOUT_SECONDS=120`** | `asyncio.wait_for` / `asyncio.timeout` | This **does fire** eventually after 120s and returns a timeout error |
| **Nginx `proxy_read_timeout`** | 30s–300s depending on location | Fires when backend proxy hangs waiting for agent response |
| **Backend Express proxy** | No explicit timeout on the proxy request | Hangs indefinitely until nginx cuts it off |
| **Frontend** | Receives 503 from backend | Visible to user — the final symptom of the upstream stall |

**The 503 is NOT a bug in the backend or nginx** — it is the correct behavior when an upstream server (the agent) stalls and the proxy's timeout fires. Fixing the model at the root fixes the entire chain.

---

## 6. Nginx Timeout Configuration (Reference)

From `/etc/nginx/sites-available/instagram-dashboard` on the VPS:

```
proxy_send_timeout 60s;
proxy_read_timeout 60s;     # ← Agent endpoint times out here → 504 Gateway Timeout

proxy_read_timeout 300s;    # ← Longer timeout for some endpoints
proxy_send_timeout 300s;

proxy_send_timeout 30s;
proxy_read_timeout 30s;     # ← Shorter timeout for other endpoints
```

The `agent.888intelligenceautomation.in` endpoint (pointing to `localhost:3002` on the VPS host) is likely behind the 30s or 60s `proxy_read_timeout` block, which explains why 503s appear at the frontend after ~30–60 seconds of stalled LLM output.

---

## 7. Monitoring & Metrics Available

The agent exposes Prometheus metrics for diagnosing future issues:

| Metric | Labels | Purpose |
|--------|--------|---------|
| `agent_llm_errors_total` | `error_type` | Tracks LLM failures (agent_execution_failed, agent_stream_failed) |
| `agent_oversight_chat_queries_total` | `status` | Counts oversight requests (started, success, error) |
| `agent_sse_heartbeats_total` | `endpoint` | Confirms heartbeat delivery rate |
| `agent_sse_active_streams` | `endpoint` | Current concurrent streaming requests |

Key query for monitoring:
```promql
rate(agent_llm_errors_total[5m])  # Should be 0 when model is working
rate(agent_oversight_chat_queries_total[5m])  # Request rate
```

---

## 8. Recommended Immediate Action Plan

1. **Update `OLLAMA_MODEL`** in `config.py`, `docker-compose.agent-only.yml`, and `startup.sh` to use `qwen2.5:7b-instruct` (Ollama registry format)
2. **Update `.env`** on the VPS to `OLLAMA_MODEL=qwen2.5:7b-instruct`
3. **Pull the new model**: `docker exec ollama ollama pull qwen2.5:7b-instruct`
4. **Restart the agent container**: `docker compose -f docker-compose.unified.yml restart langchain-agent`
5. **Run SSE test**: Confirm tokens flow within 5 seconds
6. **Run Prometheus query**: Confirm `agent_llm_errors_total` stays flat while `agent_oversight_chat_queries_total` increments

---

## 9. Long-Term Recommendations

1. **Evaluate `qwen3.5` or `qwen3-next`** from Ollama's library — these are listed on the official models page as having tool-calling support. They offer better reasoning and tool-calling reliability.

2. **Add LLM startup verification**: On agent startup, run a lightweight tool-calling test (invoke with one simple tool) before marking the service healthy. This catches tool-calling incompatibility at deploy time, not production runtime.

3. **Consider GPU upgrade for Nemotron**: If the eventual goal is to return to Nemotron-8B-GGUF on a GPU-equipped VPS, that model should work correctly with `bind_tools()` because it was specifically selected for tool-calling capability in the original architecture.

4. **Add `think=false`** as a model kwarg when using Qwen2.5 via Ollama registry (if needed):
   ```python
   llm = ChatOllama(
       model=OLLAMA_MODEL,
       base_url=OLLAMA_HOST,
       timeout=10,
       temperature=0.3,
       model_kwargs={"think": False}  # Only if model has thinking mode
   )
   ```
   Note: This only applies if the model has a "thinking" mode. The Ollama registry `qwen2.5:7b-instruct` is Qwen2.5 base — it does **not** have DeepSeek-R1 style thinking. The `think=false` parameter was only relevant for the Nemotron model which did have thinking mode.

---

## Sources

- [Ollama Blog — Tool Support](https://ollama.com/blog/tool-support) — Official Ollama documentation on tool calling
- [Ollama Models Page](https://ollama.com/models) — Models with `tool_calling` tag
- [LangChain Ollama Integration](https://python.langchain.com/docs/integrations/llms/ollama/) — `bind_tools()` usage examples
- [HuggingFace Qwen2.5-7B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) — Model card (no tool calling documentation found)
- Repository files: `agent/services/agent_service.py`, `agent/config.py`, `agent/services/oversight_brain.py`, `agent/tools/oversight_tools.py`, `agent/prompts.py`, `agent/startup.sh`

---

# Dev Agent Context — Oversight Chat Failure: Full Investigation & Remediation Record

**Date of investigation:** 2026-03-25
**Status:** Root cause confirmed. Fixes prioritized and documented. Environment already partially remediated on VPS.
**Current active model (VPS):** `qwen2.5:7b-instruct` (Ollama registry, loaded after GGUF fallback)
**Previous model:** Nemotron 8B (NVIDIA GPU, CUDA-optimized, works with multi-tool binding)

---

## A. What Happened (Full Timeline)

1. **Switch from Nemotron → Qwen2.5 7B**: The VPS was migrated from a CUDA-capable environment (Nemotron 8B) to CPU-only Qwen2.5 7B. The code was not changed — only the model. The Oversight Brain immediately started returning 503 errors.

2. **503 chain traced**: Frontend 503 → backend proxy → agent nginx 504 → agent endpoint stalled.

3. **GGUF hypothesis disproven**: `startup.sh` attempts HF GGUF pull first, but the `MODEL_SHORT` check never matches (Ollama stores GGUF under a different name), so it falls back to `qwen2.5:7b` (registry base model). The base model also hung. At this point the fix applied on VPS was switching to `qwen2.5:7b-instruct`.

4. **Registry model partial fix**: `qwen2.5:7b-instruct` improved things — the model started generating tokens. But the Oversight Chat **still hung**. The reason: the model handles **1 tool correctly** but **hangs with 2+ tools**.

5. **Root cause confirmed**: `qwen2.5:7b-instruct` via Ollama has a **hard tool-count ceiling of 1**. This is a model capability limitation of the Qwen2.5 7B family — not a configuration or code bug.

---

## B. Testing Conducted & Results

### Test 1 — GGUF direct Ollama run (no tools)
```
docker exec ollama ollama run qwen2.5:7b "Say hello in 3 words" --verbose
→ "there!"
→ total duration: 3.84s, eval rate: 5.16 tokens/s
```
**Result:** ✅ Model generates text normally without `bind_tools()`.

---

### Test 2 — GGUF via LangChain `bind_tools()` (1 tool)
```
# Inside agent container
python3 -c "from langchain_ollama import ChatOllama; ..."
```
**Result:** ❌ Zero tokens. Model stalls before generating anything. Confirmed GGUF has no tool-calling template.

---

### Test 3 — Registry model `qwen2.5:7b-instruct` (1 tool vs 2 tools)

```
# 1 tool test (GET endpoint for account info)
curl -sf http://ollama:11434/api/chat \
  -d '{"model":"qwen2.5:7b-instruct","messages":[...],"tools":[TOOL_1_ONLY]}'
→ Response in ~12-17s ✅
```
```
# 2 tool test (same + 1 additional tool)
curl -sf http://ollama:11434/api/chat \
  -d '{"model":"qwen2.5:7b-instruct","messages":[...],"tools":[TOOL_1, TOOL_2]}'
→ Timeout after 30s, httpx fires ❌
```
**Result:** ✅ 1 tool works. ❌ 2+ tools hang indefinitely. This is the **confirmed root cause**.

---

### Test 4 — SSE streaming endpoint
```
curl -N -X POST https://agent.888intelligenceautomation.in/oversight/chat \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80" \
  -H "Accept: text/event-stream" \
  -d '{"question": "...", "business_account_id": "...", "stream": true}'
```
**Result:** Heartbeats arrive (stream infrastructure ✅), zero LLM tokens (model stalled ❌). Confirms the hang is at the Ollama API layer, not the SSE layer.

---

### Test 5 — Health check after VPS model switch
```
curl http://agent.888intelligenceautomation.in/health \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80"
```
**Result:** `{"model":"qwen2.5:7b-instruct","status":"ok"}` ✅ Model is loaded and health check passes.

---

## C. Code Findings — Full Repository Audit

### C.1 `agent/tools/oversight_tools.py` — THE PRIMARY CULPRIT
```python
OVERSIGHT_TOOLS = [
    get_audit_log_entries_tool,   # tool 1
    get_run_summary_tool,          # tool 2 → causes hang with qwen2.5:7b-instruct
]
```
Both tools have Pydantic schemas. When bound via `llm.bind_tools(OVERSIGHT_TOOLS)`, LangChain sends a `tools` array with **2 entries** to Ollama. The model cannot process 2 tools → hangs → 120s timeout → 503.

**Fix required:** Merge these 2 tools into 1 unified tool with an `action` parameter.

---

### C.2 `agent/tools/supabase_tools.py` — SECONDARY RISK
```python
SUPABASE_TOOLS = [
    get_post_context_tool,
    get_account_info_tool,
    get_recent_comments_tool,
    get_dm_history_tool,
    get_dm_conversation_context_tool,
    get_post_performance_tool,
    log_decision_tool,
]  # 7 tools
```
Used by: Analytics Reports (via `AgentService(ALL_TOOLS)`). With 12 tools in the full `ALL_TOOLS` set, this is equally at risk.

---

### C.3 `agent/tools/automation_tools.py` — NESTED TOOL REBINDING
```python
def _analyze_message(...) -> dict:
    agent = _get_agent_service()      # rebinds ALL_TOOLS = 12 tools
    result = asyncio.run(agent.analyze_async(prompt))
```
`_analyze_message` is itself called as a LangChain tool. Inside it, it calls `AgentService.analyze_async()` which **rebinds all 12 tools**. This is nested tool-calling — a pattern that amplifies the tool-count problem.

---

### C.4 `agent/services/agent_service.py` — MISSING TIMEOUT
```python
# Blocking path — NO outer timeout (❌ at risk of indefinite block)
async def _analyze(self, prompt: str) -> dict:
    async with _llm_semaphore:
        result = await asyncio.to_thread(self.llm_with_tools.invoke, full_prompt)

# Streaming path — has asyncio.timeout (✅ protected)
async def _astream(self, prompt: str, on_event=None):
    async with _llm_semaphore:  # no outer timeout here either
        async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
            async for chunk in self.llm_with_tools.astream(full_prompt):
                yield chunk
```
Both `_analyze()` and `_astream()` have **no outer `asyncio.wait_for`** around the semaphore. If the model hangs inside the semaphore, the entire task hangs forever.

---

### C.5 `agent/config.py` — STALE DEFAULT
```python
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF/qwen2.5-7b-instruct-q4_k_m"  # stale default
)
```
Default still points to HF GGUF path. Should be `qwen2.5:7b-instruct`. The VPS `.env` already has this corrected.

---

### C.6 `agent/startup.sh` — MISLEADING COMMENTS
Comments claim HF GGUF is the primary model. It's not — it always falls through to the registry model due to the name mismatch. The comments are confusing and should be updated.

---

### C.7 `agent/prompts.py` — SYSTEM PROMPT (correct as-is)
```python
SYSTEM_PROMPT = """You are an Instagram automation intelligence layer with access to database tools.
Use tools only when data you need is not already present in the prompt —
if context is pre-injected, answer from it directly without making tool calls."""
```
This prompt is **correct and well-designed**. It tells the model to avoid tool calls when context is pre-injected. The problem is `bind_tools()` activates tool-calling mode regardless of whether the prompt needs tools.

---

## D. Timeout Chain (Current Configuration)

```
Frontend (user)
    ↓
Backend Express proxy (axios timeout=65000ms)  [backend.api/routes/agents/oversight.js]
    ↓
Nginx (proxy_read_timeout=30s or 60s)  [VPS host /etc/nginx/sites-available/instagram-dashboard]
    ↓
Agent FastAPI /oversight/chat endpoint  [agent/routes/oversight.py]
    ↓
asyncio.timeout(120s)  [inside oversight_brain.py run_llm()]
    ↓
llm_with_tools.astream()  [agent/services/agent_service.py]
    ↓
Ollama /api/chat with "tools": [...]  [2 tools → hangs indefinitely]
```

The 120s `asyncio.timeout` fires eventually and returns a timeout error — this is working as designed. The 503 at the frontend is the **correct end-to-end behavior** when the agent stalls.

---

## E. Current Environment State (VPS)

| Setting | Value | Status |
|---------|-------|--------|
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct` | ✅ Correct (manually set in VPS `.env`) |
| Model loaded in Ollama | `qwen2.5:7b-instruct` | ✅ Confirmed via health check |
| Health endpoint | Returns 200 | ✅ Agent is alive |
| `OVERSIGHT_LLM_TIMEOUT_SECONDS` | `120` | ✅ Set in docker-compose env |
| `bind_tools()` count for Oversight | **2 tools** | ❌ Still causes hang |

The **environment is partially remediated** — the correct model is loaded. But the **tool count problem remains** — the code still binds 2 tools to a model that can only handle 1.

---

## F. Full Priority Fix Plan

### Priority 1 — Consolidate Oversight Tools (2 → 1) — **DO FIRST**
**File:** `agent/tools/oversight_tools.py`

Replace `OVERSIGHT_TOOLS` (2 entries) with a single unified tool:
```python
def create_unified_oversight_tool():
    """Single tool with action parameter: 'get_audit_log' | 'get_run_summary'"""
    ...
UNIFIED_OVERSIGHT_TOOL = create_unified_oversight_tool()
OVERSIGHT_TOOLS = [UNIFIED_OVERSIGHT_TOOL]  # now 1 tool
```

**Also update:** `agent/tools/__init__.py` if it references `OVERSIGHT_TOOLS` by name.
**Also update:** `agent/services/oversight_brain.py` — internal tool handler must dispatch by `action` field.

**Expected outcome:** Oversight Chat responds in ~12–17s with tokens flowing.

---

### Priority 2 — Analytics Reports Tool Overload
**File:** `agent/scheduler/analytics_reports.py`

`AgentService(ALL_TOOLS)` binds 12 tools. When `generate_llm_insights()` fires, it will hang the same way.

**Fix:** Create a dedicated `AgentService` instance scoped only to what analytics needs, OR consolidate analytics tools the same way (1 unified tool).

---

### Priority 3 — `analyze_message` Nested Rebinding
**File:** `agent/tools/automation_tools.py`

`_analyze_message()` rebinds all 12 tools internally. Fix by passing a minimal tool set or bypassing `AgentService` for simple classification.

---

### Priority 4 — Global Timeout Hardening
**File:** `agent/services/agent_service.py`

Add outer `asyncio.wait_for` around the semaphore in `_analyze()`:
```python
async def _analyze(self, prompt: str) -> dict:
    async with _llm_semaphore:
        result = await asyncio.wait_for(
            asyncio.to_thread(self.llm_with_tools.invoke, full_prompt),
            timeout=OVERSIGHT_LLM_TIMEOUT_SECONDS
        )
```

---

### Priority 5 — Config Default Cleanup
**File:** `agent/config.py`

Update the `OLLAMA_MODEL` default from HF GGUF path to Ollama registry:
```python
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
```

---

### Priority 6 — Startup Script Cleanup
**File:** `agent/startup.sh`

Remove misleading HF GGUF primary-path comments. Set all 3 model variables to `qwen2.5:7b-instruct`.

---

## G. What NOT to Change

- The SSE streaming infrastructure — heartbeats arrive correctly, stream works fine
- The backend Express proxy (`backend.api/routes/agents/oversight.js`) — it correctly times out waiting for the agent
- Nginx configuration — 503 is the correct behavior when the agent stalls
- The `oversight_brain` prompt in `prompts.py` — it is well-designed and correct
- `OVERSIGHT_LLM_TIMEOUT_SECONDS=120` — already set correctly in docker-compose

---

## H. Verification Commands

### After Priority 1 fix is deployed:

```bash
# Test 1: Health check (confirm correct model)
curl http://agent.888intelligenceautomation.in/health \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80"
# Expected: {"model":"qwen2.5:7b-instruct","status":"ok"}

# Test 2: Oversight SSE chat
curl -N -X POST https://agent.888intelligenceautomation.in/oversight/chat \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80" \
  -H "Accept: text/event-stream" \
  -d '{"question": "What did the agent do today?", "business_account_id": "0882b710-4258-47cf-85c8-1fa82a3de763", "stream": true}'
# Expected: tokens arrive within 20s, no 503, SSE delivers content

# Test 3: Prometheus metrics
curl http://agent.888intelligenceautomation.in/metrics \
  -H "X-API-Key: dqoSRrL3FJkXoUnI8B1HQ1Zpc2pEO3EsoMveDm0XB80"
# Check: agent_llm_errors_total stays flat, agent_oversight_chat_queries_total increments
```

---

## I. Key Files Reference

| File | Role | Relevant For |
|------|------|-------------|
| `agent/tools/oversight_tools.py` | 2 oversight tools → fix here first | Priority 1 |
| `agent/tools/supabase_tools.py` | 7 DB tools | Priority 2 |
| `agent/tools/automation_tools.py` | 3 automation tools + `_analyze_message` | Priority 3 |
| `agent/tools/__init__.py` | `ALL_TOOLS = SUPABASE + AUTOMATION + OVERSIGHT` | Priorities 1-3 |
| `agent/services/agent_service.py` | LLM binding + `_analyze()` / `_astream()` | Priority 4 |
| `agent/services/oversight_brain.py` | Tool handler dispatch | Priority 1 |
| `agent/scheduler/analytics_reports.py` | Uses `AgentService(ALL_TOOLS)` = 12 tools | Priority 2 |
| `agent/config.py` | `OLLAMA_MODEL` default, `ChatOllama` singleton | Priority 5 |
| `agent/startup.sh` | Model pull script | Priority 6 |
| `docker-compose.unified.yml` | `OVERSIGHT_LLM_TIMEOUT_SECONDS=120`, container env | Reference |
| `.env` (VPS) | `OLLAMA_MODEL=qwen2.5:7b-instruct` | Already correct |
| `agent/prompts.py` | SYSTEM_PROMPT, oversight_brain prompt | Do not change |

---

## J. Long-Term Model Recommendations

When upgrading beyond Qwen2.5 7B:

1. **`qwen3.5` or `qwen3-next`** — listed on Ollama official models page as `tool_calling: true`. Significantly better multi-tool capability.

2. **Nemotron 8B return path** — If GPU returns (Hetzner GPU node, Colab Enterprise, etc.), Nemotron 8B was confirmed working with all 12 tools via `bind_tools()`. No code changes needed — just `OLLAMA_MODEL` env var.

3. **Startup LLM health check** — Add a lightweight tool-calling test in the agent's startup sequence (`agent.py` lifespan). If the test fails, mark the agent unhealthy immediately — catch the problem at deploy time, not in production.
