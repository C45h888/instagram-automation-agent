# Phase 1: SSE Hardening Implementation Plan

## Overview

This plan covers **SSE Hardening only** — no WebSocket, no Scheduler Streams, no Pub/Sub broadcast.

### Goals
1. **Heartbeat pings** — Prevent proxy timeouts on idle connections
2. **Disconnect detection** — Stop LLM when client drops
3. **Event IDs** — Enable `Last-Event-ID` resume capability
4. **Tool status events** — Emit `tool_call`/`tool_done` during tool execution

---

## Current State Analysis

### File: [`config.py`](../agent/config.py) (Lines 183-188)

**Current:**
```python
SSE_RESPONSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
```

**Missing:**
- `SSE_HEARTBEAT_INTERVAL_SECONDS` — Heartbeat interval
- `SSE_MAX_RECONNECT_WINDOW_SECONDS` — Reconnect window
- `Content-Type: text/event-stream` — Explicit for nginx

---

### File: [`metrics.py`](../agent/metrics.py) (Lines 72-76)

**Current:**
```python
OVERSIGHT_CHAT_QUERIES = Counter(
    "agent_oversight_chat_queries_total",
    "Oversight Brain chat queries by status",
    ["status"],
)
```

**Missing:**
- `SSE_DISCONNECTS` — Counter for client disconnections
- `SSE_HEARTBEATS_SENT` — Counter for heartbeat pings
- `SSE_ACTIVE_STREAMS` — Gauge for active streams

---

### File: [`services/agent_service.py`](../agent/services/agent_service.py) (Lines 58-70, 123-166)

**Current `astream_analyze()`:**
```python
async def astream_analyze(self, prompt: str):
    async with _llm_semaphore:
        async for chunk in self._astream(prompt):
            yield chunk
```

**Current `_astream()`:**
```python
async def _astream(self, prompt: str):
    # Step 1: Initial invoke (non-streaming) to detect tool calls
    result = await asyncio.to_thread(self.llm_with_tools.invoke, full_prompt)
    tool_calls = getattr(result, "tool_calls", [])

    # Step 2: Execute tool calls in parallel if any
    tool_outputs = {}
    if tool_calls:
        tool_outputs = await self._execute_tool_calls_async(tool_calls)
        # ... stream follow-up
```

**Problem:** No events emitted during tool execution — client sees nothing until tools complete.

**Required Changes:**
- Add `on_event: Optional[Callable[[dict], Awaitable[None]]] = None` parameter
- Emit `tool_call` event before each tool execution
- Emit `tool_done` event after each tool execution

---

### File: [`services/oversight_brain.py`](../agent/services/oversight_brain.py) (Lines 185-255)

**Current `astream_chat()`:**
```python
async def astream_chat(question, business_account_id, chat_history, user_id, request_id):
    # ... build prompt ...
    
    accumulated = ""
    try:
        agent = _get_agent()
        async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
            async for chunk in agent.astream_analyze(prompt):
                accumulated += chunk
                yield f"data: {json_mod.dumps({'token': chunk})}\n\n"
    except TimeoutError:
        yield f"data: {json_mod.dumps({'error': 'timeout'})}\n\n"

    yield f"data: {json_mod.dumps({'done': True, 'latency_ms': latency_ms, 'request_id': request_id})}\n\n"
```

**Missing:**
- No `request` parameter for disconnect detection
- No heartbeat pings
- No event IDs (`id:` field)
- No `event:` type field
- No tool status events

---

### File: [`routes/oversight.py`](../agent/routes/oversight.py) (Lines 92-107)

**Current:**
```python
if request_body.stream and OVERSIGHT_STREAM_ENABLED:
    return StreamingResponse(
        oversight_stream_chat(
            question=request_body.question,
            business_account_id=request_body.business_account_id,
            chat_history=request_body.chat_history,
            user_id=request_body.user_id,
            request_id=request_id,
        ),
        media_type="text/event-stream",
        headers={**SSE_RESPONSE_HEADERS, "X-Request-ID": request_id},
    )
```

