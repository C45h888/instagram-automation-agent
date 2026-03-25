  ## BUG: oversight_brain.py — heartbeat_loop creates concurrency deadlock with LLM stream

  ### What is broken

  In `astream_chat()`, the Flask app creates TWO concurrent tasks:
  1. `run_llm()` — streams tokens from Ollama and writes ("token", text) to event_queue
  2. `heartbeat_loop()` — sleeps 10s and writes ("heartbeat", None) to the SAME event_queue

  Meanwhile, the main loop reads from event_queue using:
    event_type, event_data = await asyncio.wait_for(event_queue.get(), timeout=25s)

  For a small 8B model (llama3.1:8b), tokens arrive in 2-5 seconds. The heartbeat_loop
  fires every 10s and fills the queue with ("heartbeat", None), competing with token writes.
  This causes:
  - Token events being starved by heartbeat events in the queue
  - The wait_for timeout (25s) firing while LLM is still producing tokens
  - The main loop breaking early, never yielding token events to the caller

  ### The Express backend ALREADY handles heartbeats correctly

  In backend.api/routes/agents/oversight.js, Express sends:
    res.write(': ping\\n\\n')   // every 15 seconds via setInterval

  This is the correct SSE keepalive mechanism. Flask's heartbeat_loop is redundant
  AND creates a concurrency race condition.

  ### What to do

  1. REMOVE the heartbeat_loop entirely — delete the function and the asyncio.create_task call
  2. REMOVE the SSE_HEARTBEAT_INTERVAL_SECONDS and SSE_HEARTBEATS_SENT metric references
  3. SIMPLIFY the main loop — just stream tokens directly, no queue needed
  4. Keep the Express backend's : ping\\n\\n as the sole heartbeat mechanism
  5. Keep SSE_ACTIVE_STREAMS and SSE_DISCONNECTS metrics (those are fine)

  ### Important: do NOT remove any of these (they are correct):
  - The tool call handling in run_llm() — tool calls via <<TOOL_CALL:...>> syntax are valid
  - The _execute_oversight_tool() call — tool execution is needed for live data
  - The error handling with asyncio.TimeoutError — timeouts are still valid safety nets
  - The client disconnect check — is_disconnected() is still useful

  ### Only remove:
  - heartbeat_loop function
  - SSE_HEARTBEAT_INTERVAL_SECONDS and SSE_HEARTBEATS_SENT metric
  - The asyncio.Queue event_queue mechanism (replace with direct yield)
  - The run_llm() background task pattern (simplify to direct streaming)

  ---
  Plan for Backend Repo (No changes needed)

  The Express backend (backend.api/routes/agents/oversight.js) is correct as-is. It:
  - Sends : ping\n\n SSE comment lines every 15s — ✅ correct keepalive
  - Uses setInterval (not async) — ✅ doesn't compete with event loop
  - Writes to res directly, not a shared queue — ✅ no race condition