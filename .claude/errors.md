docker compose -f docker-compose.unified.yml logs -f langchain-agent && ollama
WARN[0000] The "N8N_COMMENT_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_ORDER_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_DM_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_BASE_URL" variable is not set. Defaulting to a blank string. 
langchain-agent  | 2026-03-21 12:28:45,086 [INFO] oversight-agent: Redis connected at redis:6379
langchain-agent  | INFO:     Started server process [1]
langchain-agent  | INFO:     Waiting for application startup.
langchain-agent  | 2026-03-21 12:28:45,310 [INFO] oversight-agent: ============================================================
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent: Oversight Brain Agent starting up
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Ollama Host: http://ollama:11434
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Model: hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q4_K_M
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Rate Limit: 60/min global, 20/min on /oversight/chat (per-user), 10/min on /webhook/*
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   CORS Origins: ['https://app.888intelligenceautomation.in', 'https://api.888intelligenceautomation.in', 'https://agent.888intelligenceautomation.in']
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Webhook Endpoints: /webhook/comment, /webhook/dm, /webhook/order-created, /log-outcome
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Scheduler: /engagement-monitor/*, /content-scheduler/*, /sales-attribution/*
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent:   Utility: /health, /metrics
langchain-agent  | 2026-03-21 12:28:45,311 [INFO] oversight-agent: ============================================================
langchain-agent  | 2026-03-21 12:28:45,546 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:45,557 [INFO] oversight-agent: Supabase connection verified successfully
langchain-agent  | 2026-03-21 12:28:45,708 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=caption%2Clike_count%2Ccomments_count%2Creach%2Cpublished_at&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:45,709 [INFO] oversight-agent: Schema OK: instagram_media
langchain-agent  | 2026-03-21 12:28:45,862 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=username%2Cname%2Caccount_type%2Cfollowers_count&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:45,865 [INFO] oversight-agent: Schema OK: instagram_business_accounts
langchain-agent  | 2026-03-21 12:28:46,021 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=text%2Csentiment%2Cbusiness_account_id%2Ccreated_at%2Cprocessed_by_automation%2Cautomated_response_sent%2Cresponse_text%2Cmedia_id%2Cinstagram_comment_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,023 [INFO] oversight-agent: Schema OK: instagram_comments
langchain-agent  | 2026-03-21 12:28:46,176 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=customer_instagram_id%2Cbusiness_account_id%2Cwithin_window%2Cwindow_expires_at%2Cconversation_status%2Cinstagram_thread_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,176 [INFO] oversight-agent: Schema OK: instagram_dm_conversations
langchain-agent  | 2026-03-21 12:28:46,356 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=message_text%2Cconversation_id%2Cis_from_business%2Csent_at&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,358 [INFO] oversight-agent: Schema OK: instagram_dm_messages
langchain-agent  | 2026-03-21 12:28:46,513 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=event_type%2Caction%2Cdetails%2Cresource_type&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,514 [INFO] oversight-agent: Schema OK: audit_log
langchain-agent  | 2026-03-21 12:28:46,515 [INFO] oversight-agent: All required schema validations passed
langchain-agent  | 2026-03-21 12:28:46,666 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/prompt_templates?select=prompt_key%2Ctemplate%2Cversion%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,668 [INFO] oversight-agent: Schema OK (optional): prompt_templates
langchain-agent  | 2026-03-21 12:28:46,831 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_assets?select=business_account_id%2Cstorage_path%2Ctags%2Clast_posted%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:46,833 [INFO] oversight-agent: Schema OK (optional): instagram_assets
langchain-agent  | 2026-03-21 12:28:47,015 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/scheduled_posts?select=business_account_id%2Cstatus%2Cgenerated_caption%2Cagent_quality_score%2Crun_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,017 [INFO] oversight-agent: Schema OK (optional): scheduled_posts
langchain-agent  | 2026-03-21 12:28:47,178 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/sales_attributions?select=order_id%2Corder_value%2Cattribution_score%2Cauto_approved%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,184 [INFO] oversight-agent: Schema OK (optional): sales_attributions
langchain-agent  | 2026-03-21 12:28:47,328 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/attribution_review_queue?select=order_id%2Creview_status%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,329 [INFO] oversight-agent: Schema OK (optional): attribution_review_queue
langchain-agent  | 2026-03-21 12:28:47,497 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/attribution_models?select=weights%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,498 [INFO] oversight-agent: Schema OK (optional): attribution_models
langchain-agent  | 2026-03-21 12:28:47,646 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_monitored_hashtags?select=business_account_id%2Chashtag%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,648 [INFO] oversight-agent: Schema OK (optional): ugc_monitored_hashtags
langchain-agent  | 2026-03-21 12:28:47,818 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_content?select=visitor_post_id%2Cbusiness_account_id%2Cauthor_username%2Cmessage%2Cmedia_type%2Cmedia_url%2Cquality_score%2Cquality_tier%2Csource&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,821 [INFO] oversight-agent: Schema OK (optional): ugc_content
langchain-agent  | 2026-03-21 12:28:47,968 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_permissions?select=ugc_content_id%2Cbusiness_account_id%2Cstatus%2Crequest_message%2Crun_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:47,969 [INFO] oversight-agent: Schema OK (optional): ugc_permissions
langchain-agent  | 2026-03-21 12:28:48,126 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/analytics_reports?select=business_account_id%2Creport_type%2Creport_date%2Cinstagram_metrics%2Cinsights&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:48,127 [INFO] oversight-agent: Schema OK (optional): analytics_reports
langchain-agent  | 2026-03-21 12:28:48,271 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=job_id%2Caction_type%2Cpriority%2Cendpoint%2Cpayload%2Cstatus%2Cretry_count&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:48,273 [INFO] oversight-agent: Schema OK (optional): outbound_queue_jobs
langchain-agent  | 2026-03-21 12:28:48,420 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/system_alerts?select=business_account_id%2Calert_type%2Cmessage%2Cdetails%2Cresolved&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:48,421 [INFO] oversight-agent: Schema OK (optional): system_alerts
langchain-agent  | 2026-03-21 12:28:48,567 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/prompt_templates?select=prompt_key%2C%20template%2C%20version&is_active=eq.True "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:48,569 [INFO] oversight-agent: Prompt versions: {'comment': 0, 'dm': 0, 'post': 0, 'analyze_message': 0, 'generate_and_evaluate_caption': 0, 'generate_and_evaluate_attribution': 0, 'generate_analytics_insights': 0, 'oversight_brain': 0}
langchain-agent  | 2026-03-21 12:28:48,575 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,575 [INFO] oversight-agent: DM Monitor scheduled (every 5 min)
langchain-agent  | 2026-03-21 12:28:48,575 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,575 [INFO] oversight-agent: Engagement Monitor scheduled (every 5 min)
langchain-agent  | 2026-03-21 12:28:48,581 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,582 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,582 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,582 [INFO] oversight-agent: Content Scheduler scheduled at 09:00, 14:00, 19:00
langchain-agent  | 2026-03-21 12:28:48,582 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,582 [INFO] oversight-agent: Weekly Attribution Learning scheduled (mon at 08:00)
langchain-agent  | 2026-03-21 12:28:48,583 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,583 [INFO] oversight-agent: UGC Collection scheduled (every 4 hours)
langchain-agent  | 2026-03-21 12:28:48,583 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,584 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,584 [INFO] oversight-agent: Analytics Reports scheduled (daily at 23:00, weekly on sun at 23:00)
langchain-agent  | 2026-03-21 12:28:48,584 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-21 12:28:48,584 [INFO] oversight-agent: Heartbeat Sender scheduled (every 20 min)
langchain-agent  | 2026-03-21 12:28:48,585 [INFO] apscheduler.scheduler: Added job "DM Monitor" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,585 [INFO] apscheduler.scheduler: Added job "Engagement Monitor" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,585 [INFO] apscheduler.scheduler: Added job "Content Scheduler (09:00)" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,585 [INFO] apscheduler.scheduler: Added job "Content Scheduler (14:00)" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "Content Scheduler (19:00)" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "Weekly Attribution Learning" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "UGC Collection" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "Analytics Daily Report" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "Analytics Weekly Report" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Added job "Heartbeat Sender" to job store "default"
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] apscheduler.scheduler: Scheduler started
langchain-agent  | 2026-03-21 12:28:48,586 [INFO] oversight-agent: Scheduler started
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent: QueueWorker started: 3 background loops (high, normal, retry)
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   Outbound Queue Worker: enabled
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   DM Monitor: enabled (webhook fallback, every 5 min)
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   Engagement Monitor: enabled
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   Content Scheduler: enabled
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   Sales Attribution: enabled
langchain-agent  | 2026-03-21 12:28:48,599 [INFO] oversight-agent:   Weekly Learning: enabled
langchain-agent  | 2026-03-21 12:28:48,600 [INFO] oversight-agent:   UGC Collection: enabled
langchain-agent  | 2026-03-21 12:28:48,600 [INFO] oversight-agent:   Analytics Reports: enabled
langchain-agent  | 2026-03-21 12:28:48,600 [INFO] oversight-agent:   Heartbeat Sender: enabled (interval: 20min, agent_id: 08408f8d-68ae-40b8-a32a-607c0a03dea0)
langchain-agent  | 2026-03-21 12:28:48,600 [INFO] oversight-agent:   Oversight Brain: /oversight/chat (auth+20/minute/user), /oversight/status (public), streaming=enabled
langchain-agent  | 2026-03-21 12:28:48,743 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/scheduled_posts?select=id%2C%20business_account_id%2C%20generated_caption%2C%20asset_id&status=eq.publishing&updated_at=lt.2026-03-21T11%3A58%3A48.601260%2B00%3A00 "HTTP/2 200 OK"
langchain-agent  | INFO:     Application startup complete.
langchain-agent  | INFO:     Uvicorn running on http://0.0.0.0:3002 (Press CTRL+C to quit)
langchain-agent  | 2026-03-21 12:28:48,902 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:53,474 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:53,637 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:53,789 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:53,938 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:54,091 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:28:54,246 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:53910 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:29:19,277 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:24,553 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:24,690 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:24,825 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:24,970 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:25,105 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:25,265 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:42868 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:29:49,452 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:55,578 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:55,727 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:55,864 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:55,995 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:56,129 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:29:56,276 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:49676 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:30:19,838 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:26,534 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:26,673 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:27,031 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:27,176 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:27,342 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:27,481 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:45764 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:30:50,207 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:57,746 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:57,893 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:58,033 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:58,163 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:58,297 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:30:58,424 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:42286 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:31:20,404 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:28,772 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:28,912 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:29,068 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:29,211 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:29,373 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:29,512 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:35472 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:31:50,586 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:59,801 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:31:59,941 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:00,079 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:00,224 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:00,361 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:00,496 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:58610 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:32:20,741 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,219 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,358 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,488 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,620 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,760 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:32:31,894 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:59200 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:32:50,909 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,143 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,278 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,410 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,541 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,673 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:02,802 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:54516 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:33:21,117 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,090 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,232 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,361 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,493 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,636 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:33,771 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:56940 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:33:48,576 [INFO] apscheduler.executors.default: Running job "DM Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:38:48 UTC)" (scheduled at 2026-03-21 12:33:48.574677+00:00)
langchain-agent  | 2026-03-21 12:33:48,577 [INFO] oversight-agent: [dede0d7b-6bcb-4998-aa73-c2278121b45a] DM monitor cycle starting
langchain-agent  | 2026-03-21 12:33:48,768 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:48,773 [INFO] oversight-agent: [dede0d7b-6bcb-4998-aa73-c2278121b45a] Found 1 active account(s)
langchain-agent  | 2026-03-21 12:33:48,926 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id%2C%20instagram_message_id%2C%20message_text%2C%20sent_at%2C%20conversation_id%2C%20business_account_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&is_from_business=eq.False&processed_by_automation=eq.False&sent_at=gte.2026-03-20T12%3A33%3A48.774607%2B00%3A00&order=sent_at&limit=20 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:49,067 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-21 12:33:49,069 [INFO] oversight-agent: [dede0d7b-6bcb-4998-aa73-c2278121b45a] DM monitor cycle complete (0.4s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-21 12:33:49,070 [INFO] apscheduler.executors.default: Job "DM Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:38:48 UTC)" executed successfully
langchain-agent  | 2026-03-21 12:33:49,071 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:38:48 UTC)" (scheduled at 2026-03-21 12:33:48.575358+00:00)
langchain-agent  | 2026-03-21 12:33:49,072 [INFO] oversight-agent: [e3c4f0ad-dad3-4e5d-bd61-141208d9f819] Engagement monitor cycle starting
langchain-agent  | 2026-03-21 12:33:49,208 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:49,212 [INFO] oversight-agent: [e3c4f0ad-dad3-4e5d-bd61-141208d9f819] Found 1 active account(s)
langchain-agent  | 2026-03-21 12:33:49,345 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-20T12%3A33%3A49.212276%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:49,347 [INFO] oversight-agent: [e3c4f0ad-dad3-4e5d-bd61-141208d9f819] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-21 12:33:49,487 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:50,432 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18119332864451803&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-21 12:33:50,569 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?on_conflict=instagram_comment_id&columns=%22created_at%22%2C%22text%22%2C%22author_username%22%2C%22media_id%22%2C%22business_account_id%22%2C%22instagram_comment_id%22%2C%22author_instagram_id%22%2C%22like_count%22 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:51,041 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18114826447521018&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-21 12:33:51,258 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:51,520 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=17991698096696570&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-21 12:33:51,660 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-20T12%3A33%3A51.524197%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:33:51,799 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-21 12:33:51,802 [INFO] oversight-agent: [e3c4f0ad-dad3-4e5d-bd61-141208d9f819] Engagement monitor cycle complete (2.6s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-21 12:33:51,803 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:38:48 UTC)" executed successfully
langchain-agent  | 2026-03-21 12:34:04,088 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:04,241 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:04,402 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:04,551 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:04,694 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:04,843 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:33126 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:34:21,742 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:35,241 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:35,403 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:35,557 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:35,701 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:35,855 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:34:36,007 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:39002 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:34:51,968 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:06,287 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:06,435 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:06,580 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:06,734 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:06,882 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:07,046 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:34080 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:35:22,150 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:37,317 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:37,468 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:37,604 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:37,742 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:37,878 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:35:38,012 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:60408 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:35:52,343 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,277 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,417 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,552 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,681 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,812 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:08,949 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:49572 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:36:22,521 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,234 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,404 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,550 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,692 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,840 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:36:39,986 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:43896 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:36:52,689 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:10,301 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:10,458 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:10,607 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:10,749 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:10,897 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:11,063 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:60134 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:37:22,880 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:41,350 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:41,506 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:41,661 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:41,808 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:41,960 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:37:42,102 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:58856 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:37:53,096 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:12,398 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:12,554 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:12,695 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:12,866 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:13,027 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:13,180 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:46808 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:38:23,269 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:43,461 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:43,608 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:43,757 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:43,893 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:44,027 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:44,164 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:57226 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-21 12:38:48,575 [INFO] apscheduler.executors.default: Running job "DM Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:43:48 UTC)" (scheduled at 2026-03-21 12:38:48.574677+00:00)
langchain-agent  | 2026-03-21 12:38:48,575 [INFO] oversight-agent: [4341b798-e022-4b27-95b7-0bda873d0708] DM monitor cycle starting
langchain-agent  | 2026-03-21 12:38:48,709 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:48,712 [INFO] oversight-agent: [4341b798-e022-4b27-95b7-0bda873d0708] Found 1 active account(s)
langchain-agent  | 2026-03-21 12:38:48,851 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id%2C%20instagram_message_id%2C%20message_text%2C%20sent_at%2C%20conversation_id%2C%20business_account_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&is_from_business=eq.False&processed_by_automation=eq.False&sent_at=gte.2026-03-20T12%3A38%3A48.712412%2B00%3A00&order=sent_at&limit=20 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:48,990 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-21 12:38:48,991 [INFO] oversight-agent: [4341b798-e022-4b27-95b7-0bda873d0708] DM monitor cycle complete (0.3s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-21 12:38:48,991 [INFO] apscheduler.executors.default: Job "DM Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:43:48 UTC)" executed successfully
langchain-agent  | 2026-03-21 12:38:48,992 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:43:48 UTC)" (scheduled at 2026-03-21 12:38:48.575358+00:00)
langchain-agent  | 2026-03-21 12:38:48,992 [INFO] oversight-agent: [28e9d098-06d6-49f1-8c98-da20b746289d] Engagement monitor cycle starting
langchain-agent  | 2026-03-21 12:38:49,134 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:49,135 [INFO] oversight-agent: [28e9d098-06d6-49f1-8c98-da20b746289d] Found 1 active account(s)
langchain-agent  | 2026-03-21 12:38:49,271 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-20T12%3A38%3A49.135448%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:49,273 [INFO] oversight-agent: [28e9d098-06d6-49f1-8c98-da20b746289d] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-21 12:38:49,407 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:49,566 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-20T12%3A38%3A49.410827%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-21 12:38:49,704 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-21 12:38:49,705 [INFO] oversight-agent: [28e9d098-06d6-49f1-8c98-da20b746289d] Engagement monitor cycle complete (0.6s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-21 12:38:49,705 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-21 12:43:48 UTC)" executed successfully
langchain-agent  | 2026-03-21 12:38:53,415 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
   

Console log error 
   supabase.ts:92 
 POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/oversight_chat_sessions?select=* 400 (Bad Request)
(anonymous)	@	supabase.ts:92
(anonymous)	@	auth-DMUYElC8.js:1
h	@	auth-DMUYElC8.js:1
le	@	supabase.ts:86
(anonymous)	@	fetch.js:23
(anonymous)	@	fetch.js:44
a	@	fetch.js:4
Promise.then		
c	@	fetch.js:6
(anonymous)	@	fetch.js:7
zs	@	fetch.js:3
(anonymous)	@	fetch.js:34
then	@	PostgrestBuilder.js:66
3
authStore.ts:744 🔄 Auth state changed: SIGNED_IN
﻿

Request conditions
Block and throttle individual network requests with the new Request conditions panel.

MCP server
Use auto connect to continue a debugging session in an already running Chrome instance.

Adopted stylesheets
Adopted stylesheets are now visible under shadow roots in the Elements panel.