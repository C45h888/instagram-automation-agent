"""
Oversight Brain Service
=======================
Explainability service for the Oversight Brain chat interface.

Pattern: build prompt with auto-context → direct llm.invoke/astream → optional tool calls
No bind_tools() — the LLM generates text directly from pre-injected context.
Tool descriptions are embedded as readable text in the prompt. The LLM uses a
special syntax <<TOOL:...>> to request a tool call when data is genuinely missing.
Tool execution is handled inline without AgentService, keeping oversight isolated
from the automation tool layer.

Caching: L1 TTLCache + L2 Redis (same pattern as supabase_service.py).
Conversation-aware: skips cache when chat_history is provided.
"""

import asyncio
import hashlib
import json
import re
import time
import uuid as uuid_mod
from typing import Optional

from cachetools import TTLCache

from config import llm, logger
from services.supabase_service import SupabaseService, _cache_get, _cache_set
from services.prompt_service import PromptService
from metrics import SSE_DISCONNECTS, SSE_HEARTBEATS_SENT, SSE_ACTIVE_STREAMS, TOOL_CALLS


# L1 in-memory cache (mirrors supabase_service.py pattern)
_question_cache: TTLCache = TTLCache(maxsize=100, ttl=300)  # 5-minute TTL

# Semaphore — limits concurrent LLM calls to protect Ollama CPU
_llm_semaphore = asyncio.Semaphore(2)

# Tool call timeout per tool
TOOL_TIMEOUT_SECONDS = 5.0

# Marker the LLM outputs to request a tool call (detected in the text stream)
TOOL_CALL_OPEN = "<<TOOL_CALL:"
TOOL_CALL_CLOSE = ">>"


def _cache_key(question: str, business_account_id: str = "") -> str:
    """Stable cache key for a question (history-less queries only)."""
    raw = f"{business_account_id}:{question.lower().strip()}"
    return f"oversight:{hashlib.md5(raw.encode()).hexdigest()}"


def _build_tool_descriptions() -> str:
    """Build tool descriptions as plain text for prompt injection.

    These are NOT bound via bind_tools() — the LLM sees them as readable reference
    text and uses the <<TOOL_CALL:...>> marker syntax when it wants to invoke one.
    This avoids LangChain's bind_tools() system prompt that stalls smaller models.
    """
    return """
## AVAILABLE TOOLS (optional — use only if data is genuinely missing)
If you need data that is NOT in the context above, output: <<TOOL_CALL:get_audit_log_entries|resource_id:ID,event_type:TYPE,date_from:YYYY-MM-DD,business_account_id:ID,limit:N>>
If you need run statistics: <<TOOL_CALL:get_run_summary|run_id:RUN_UUID>>
After outputting the marker, I will insert the tool results. Then provide your final answer.
"""


# ------------------------------------------------------------------
# Tool call parsing and execution (inline, no AgentService needed)
# ------------------------------------------------------------------

def _parse_tool_calls(text: str) -> list[dict]:
    """Extract <<TOOL_CALL:tool_name|args>> markers from LLM text output.

    Args format inside markers: key1:value1,key2:value2
    Values containing commas or special chars are NOT quoted — keep it simple.
    """
    pattern = re.escape(TOOL_CALL_OPEN) + r"([^|]+)\|([^" + re.escape(TOOL_CALL_CLOSE) + r"]+)" + re.escape(TOOL_CALL_CLOSE)
    matches = re.findall(pattern, text)
    calls = []
    for tool_name_raw, args_raw in matches:
        tool_name = tool_name_raw.strip()
        args = {}
        for pair in args_raw.split(","):
            if ":" not in pair:
                continue
            k, v = pair.split(":", 1)
            k = k.strip()
            v = v.strip()
            # Coerce numeric types
            if v.lower() == "none" or v.lower() == "null" or v == "":
                continue
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass  # keep as string
            args[k] = v
        calls.append({"name": tool_name, "args": args})
    return calls


async def _execute_oversight_tool(tool_name: str, args: dict) -> dict:
    """Execute a single oversight tool by name, with timeout."""
    from tools.oversight_tools import _get_audit_log_entries, _get_run_summary

    TOOL_MAP = {
        "get_audit_log_entries": _get_audit_log_entries,
        "get_run_summary": _get_run_summary,
    }

    func = TOOL_MAP.get(tool_name)
    if not func:
        return {"error": f"unknown_tool", "message": f"Tool '{tool_name}' not found"}

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(func, **args),
            timeout=TOOL_TIMEOUT_SECONDS,
        )
        logger.info(f"Oversight tool '{tool_name}' executed successfully")
        TOOL_CALLS.labels(tool_name=tool_name).inc()
        return result
    except asyncio.TimeoutError:
        logger.warning(f"Oversight tool '{tool_name}' timed out after {TOOL_TIMEOUT_SECONDS}s")
        TOOL_CALLS.labels(tool_name=f"{tool_name}_timeout").inc()
        return {"error": "timeout", "message": f"Tool '{tool_name}' timed out"}
    except Exception as e:
        logger.error(f"Oversight tool '{tool_name}' failed: {e}")
        TOOL_CALLS.labels(tool_name=f"{tool_name}_error").inc()
        return {"error": str(e)}


