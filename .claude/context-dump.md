#AgentService Tool Binding Architecture                                               
                                                                                       
  Core Principle                                                                       
                                                                                       
  AgentService is the single binding layer for all LLM+tools invocations. All pipelines
   route through llm.bind_tools() — never call llm.invoke() directly in production     
  paths.                                                                               
                                                                                       
  ┌─────────────────────────────────────────────────────────────┐
  │  Scheduler (engagement_monitor / dm_monitor)                │                      
  │      │                                                     │
  │      ├── _build_agent_prompt()                              │                      
  │      │       └── PromptService.get("analyze_message_agent") │
  │      │                                                     │                       
  │      └── agent.astream_analyze(prompt)                     │                     
  │              └── llm.bind_tools(ENGAGEMENT_SCOPE_TOOLS)   │                        
  │                      └── LLM calls tools via tool_calls     │
  │                              get_post_context              │                       
  │                              get_account_info              │                     
  │                              get_recent_comments           │                       
  │                              get_dm_history                │                     
  │                              get_dm_conversation_context   │
  │                                                             │                      
  │              ┌─── Accumulate streaming tokens ───┐         │
  │              │   Parse JSON → apply hard rules  │         │                        
  │              └─── Route: escalate / auto-reply / skip ──┘  │                       
  │                      │                                    │
  │                      └── _reply_to_comment() / _reply_to_dm() │                    
  │                              └── Python-side OutboundQueue  │                      
  └─────────────────────────────────────────────────────────────┘
                                                                                       
  Why This Architecture                                                              

  ┌────────────────────────────────────┬───────────────────────────────────────────┐   
  │       Old Pattern (REMOVED)        │           New Pattern (ACTIVE)            │ 
  ├────────────────────────────────────┼───────────────────────────────────────────┤   
  │ LLMService.invoke() directly — LLM │ AgentService.astream_analyze() — LLM      │ 
  │  never saw tools                   │ calls tools via bind_tools()              │ 
  ├────────────────────────────────────┼───────────────────────────────────────────┤   
  │ Python pre-fetched ALL context     │ LLM fetches context only when             │ 
  │ (slow, wasteful)                   │ pre-injected data is insufficient         │   
  ├────────────────────────────────────┼───────────────────────────────────────────┤ 
  │ analyze_message_tool in scope →    │ analyze_message_tool removed from scope   │   
  │ recursion loop                     │                                           │ 
  ├────────────────────────────────────┼───────────────────────────────────────────┤ 
  │ reply_to_comment_tool in scope +   │ Execution stays Python-side via           │
  │ Python call → double execution     │ OutboundQueue                             │   
  ├────────────────────────────────────┼───────────────────────────────────────────┤
  │ log_decision in scope + Python     │ log_decision removed from scope; Python   │   
  │ call → double audit entries        │ logs deterministically                    │   
  └────────────────────────────────────┴───────────────────────────────────────────┘
                                                                                       
  ---                                                                                
  Scoped Tool Sets

  Defined in agent/services/agent_service.py:

  ENGAGEMENT_SCOPE_TOOLS = [
      get_post_context,              # Post caption, likes, engagement_rate
      get_account_info,             # Username, followers, account_type                
      get_recent_comments,          # Account-level comment patterns (NOT thread)
      get_dm_history,               # Prior DM messages for sender context             
      get_dm_conversation_context,  # 24h reply window status for DM                 
      # log_decision — Python-only (no duplication)                                    
      # analyze_message_tool — removed (recursion loop)                              
      # reply_to_comment_tool — removed (Python executes via _reply_to_comment())      
      # reply_to_dm_tool — removed (Python executes via _reply_to_dm())                
  ]
                                                                                       
  CONTENT_SCOPE_TOOLS = [                                                            
      get_post_context,
      get_account_info,
      get_post_performance,                                                            
      log_decision,
  ]                                                                                    
                                                                                     
  ATTRIBUTION_SCOPE_TOOLS = [
      get_dm_history,
      get_account_info,
      log_decision,
  ]
                                                                                       
  ---
  Supabase Tools (read-only, LLM-decided gap fillers)                                  
                                                                                     
  All from agent/tools/supabase_tools.py — @tool-decorated functions, NO Pydantic
  schemas:                                                                             
   
  ┌─────────────────────────────┬─────────────────────────┬────────────────────────┐   
  │            Tool             │         Purpose         │        Used By         │ 
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤ 
  │ get_post_context            │ Post caption, likes,    │ Engagement             │ 
  │                             │ engagement_rate         │                        │ 
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤ 
  │ get_account_info            │ Username, followers,    │ Engagement, Content,   │   
  │                             │ account_type            │ Attribution            │ 
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤   
  │ get_recent_comments         │ Account-level comment   │ Engagement             │ 
  │                             │ patterns                │                        │ 
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤ 
  │ get_dm_history              │ Prior DM messages       │ Engagement,            │ 
  │                             │                         │ Attribution            │   
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤ 
  │ get_dm_conversation_context │ 24h reply window status │ Engagement             │   
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤ 
  │ get_post_performance        │ Average engagement      │ Content                │
  │                             │ benchmarks              │                        │   
  ├─────────────────────────────┼─────────────────────────┼────────────────────────┤
  │ log_decision                │ Audit trail entries     │ Content, Attribution   │   
  │                             │                         │ (NOT Engagement)       │ 
  └─────────────────────────────┴─────────────────────────┴────────────────────────┘

  ---
  Automation Tools (Python-only execution)
                                          
  All from agent/tools/automation_tools.py — NOT in any scope, called directly by
  Python:                                                                              
   
  ┌────────────────────────────────┬──────────────────────┬────────────────────────┐   
  │            Function            │       Purpose        │       Called By        │ 
  ├────────────────────────────────┼──────────────────────┼────────────────────────┤   
  │                                │ VIP, urgent          │ engagement_monitor,    │
  │ _apply_hard_escalation_rules() │ keywords, complaints │ dm_monitor             │   
  │                                │  override            │                        │ 
  ├────────────────────────────────┼──────────────────────┼────────────────────────┤
  │ _reply_to_comment()            │ Backend proxy →      │ engagement_monitor     │
  │                                │ Instagram API        │                        │   
  ├────────────────────────────────┼──────────────────────┼────────────────────────┤
  │ _reply_to_dm()                 │ Backend proxy →      │ dm_monitor             │   
  │                                │ Instagram API        │                        │ 
  └────────────────────────────────┴──────────────────────┴────────────────────────┘

  ---
  Prompts
         
  ┌───────────────────────────────┬──────────────────┬────────────────────────────┐ 
  │              Key              │     Used By      │           Route            │    
  ├───────────────────────────────┼──────────────────┼────────────────────────────┤ 
  │ analyze_message_agent         │ engagement_monit │ → AgentService.astream_ana │    
  │                               │ or, dm_monitor   │ lyze()                     │  
  ├───────────────────────────────┼──────────────────┼────────────────────────────┤ 
  │                               │ Webhooks         │ → _analyze_message()       │ 
  │ analyze_message               │ (backward        │ directly                   │    
  │                               │ compat)          │                            │ 
  ├───────────────────────────────┼──────────────────┼────────────────────────────┤    
  │ generate_and_evaluate_caption │ content_schedule │ → AgentService.analyze_asy │  
  │                               │ r                │ nc()                       │ 
  ├───────────────────────────────┼──────────────────┼────────────────────────────┤
  │ generate_and_evaluate_attribu │ attribution_tool │ → AgentService.analyze_asy │    
  │ tion                          │ s                │ nc()                       │
  ├───────────────────────────────┼──────────────────┼────────────────────────────┤    
  │ oversight_brain               │ oversight_brain  │ → AgentService.analyze_asy │  
  │                               │                  │ nc()                       │    
  └───────────────────────────────┴──────────────────┴────────────────────────────┘
                                                                                       
  ---                                                                                
  Safety Flow

  LLM returns JSON
          ↓
  AgentService._parse_json_response()
          ↓
  _apply_hard_escalation_rules()  ← Python safety override
          ↓                                                                            
  VIP? → escalate
  Urgent keyword? → escalate                                                           
  Negative complaint? → escalate                                                     
          ↓
  Route: escalate / auto-reply / skip

  ---                                                                                  
  Instance Lifecycle
                                                                                       
  One AgentService(scope="engagement") instance per run — created once in            
  engagement_monitor_run() / dm_monitor_run(), shared across all accounts and all      
  messages. Amortizes bind_tools() initialization cost.
                                                                                       
  ---                                                                                
  Engagement Monitor Flow

  engagement_monitor_run()
      │
      └── agent = AgentService(scope="engagement")  ← once per run
              │                                                                        
              └── for each account:
                      └── _process_account(agent)                                      
                              │                                                      
                              └── for each comment (parallel, semaphore-limited):
                                      │                                                
                                      ├── _build_agent_prompt()
                                      │       └──                                      
  PromptService.get("analyze_message_agent")                                         
                                      │
                                      ├── agent.astream_analyze(prompt)
                                      │       └──
  llm.bind_tools(ENGAGEMENT_SCOPE_TOOLS)                                               
                                      │               └── LLM calls tools as needed
                                      │                                                
                                      ├── AgentService._parse_json_response()        
                                      │
                                      ├── _apply_hard_escalation_rules()  ← safety
                                      │                                                
                                      └── Route:
                                              ├── needs_human=true →                   
  _handle_escalation()                                                               
                                              ├── confidence >= threshold →
  _handle_auto_reply()                                                                 
                                              │       └── _reply_to_comment() →
  OutboundQueue                                                                        
                                              └── else → _handle_skip()              

  ---
  DM Monitor Flow
                 
  Same pattern as Engagement Monitor, with:
  - AgentService(scope="engagement") — shared per run                                  
  - _build_agent_prompt(message_type="dm", ...) — DM-specific prompt
  - _reply_to_dm() instead of _reply_to_comment()                                      
  - get_dm_history and get_dm_conversation_context available to LLM                    
  
  ---                                                                                  
  Verification                                                                       
                                                                                       
  # Check ENGAGEMENT_SCOPE_TOOLS has exactly 5 tools                                 
  python -c "from services.agent_service import AgentService; a = 
  AgentService(scope='engagement'); print(sorted(a._tool_map.keys()))"                 
  # Expected: ['get_account_info', 'get_dm_conversation_context', 'get_dm_history', 
  'get_post_context', 'get_recent_comments']                                           
                                                                                     
⏺ Ran 1 stop hook (ctrl+o to expand)                                                   
  ⎿  Stop hook error: Failed with non-blocking status code: /bin/sh:                   
  /Users/kamii/.claude/plugins/marketplaces/claude-plugins-official/plugins/ral
  ph-loop/hooks/stop-hook.sh: Permission denied
                                                                                       
✻ Crunched for 1m 33s
                                                                                       
──────────────────────────────────────────────────────────────────────── toolbinding ──
❯  
───────────────────────────────────────────────────────────────────────────────────────
  ? for shortcuts                                               ⧉ In agent_service.py
                                                                                       