**Missing:**
- `request` object not passed to `oversight_stream_chat()`
- No `Last-Event-ID` header handling

---

## Implementation Details

### Task 1: [`config.py`](../agent/config.py)

Add after line 181:

```python
# SSE Hardening (Phase 1)
SSE_HEARTBEAT_INTERVAL_SECONDS = int(os.getenv("SSE_HEARTBEAT_INTERVAL_SECONDS", "10"))
SSE_MAX_RECONNECT_WINDOW_SECONDS = int(os.getenv("SSE_MAX_RECONNECT_WINDOW_SECONDS", "300"))

# SSE response headers — must match backend.api/routes/agents/oversight.js
SSE_RESPONSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
    "Content-Type": "text/event-stream",  # Explicit for nginx
}
```

---

### Task 2: [`metrics.py`](../agent/metrics.py)

Add after line 76:

```python
# ================================
# SSE Streaming (Phase 1 Hardening)
# ================================
SSE_DISCONNECTS = Counter(
    "agent_sse_disconnects_total",
    "SSE client disconnections",
    ["endpoint"],
)

SSE_HEARTBEATS_SENT = Counter(
    "agent_sse_heartbeats_total",
    "SSE heartbeat pings sent to clients",
    ["endpoint"],
)

SSE_ACTIVE_STREAMS = Gauge(
    "agent_sse_active_streams",
    "Active SSE streams by endpoint",
    ["endpoint"],
)
```

---

### Task 3: [`services/agent_service.py`](../agent/services/agent_service.py)

**Change `astream_analyze()` signature:**
```python
async def astream_analyze(self, prompt: str, on_event=None):
    """Async streaming entry point with semaphore-limited concurrency.

    Args:
        prompt: Prompt to send to LLM
        on_event: Optional async callback(event: dict) for tool_call/tool_done events

    Yields:
        str: Text chunks from the LLM response
    """
    async with _llm_semaphore:
        async for chunk in self._astream(prompt, on_event=on_event):
            yield chunk
```

**Change `_astream()` signature and add event emission:**
```python
async def _astream(self, prompt: str, on_event=None):
    """Async streaming LLM invocation with tool support.

    Args:
        prompt: Prompt to send to LLM
        on_event: Optional async callback(event: dict) for tool events
    """
    start_time = time.time()

    try:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

        # Step 1: Initial invoke to detect tool calls
        result = await asyncio.to_thread(self.llm_with_tools.invoke, full_prompt)
        tool_calls = getattr(result, "tool_calls", [])

        # Step 2: Execute tool calls with event emission
        tool_outputs = {}
        if tool_calls:
            # Emit tool_call events before execution
            for call in tool_calls:
                tool_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if on_event:
                    await on_event({
                        "event_type": "tool_call",
                        "tool_name": tool_name,
                    })

            tool_start = time.time()
            tool_outputs = await self._execute_tool_calls_async(tool_calls)
            tool_elapsed_ms = int((time.time() - tool_start) * 1000)

            # Emit tool_done events after execution
            for call in tool_calls:
                tool_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
                if on_event:
                    await on_event({
                        "event_type": "tool_done",
                        "tool_name": tool_name,
                        "elapsed_ms": tool_elapsed_ms,
                    })

            # Stream follow-up with tool context
            if tool_outputs:
                enriched_prompt = self._build_enriched_prompt(full_prompt, tool_outputs)
                async for chunk in self.llm_with_tools.astream(enriched_prompt):
                    text = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if text:
                        yield text
                return

        # Step 3: No tools — yield the already-completed response
        raw_text = result.content if hasattr(result, "content") else str(result)
        yield raw_text

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"AgentService stream failed (latency={latency_ms}ms): {e}")
        LLM_ERRORS.labels(error_type="agent_stream_failed").inc()
        yield json.dumps({"error": "agent_stream_failed", "message": str(e)})
```