async def _fetch_auto_context(business_account_id: str, limit: int = 12) -> str:
    """Format recent operational audit_log decisions for prompt injection.

    Query logic lives in _get_operational_entries (oversight_tools.py).
    This function owns only formatting — no query logic, no type lists.
    """
    from tools.oversight_tools import _get_operational_entries

    entries = _get_operational_entries(business_account_id, limit)

    if not entries:
        return "(No recent agent decisions found for this account)"

    lines = []
    for e in entries:
        lines.append(
            f"- [{e.get('created_at', '?')}] {e.get('event_type', '?')}: "
            f"action={e.get('action', '?')}, resource={e.get('resource_id', 'N/A')}"
        )
    return "RECENT AGENT DECISIONS (auto-injected):\n" + "\n".join(lines)


async def chat(
    question: str,
    business_account_id: str = "",
    chat_history: Optional[list] = None,
    user_id: str = "dashboard-user",
    request_id: str = "unknown",
) -> dict:
    """Ask the Oversight Brain a question, returns explanation with sources.

    No bind_tools() — uses direct llm.invoke() with tool descriptions in prompt.
    LLM optionally requests tools via <<TOOL_CALL:...>> text syntax.
    """
    start = time.time()

    # --- L1 / L2 cache (skip if conversation history changes context) ---
    cache_key = _cache_key(question, business_account_id)
    if not chat_history:
        if cache_key in _question_cache:
            logger.info(f"[{request_id}] Oversight Brain L1 cache hit")
            return {**_question_cache[cache_key], "request_id": request_id, "latency_ms": 0, "cached": True}

        l2 = _cache_get(cache_key)
        if l2:
            _question_cache[cache_key] = l2
            logger.info(f"[{request_id}] Oversight Brain L2 cache hit")
            return {**l2, "request_id": request_id, "latency_ms": 0, "cached": True}

    # --- Build prompt ---
    history_text = ""
    if chat_history:
        for msg in chat_history[-5:]:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")[:300]
            history_text += f"{role}: {content}\n"

    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT
    auto_context = await _fetch_auto_context(business_account_id, limit=OVERSIGHT_AUTO_CONTEXT_LIMIT)

    prompt = (
        "INSTRUCTION: You are in read-only explainability mode. "
        "Answer from the injected context below. Use tools only if specific data is genuinely absent.\n"
        + _build_tool_descriptions()
        + "\n\n"
        + PromptService.get("oversight_brain").format(
            input=f"{auto_context}\n\n{question}",
            chat_history=history_text or "(No prior conversation)",
        )
    )

    # --- LLM call with semaphore + outer timeout ---
    from config import OVERSIGHT_LLM_TIMEOUT_SECONDS
    tools_called = []
    final_text = ""

    try:
        async with _llm_semaphore:
            async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
                raw_result = await asyncio.to_thread(llm.invoke, prompt)

    except asyncio.TimeoutError:
        logger.warning(f"[{request_id}] Oversight Brain LLM timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
        final_text = "I timed out while generating a response. Please try again."
        raw_result = None

    except Exception as e:
        logger.error(f"[{request_id}] Oversight LLM invoke failed: {e}")
        final_text = f"An error occurred: {e}"
        raw_result = None

    if raw_result:
        raw_text = raw_result.content if hasattr(raw_result, "content") else str(raw_result)
        # Remove any tool call markers from text before parsing
        cleaned = re.sub(r"<<TOOL_CALL:[^>]+>>", "", raw_text)
        final_text = cleaned.strip()

        # Parse and execute any tool calls found in the text
        calls = _parse_tool_calls(raw_text)
        if calls:
            for call in calls:
                tool_result = await _execute_oversight_tool(call["name"], call["args"])
                tools_called.append(call["name"])

                # Second pass: inject tool result and ask for final answer
                second_prompt = (
                    f"{prompt}\n\n"
                    f"[TOOL_RESULT for {call['name']}]:\n{json.dumps(tool_result, default=str, indent=2)}\n\n"
                    "Using the tool result above, provide your final answer as JSON."
                )
                try:
                    async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
                        second_result = await asyncio.to_thread(llm.invoke, second_prompt)
                    second_text = second_result.content if hasattr(second_result, "content") else str(second_result)
                    # Clean tool markers from second pass too
                    final_text = re.sub(r"<<TOOL_CALL:[^>]+>>", "", second_text).strip()
                except Exception as e2:
                    logger.warning(f"[{request_id}] Oversight second-pass failed: {e2}")
                    # Use the cleaned first-pass text as fallback
                    final_text = cleaned.strip()

    # --- Parse JSON from LLM response ---
    parsed = _parse_json_response_blocking(final_text)
    latency_ms = int((time.time() - start) * 1000)

    response = {
        "answer": parsed.get("answer", final_text or "I need more context from the database to answer that."),
        "sources": parsed.get("sources", []),
        "tools_used": tools_called,
        "latency_ms": latency_ms,
        "request_id": request_id,
    }

    # --- Store in cache (no-history questions only) ---
    if not chat_history:
        cacheable = {k: v for k, v in response.items() if k not in ("request_id", "latency_ms")}
        _question_cache[cache_key] = cacheable
        _cache_set(cache_key, cacheable, ttl=300)

    # --- Audit every query ---
    SupabaseService.log_decision(
        event_type="oversight_chat_query",
        action="error" if "error" in parsed else "answered",
        resource_type="oversight_query",
        resource_id=str(uuid_mod.uuid4()),
        user_id=user_id,
        details={
            "question": question[:500],
            "answer": response["answer"][:500],
            "business_account_id": business_account_id,
            "tools_used": tools_called,
            "latency_ms": latency_ms,
            "request_id": request_id,
            "streamed": False,
        },
    )

    logger.info(
        f"[{request_id}] Oversight Brain answered in {latency_ms}ms "
        f"(tools: {tools_called}, sources: {len(response['sources'])})"
    )
    return response


def _parse_json_response_blocking(raw: str) -> dict:
    """Parse JSON from LLM response text — handles raw, markdown, partial."""
    import json as json_mod

    cleaned = raw.strip()

    # Direct parse
    try:
        return json_mod.loads(cleaned)
    except json_mod.JSONDecodeError:
        pass

    # Markdown code block
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if code_block_match:
        try:
            return json_mod.loads(code_block_match.group(1))
        except json_mod.JSONDecodeError:
            pass

    # First { ... } block
    brace_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
    if brace_match:
        try:
            return json_mod.loads(brace_match.group(0))
        except json_mod.JSONDecodeError:
            pass

    logger.warning(f"Oversight: failed to parse JSON from response: {cleaned[:200]}...")
    return {}  # Return empty dict — caller uses answer field as fallback


async def astream_chat(
    question: str,
    business_account_id: str = "",
    chat_history: Optional[list] = None,
    user_id: str = "dashboard-user",
    request_id: str = "unknown",
    request=None,  # FastAPI Request for disconnect detection
):
    """Streaming version — direct llm.astream(), no bind_tools().

    Features:
    - Tool descriptions embedded in prompt as readable text
    - Optional tool calls via <<TOOL_CALL:...>> text syntax
    - Tool execution triggers "tool_status" SSE event (user sees "thinking...")
    - Second-pass LLM stream delivers final answer after tool results injected
    - Event IDs, heartbeat pings, disconnect detection — all preserved
    """
    from config import OVERSIGHT_AUTO_CONTEXT_LIMIT, OVERSIGHT_LLM_TIMEOUT_SECONDS, SSE_HEARTBEAT_INTERVAL_SECONDS

    start = time.time()
    event_id = 0
    accumulated = ""

    # Helper: format SSE event with id and event type
    def format_sse_event(payload: dict, event_type: str = "message") -> str:
        nonlocal event_id
        event_id += 1
        data = json.dumps(payload)
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

    prompt = (
        "INSTRUCTION: You are in read-only explainability mode. "
        "Answer from the injected context below. Use tools only if specific data is genuinely absent.\n"
        + _build_tool_descriptions()
        + "\n\n"
        + PromptService.get("oversight_brain").format(
            input=f"{auto_context}\n\n{question}",
            chat_history=history_text or "(No prior conversation)",
        )
    )

    # Shared queue: both background tasks write here; generator reads and yields.
    # Queue is consumed item-by-item as events arrive — heartbeats are never
    # delayed behind LLM tokens because LLM tokens don't exist in the queue yet
    # during inference. The generator sits at queue.get() and wakes immediately
    # on whichever event arrives first.
    event_queue: asyncio.Queue = asyncio.Queue()
    tool_was_called = False

    async def run_llm():
        """Background task: run direct LLM stream, detect tool call markers, execute tools."""
        nonlocal tool_was_called
        try:
            async with _llm_semaphore:
                # First pass: stream tokens, detect tool call markers
                buffer = ""
                tool_call_detected = False
                tool_call_full = ""  # accumulate the complete <<TOOL_CALL:...>> block

                async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
                    async for chunk in llm.astream(prompt):
                        text = chunk.content if hasattr(chunk, "content") else ""
                        if not text:
                            continue

                        # Track if we're inside a tool call marker
                        if TOOL_CALL_OPEN in buffer or tool_call_detected:
                            tool_call_detected = True
                            tool_call_full += text
                            buffer += text
                            # Keep yielding text BEFORE the tool marker (preface)
                            # We yield after the tool marker is complete
                            if TOOL_CALL_CLOSE in tool_call_full:
                                # Extract text before marker, yield that
                                marker_start = tool_call_full.find(TOOL_CALL_OPEN)
                                before_marker = tool_call_full[:marker_start]
                                if before_marker:
                                    accumulated_local = before_marker
                                    await event_queue.put(("token", accumulated_local))
                                break
                        else:
                            buffer += text
                            await event_queue.put(("token", text))

                # Check if a tool call was detected
                if tool_call_detected and tool_call_full:
                    # Parse tool call
                    calls = _parse_tool_calls(tool_call_full)
                    if calls:
                        tool_was_called = True
                        call = calls[0]  # handle one at a time
                        logger.info(f"[{request_id}] Oversight LLM requested tool: {call['name']}")

                        # Tell user tool is being called
                        await event_queue.put(("tool_status", {
                            "status": "calling",
                            "tool_name": call["name"],
                            "message": f"Fetching {call['name']} data...",
                        }))

                        # Execute tool
                        tool_result = await _execute_oversight_tool(call["name"], call["args"])

                        # Second pass: inject result, stream final answer
                        second_prompt = (
                            f"{prompt}\n\n"
                            f"[TOOL_RESULT for {call['name']}]:\n{json.dumps(tool_result, default=str, indent=2)}\n\n"
                            "Using the tool result above, provide your final answer as JSON."
                        )

                        async with asyncio.timeout(OVERSIGHT_LLM_TIMEOUT_SECONDS):
                            async for chunk in llm.astream(second_prompt):
                                text = chunk.content if hasattr(chunk, "content") else ""
                                if text:
                                    # Clean any residual tool markers
                                    cleaned = re.sub(r"<<TOOL_CALL:[^>]+>>", "", text)
                                    if cleaned:
                                        await event_queue.put(("token", cleaned))

        except asyncio.TimeoutError:
            logger.warning(f"[{request_id}] Oversight stream timed out after {OVERSIGHT_LLM_TIMEOUT_SECONDS}s")
            await event_queue.put(("error", {"error": "timeout", "message": "LLM timed out"}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{request_id}] Oversight stream error: {e}")
            await event_queue.put(("error", {"error": "stream_failed", "message": str(e)}))
        finally:
            await event_queue.put(("stream_done", None))

    async def heartbeat_loop():
        """Background task: post a ping every N seconds while LLM is running."""
        while True:
            try:
                await asyncio.sleep(SSE_HEARTBEAT_INTERVAL_SECONDS)
                await event_queue.put(("heartbeat", None))
                SSE_HEARTBEATS_SENT.labels(endpoint="oversight").inc()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[{request_id}] Heartbeat error: {e}")
                break

    SSE_ACTIVE_STREAMS.labels(endpoint="oversight").inc()

    # Start both tasks — they run concurrently and independently
    llm_task = asyncio.create_task(run_llm())
    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        while True:
            try:
                event_type, event_data = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=OVERSIGHT_LLM_TIMEOUT_SECONDS + 10,  # outer safety net
                )
            except asyncio.TimeoutError:
                logger.warning(f"[{request_id}] Queue drain safety timeout — forcing stream end")
                break

            if await is_disconnected():
                logger.info(f"[{request_id}] Client disconnected")
                SSE_DISCONNECTS.labels(endpoint="oversight").inc()
                llm_task.cancel()
                break

            if event_type == "heartbeat":
                yield format_sse_event({"heartbeat": True}, event_type="ping")

            elif event_type == "tool_status":
                yield format_sse_event(event_data, event_type="tool_status")

            elif event_type == "token":
                accumulated += event_data
                yield format_sse_event({"token": event_data}, event_type="message")

            elif event_type == "error":
                yield format_sse_event(event_data, event_type="error")
                break

            elif event_type == "stream_done":
                break

    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if not llm_task.done():
            llm_task.cancel()
            try:
                await llm_task
            except asyncio.CancelledError:
                pass
        SSE_ACTIVE_STREAMS.labels(endpoint="oversight").dec()

    # Final completion event — always emitted so the frontend persistMessage() fires
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
            "tool_called": tool_was_called,
        },
    )

    logger.info(f"[{request_id}] Oversight Brain streamed in {latency_ms}ms ({event_id} events)")
