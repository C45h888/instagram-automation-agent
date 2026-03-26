agent_service.py — Function Audit
Function	Status	Used by	Issues
__init__()	✅ Works	Nobody (DEAD)	Tool binding logic correct. Scoped tools correct. Never instantiated.
analyze_async()	✅ Works	Nobody (DEAD)	Async entry + semaphore. Never called.
_analyze()	✅ Works	Nobody (DEAD)	2-pass flow, parallel tool execution, 5s timeout. No LLM retry (semaphore prevents overload, but transient errors still fail hard).
_astream()	✅ Works	Nobody (DEAD)	2-pass streaming. No retry — if stream drops mid-way, client gets nothing.
_execute_tool_calls_async()	✅ Works	Nobody (DEAD)	Parallel tool exec + 5s timeout per tool. Correct.
_build_enriched_prompt()	✅ Works	Nobody (DEAD)	Prompt enrichment. Correct.
_parse_json_response()	✅ Works (duplicate)	4 tool files	Identical to LLMService._parse_json_response() — duplicate logic in two places.
 What Is Broken in agent_service
_analyze() — LLM retry missing

Problem: If llm_with_tools.invoke() fails (connection drop, 503 busy),
the whole request fails. No retry.

Fix: Route through LLMService.invoke() with retry+backoff.
_astream() — No retry on streaming

Problem: self.llm_with_tools.astream() has no retry.
If connection drops mid-stream → generator dies → client gets nothing.

Fix: Add per-pass retry inside _astream().
Streaming retry is different from invoke retry:
  - Stream starts → yields tokens to client in real time
  - Stream fails → retry restarts the whole pass from beginning
  - Client may have already received partial text
  - This is acceptable for streaming — can't buffer mid-stream
_parse_json_response() — Duplicate logic

LLMService._parse_json_response() and AgentService._parse_json_response()
are identical. Keep one, remove the other.