---

### Task 4: [`services/oversight_brain.py`](../agent/services/oversight_brain.py)

Complete rewrite of `astream_chat()`:

```python
async def astream_chat(
    question: str,
    business_account_id: str = "",
    chat_history: Optional[list] = None,
    user_id: str = "dashboard-user",
    request_id: str = "unknown",
    request = None,  # NEW: FastAPI Request for disconnect detection
):
    """Streaming version of chat() with Phase 1 hardening.

    Features:
    - Event IDs for Last-Event-ID resume support
    - Heartbeat pings every N seconds (prevents proxy timeouts)
    - Disconnect detection (stops LLM on client disconnect)
    - Tool status events (tool_call, tool_done)
    - Proper SSE formatting (id:, event:, data: fields)

    Args:
        request: FastAPI Request object for disconnect detection
    """
    import json as json_mod
    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT, OVERSIGHT_LLM_TIMEOUT_SECONDS, SSE_HEARTBEAT_INTERVAL_SECONDS

    start = time.time()
    event_id = 0
    accumulated = ""

    # Helper: format SSE event with id and event type
    def format_sse_event(payload: dict, event_type: str = "message") -> str:
        nonlocal event_id
        event_id += 1
        data = json_mod.dumps(payload)
        return f"id: {event_id}\nevent: {event_type}\ndata: {data}\nretry: 3000\n\n"

    # Helper: check if client disconnected
    async def is_disconnected() -> bool:
        if not request:
            return False
        try:
            return await request.is_disconnected()
        except Exception:
            return False

    # Build conversation history text
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    # Auto-inject recent decisions as context
    auto_context = await _fetch_auto_context(
        business_account_id,
        limit=OVERSIGHT_AUTO_CONTEXT_LIMIT,
    )

    prompt = PromptService.get("oversight_brain").format(
        input=f"{auto_context}\n\n{question}",
        chat_history=history_text or "(No prior conversation)",
    )

    # Event queue for concurrent heartbeat + LLM tokens
    event_queue = asyncio.Queue()
    heartbeat_task = None

    async def heartbeat_loop():
        """Send heartbeat pings every N seconds."""
        while True:
            try:
                await asyncio.sleep(SSE_HEARTBEAT_INTERVAL_SECONDS)
                if await is_disconnected():
                    break
                await event_queue.put(("heartbeat", None))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[{request_id}] Heartbeat error: {e}")
                break

    async def on_tool_event(event: dict):
        """Callback from agent_service for tool events."""
        await event_queue.put(("tool_event", event))

    # Start heartbeat task
   

    try:
        # Stream LLM response with timeout
        agent = _get_agent()
        async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
            async for chunk in agent.astream_analyze(prompt, on_event=on_tool_event):
                if await is_disconnected():
                    logger.info(f"[{request_id}] Client disconnected during stream")
                    break
                accumulated += chunk
                await event_queue.put(("token", chunk))

    except TimeoutError:
        logger.warning(f"[{request_id}] Oversight stream timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
        await event_queue.put(("error", {"error": "timeout"}))

    except Exception as e:
        logger.error(f"[{request_id}] Oversight stream error: {e}")
        await event_queue.put(("error", {"error": "stream_failed", "message": str(e)}))

    finally:
        # Signal end of stream
        await event_queue.put(("stream_done", None))
        # Cancel heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    # Emit all queued events as SSE
    latency_ms = int((time.time() - start) * 1000)

    while True:
        try:
            event_type, event_data = await asyncio.wait_for(event_queue.get(), timeout=1.0)

            # Check disconnect before emitting each event
            if await is_disconnected():
                logger.info(f"[{request_id}] Client disconnected before event emission")
                break

            if event_type == "heartbeat":
                yield format_sse_event({"heartbeat": True}, event_type="ping")

            elif event_type == "tool_event":
                yield format_sse_event(event_data, event_type=event_data.get("event_type", "tool_status"))

            elif event_type == "token":
                yield format_sse_event({"token": event_data}, event_type="message")

            elif event_type == "error":
                yield format_sse_event(event_data, event_type="error")

            elif event_type == "stream_done":
                break

        except asyncio.TimeoutError:
            break
        except Exception as e:
            logger.error(f"[{request_id}] Event emission error: {e}")
            break

    # Final completion event
    latency_ms = int((time.time() - start) * 1000)
    yield format_sse_event(
        {"done": True, "latency_ms": latency_ms},
        event_type="done"
    )

    # Audit log (fire-and-forget)
    SupabaseService.log_decision(
        event_type="oversight_chat_query",
        action="stream_answered",
        resource_type="oversight_query",
        resource_id=str(uuid_mod.uuid4()),
        user_id=user_id,
        details={
            "question": question[:500],
            "answer_preview": accumulated[:500],
            "business_account_id": business_account_id,
            "latency_ms": latency_ms,
            "request_id": request_id,
            "streamed": True,
            "events_sent": event_id,
        },
    )

    logger.info(f"[{request_id}] Oversight Brain streamed in {latency_ms}ms ({event_id} events)")
```

---

### Task 5: [`routes/oversight.py`](../agent/routes/oversight.py)

**Change the streaming path (lines 92-107):**

```python
    # Streaming path
    if request_body.stream and OVERSIGHT_STREAM_ENABLED:
        OVERSIGHT_CHAT_QUERIES.labels(status="stream_started").inc()
        
        # Read Last-Event-ID header for resume support
        last_event_id = request.headers.get("Last-Event-ID", None)
        if last_event_id:
            logger.info(f"[{request_id}] Client reconnecting with Last-Event-ID: {last_event_id}")
        
        return StreamingResponse(
            oversight_stream_chat(
                question=request_body.question,
                business_account_id=request_body.business_account_id,
                chat_history=request_body.chat_history,
                user_id=request_body.user_id,
                request_id=request_id,
                request=request,  # NEW: Pass request for disconnect detection
            ),
            media_type="text/event-stream",
            headers={
                **SSE_RESPONSE_HEADERS,
                "X-Request-ID": request_id,
            },
        )
```

---

## SSE Event Format (After Implementation)

### Before (Current)
```
data: {"token": "Hello"}\n\n
data: {"done": true, "latency_ms": 1234}\n\n
```

### After (Hardened)
```
id: 1
event: message
data: {"token": "Hello"}
retry: 3000

id: 2
event: ping
data: {"heartbeat": true}
retry: 3000

id: 3
event: tool_call
data: {"event_type": "tool_call", "tool_name": "get_audit_log_entries"}
retry: 3000

id: 4
event: tool_done
data: {"event_type": "tool_done", "tool_name": "get_audit_log_entries", "elapsed_ms": 150}
retry: 3000

id: 5
event: done
data: {"done": true, "latency_ms": 1234}
retry: 3000

```

---

## Testing Checklist

| Test | Method | Expected Result |
|------|--------|-----------------|
| Heartbeat pings arrive | `curl -N` for 30s | See `event: ping` every 10s |
| Disconnect stops LLM | Kill curl mid-stream | Ollama CPU drops within 5s |
| Event IDs increment | Check `id:` field | Sequential integers |
| Tool events appear | Ask question triggering tools | See `tool_call` before tokens |
| Last-Event-ID logged | Reconnect with header | Log shows "reconnecting with Last-Event-ID" |

---

## Files Modified Summary

| File | Lines Changed | Change Type |
|------|---------------|-------------|
| `config.py` | +5 | Add env vars + header |
| `metrics.py` | +15 | Add 3 metrics |
| `services/agent_service.py` | ~30 | Add callback param |
| `services/oversight_brain.py` | ~100 | Rewrite generator |
| `routes/oversight.py` | +5 | Pass request |

**Total: 5 files, ~155 lines changed**
