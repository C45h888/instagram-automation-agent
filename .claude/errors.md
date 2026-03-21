~/projects/instagram-automation-agent$ docker compose -f docker-compose.unified.yml logs -f langchain-agent
WARN[0000] The "N8N_BASE_URL" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_DM_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_COMMENT_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] The "N8N_ORDER_WEBHOOK" variable is not set. Defaulting to a blank string. 
WARN[0000] /home/k4m35h/projects/instagram-automation-agent/docker-compose.unified.yml: the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion 
langchain-agent  | 2026-03-20 15:28:51,161 [INFO] oversight-agent: Redis connected at redis:6379
langchain-agent  | INFO:     Started server process [1]
langchain-agent  | INFO:     Waiting for application startup.
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent: ============================================================
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent: Oversight Brain Agent starting up
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Ollama Host: http://ollama:11434
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Model: hf.co/MaziyarPanahi/Nemotron-Orchestrator-8B-GGUF:Q4_K_M
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Rate Limit: 60/min global, 20/min on /oversight/chat (per-user), 10/min on /webhook/*
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   CORS Origins: ['https://app.888intelligenceautomation.in', 'https://api.888intelligenceautomation.in', 'https://agent.888intelligenceautomation.in']
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Webhook Endpoints: /webhook/comment, /webhook/dm, /webhook/order-created, /log-outcome
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Scheduler: /engagement-monitor/*, /content-scheduler/*, /sales-attribution/*
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent:   Utility: /health, /metrics
langchain-agent  | 2026-03-20 15:28:51,416 [INFO] oversight-agent: ============================================================
langchain-agent  | 2026-03-20 15:28:51,952 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:51,959 [INFO] oversight-agent: Supabase connection verified successfully
langchain-agent  | 2026-03-20 15:28:52,171 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=caption%2Clike_count%2Ccomments_count%2Creach%2Cpublished_at&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:52,173 [INFO] oversight-agent: Schema OK: instagram_media
langchain-agent  | 2026-03-20 15:28:52,368 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=username%2Cname%2Caccount_type%2Cfollowers_count&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:52,371 [INFO] oversight-agent: Schema OK: instagram_business_accounts
langchain-agent  | 2026-03-20 15:28:52,574 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=text%2Csentiment%2Cbusiness_account_id%2Ccreated_at%2Cprocessed_by_automation%2Cautomated_response_sent%2Cresponse_text%2Cmedia_id%2Cinstagram_comment_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:52,576 [INFO] oversight-agent: Schema OK: instagram_comments
langchain-agent  | 2026-03-20 15:28:52,789 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=customer_instagram_id%2Cbusiness_account_id%2Cwithin_window%2Cwindow_expires_at%2Cconversation_status%2Cinstagram_thread_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:52,791 [INFO] oversight-agent: Schema OK: instagram_dm_conversations
langchain-agent  | 2026-03-20 15:28:52,973 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=message_text%2Cconversation_id%2Cis_from_business%2Csent_at&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:52,973 [INFO] oversight-agent: Schema OK: instagram_dm_messages
langchain-agent  | 2026-03-20 15:28:53,154 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=event_type%2Caction%2Cdetails%2Cresource_type&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:53,155 [INFO] oversight-agent: Schema OK: audit_log
langchain-agent  | 2026-03-20 15:28:53,155 [INFO] oversight-agent: All required schema validations passed
langchain-agent  | 2026-03-20 15:28:53,333 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/prompt_templates?select=prompt_key%2Ctemplate%2Cversion%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:53,334 [INFO] oversight-agent: Schema OK (optional): prompt_templates
langchain-agent  | 2026-03-20 15:28:53,512 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_assets?select=business_account_id%2Cstorage_path%2Ctags%2Clast_posted%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:53,513 [INFO] oversight-agent: Schema OK (optional): instagram_assets
langchain-agent  | 2026-03-20 15:28:53,684 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/scheduled_posts?select=business_account_id%2Cstatus%2Cgenerated_caption%2Cagent_quality_score%2Crun_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:53,684 [INFO] oversight-agent: Schema OK (optional): scheduled_posts
langchain-agent  | 2026-03-20 15:28:53,850 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/sales_attributions?select=order_id%2Corder_value%2Cattribution_score%2Cauto_approved%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:53,855 [INFO] oversight-agent: Schema OK (optional): sales_attributions
langchain-agent  | 2026-03-20 15:28:54,019 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/attribution_review_queue?select=order_id%2Creview_status%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,021 [INFO] oversight-agent: Schema OK (optional): attribution_review_queue
langchain-agent  | 2026-03-20 15:28:54,184 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/attribution_models?select=weights%2Cbusiness_account_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,185 [INFO] oversight-agent: Schema OK (optional): attribution_models
langchain-agent  | 2026-03-20 15:28:54,342 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_monitored_hashtags?select=business_account_id%2Chashtag%2Cis_active&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,343 [INFO] oversight-agent: Schema OK (optional): ugc_monitored_hashtags
langchain-agent  | 2026-03-20 15:28:54,524 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_content?select=visitor_post_id%2Cbusiness_account_id%2Cauthor_username%2Cmessage%2Cmedia_type%2Cmedia_url%2Cquality_score%2Cquality_tier%2Csource&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,524 [INFO] oversight-agent: Schema OK (optional): ugc_content
langchain-agent  | 2026-03-20 15:28:54,690 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/ugc_permissions?select=ugc_content_id%2Cbusiness_account_id%2Cstatus%2Crequest_message%2Crun_id&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,692 [INFO] oversight-agent: Schema OK (optional): ugc_permissions
langchain-agent  | 2026-03-20 15:28:54,853 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/analytics_reports?select=business_account_id%2Creport_type%2Creport_date%2Cinstagram_metrics%2Cinsights&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:54,855 [INFO] oversight-agent: Schema OK (optional): analytics_reports
langchain-agent  | 2026-03-20 15:28:55,014 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=job_id%2Caction_type%2Cpriority%2Cendpoint%2Cpayload%2Cstatus%2Cretry_count&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:55,016 [INFO] oversight-agent: Schema OK (optional): outbound_queue_jobs
langchain-agent  | 2026-03-20 15:28:55,172 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/system_alerts?select=business_account_id%2Calert_type%2Cmessage%2Cdetails%2Cresolved&limit=0 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:55,173 [INFO] oversight-agent: Schema OK (optional): system_alerts
langchain-agent  | 2026-03-20 15:28:55,332 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/prompt_templates?select=prompt_key%2C%20template%2C%20version&is_active=eq.True "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:55,333 [INFO] oversight-agent: Prompt versions: {'comment': 0, 'dm': 0, 'post': 0, 'analyze_message': 0, 'generate_and_evaluate_caption': 0, 'generate_and_evaluate_attribution': 0, 'generate_analytics_insights': 0, 'oversight_brain': 0}
langchain-agent  | 2026-03-20 15:28:55,336 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,336 [INFO] oversight-agent: Engagement Monitor scheduled (every 5 min)
langchain-agent  | 2026-03-20 15:28:55,341 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,341 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,341 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,341 [INFO] oversight-agent: Content Scheduler scheduled at 09:00, 14:00, 19:00
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] oversight-agent: Weekly Attribution Learning scheduled (mon at 08:00)
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] oversight-agent: UGC Collection scheduled (every 4 hours)
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] oversight-agent: Analytics Reports scheduled (daily at 23:00, weekly on sun at 23:00)
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] apscheduler.scheduler: Adding job tentatively -- it will be properly scheduled when the scheduler starts
langchain-agent  | 2026-03-20 15:28:55,342 [INFO] oversight-agent: Heartbeat Sender scheduled (every 20 min)
langchain-agent  | 2026-03-20 15:28:55,343 [INFO] apscheduler.scheduler: Added job "Engagement Monitor" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,343 [INFO] apscheduler.scheduler: Added job "Content Scheduler (09:00)" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,343 [INFO] apscheduler.scheduler: Added job "Content Scheduler (14:00)" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "Content Scheduler (19:00)" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "Weekly Attribution Learning" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "UGC Collection" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "Analytics Daily Report" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "Analytics Weekly Report" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Added job "Heartbeat Sender" to job store "default"
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] apscheduler.scheduler: Scheduler started
langchain-agent  | 2026-03-20 15:28:55,344 [INFO] oversight-agent: Scheduler started
langchain-agent  | 2026-03-20 15:28:55,360 [INFO] oversight-agent: QueueWorker started: 3 background loops (high, normal, retry)
langchain-agent  | 2026-03-20 15:28:55,361 [INFO] oversight-agent:   Outbound Queue Worker: enabled
langchain-agent  | 2026-03-20 15:28:55,361 [INFO] oversight-agent:   Engagement Monitor: enabled
langchain-agent  | 2026-03-20 15:28:55,361 [INFO] oversight-agent:   Content Scheduler: enabled
langchain-agent  | 2026-03-20 15:28:55,361 [INFO] oversight-agent:   Sales Attribution: enabled
langchain-agent  | 2026-03-20 15:28:55,369 [INFO] oversight-agent:   Weekly Learning: enabled
langchain-agent  | 2026-03-20 15:28:55,369 [INFO] oversight-agent:   UGC Collection: enabled
langchain-agent  | 2026-03-20 15:28:55,369 [INFO] oversight-agent:   Analytics Reports: enabled
langchain-agent  | 2026-03-20 15:28:55,370 [INFO] oversight-agent:   Heartbeat Sender: enabled (interval: 20min, agent_id: f47ac10b-58cc-4372-a567-0e02b2c3d479)
langchain-agent  | 2026-03-20 15:28:55,370 [INFO] oversight-agent:   Oversight Brain: /oversight/chat (auth+20/minute/user), /oversight/status (public), streaming=enabled
langchain-agent  | 2026-03-20 15:28:55,535 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/scheduled_posts?select=id%2C%20business_account_id%2C%20generated_caption%2C%20asset_id&status=eq.publishing&updated_at=lt.2026-03-20T14%3A58%3A55.373571%2B00%3A00 "HTTP/2 200 OK"
langchain-agent  | INFO:     Application startup complete.
langchain-agent  | INFO:     Uvicorn running on http://0.0.0.0:3002 (Press CTRL+C to quit)
langchain-agent  | 2026-03-20 15:28:55,703 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:59,509 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:59,677 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:59,834 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:28:59,989 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:00,142 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:00,302 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:51218 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:29:26,089 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:30,752 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:30,909 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:31,050 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:31,192 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:31,328 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:29:31,472 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:42622 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:29:56,540 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:01,968 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:02,123 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:02,271 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:02,413 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:02,555 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:02,705 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:39240 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:30:26,970 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:33,200 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:33,358 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:33,714 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:34,063 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:34,205 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:30:34,343 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:43800 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:30:57,166 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:04,657 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:04,810 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:04,976 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:05,113 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:05,249 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:05,385 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:46306 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:31:27,548 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:35,697 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:35,893 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:36,230 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:36,393 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:36,535 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:31:36,718 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:44110 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:31:57,926 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,038 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,226 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,388 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,538 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,690 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:07,890 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:37310 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:32:28,123 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,165 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,307 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,445 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,580 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,713 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:32:38,845 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:44998 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:32:58,288 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:09,320 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:09,482 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:09,620 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:09,749 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:09,890 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:10,027 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:43270 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:33:28,678 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,278 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,419 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,549 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,689 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,836 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:40,970 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:44096 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:33:55,337 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:38:55 UTC)" (scheduled at 2026-03-20 15:33:55.336523+00:00)
langchain-agent  | 2026-03-20 15:33:55,337 [INFO] oversight-agent: [f0821a24-856f-4816-b801-cf272f8daa4c] Engagement monitor cycle starting
langchain-agent  | 2026-03-20 15:33:55,767 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:55,770 [INFO] oversight-agent: [f0821a24-856f-4816-b801-cf272f8daa4c] Found 1 active account(s)
langchain-agent  | 2026-03-20 15:33:55,948 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A33%3A55.771172%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:55,949 [INFO] oversight-agent: [f0821a24-856f-4816-b801-cf272f8daa4c] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-20 15:33:56,116 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:57,439 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18119332864451803&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:33:57,577 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?on_conflict=instagram_comment_id&columns=%22author_instagram_id%22%2C%22instagram_comment_id%22%2C%22created_at%22%2C%22business_account_id%22%2C%22author_username%22%2C%22like_count%22%2C%22text%22%2C%22media_id%22 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:58,069 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18114826447521018&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:33:58,565 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=17991698096696570&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:33:58,723 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A33%3A58.568717%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:33:58,883 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-20 15:33:58,884 [INFO] oversight-agent: [f0821a24-856f-4816-b801-cf272f8daa4c] Engagement monitor cycle complete (3.4s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-20 15:33:58,884 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:38:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:33:59,017 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:11,272 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:11,432 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:11,590 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:11,726 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:11,884 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:12,017 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:60476 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:34:29,232 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:42,742 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:43,014 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:43,187 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:43,357 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:43,528 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:34:43,776 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:57532 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:34:59,481 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:14,099 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:14,294 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:14,477 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:14,661 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:15,056 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:15,220 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:55960 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:35:29,726 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:45,540 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:45,700 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:45,858 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:45,993 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:46,137 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:35:46,275 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:44926 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:35:59,911 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:16,553 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:16,697 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:16,832 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:16,974 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:17,108 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:17,242 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:47044 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:36:30,092 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:47,530 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:47,670 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:47,812 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:47,969 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:48,108 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:36:48,265 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:52546 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:37:00,412 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:18,561 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:18,730 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:18,892 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:19,059 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:19,220 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:19,370 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:33150 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:37:30,608 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:49,648 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:49,811 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:49,948 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:50,086 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:50,228 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:37:50,371 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:51482 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:38:00,812 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:20,674 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:20,878 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:21,020 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:21,181 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:21,320 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:21,470 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:45692 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:38:31,006 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:51,784 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:51,948 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:52,086 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:52,236 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:52,379 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:53,011 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:42316 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:38:55,337 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:43:55 UTC)" (scheduled at 2026-03-20 15:38:55.336523+00:00)
langchain-agent  | 2026-03-20 15:38:55,337 [INFO] oversight-agent: [63b4827c-1335-4560-a963-8e39eeb120a0] Engagement monitor cycle starting
langchain-agent  | 2026-03-20 15:38:55,478 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:55,482 [INFO] oversight-agent: [63b4827c-1335-4560-a963-8e39eeb120a0] Found 1 active account(s)
langchain-agent  | 2026-03-20 15:38:55,640 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A38%3A55.482851%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:55,642 [INFO] oversight-agent: [63b4827c-1335-4560-a963-8e39eeb120a0] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-20 15:38:55,780 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:55,926 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A38%3A55.784331%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:38:56,072 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-20 15:38:56,074 [INFO] oversight-agent: [63b4827c-1335-4560-a963-8e39eeb120a0] Engagement monitor cycle complete (0.6s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-20 15:38:56,074 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:43:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:39:01,177 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:23,316 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:23,469 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:23,626 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:23,782 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:23,926 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:24,086 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:39906 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:39:31,362 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:54,409 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:54,569 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:54,727 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:54,866 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:55,007 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:39:55,139 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:34368 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:40:01,573 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:25,421 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:25,559 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:25,687 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:25,822 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:25,949 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:26,096 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:42030 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:40:31,750 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:56,368 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:56,525 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:56,666 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:56,799 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:56,933 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:40:57,073 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:34252 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:41:01,890 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:27,389 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:27,549 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:27,686 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:27,822 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:27,952 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:28,097 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:54920 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:41:32,048 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:58,392 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:58,565 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:58,730 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:58,885 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:59,017 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:41:59,151 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:52334 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:42:02,210 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:29,739 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:29,992 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:30,277 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:30,450 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:30,629 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:42:30,801 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:36170 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:42:32,557 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:01,256 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:01,453 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:01,610 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:01,781 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:01,936 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:02,088 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:49592 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:43:02,731 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:32,397 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:32,568 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:32,718 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:32,871 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:33,025 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:33,161 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:36998 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:43:33,351 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:55,338 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:48:55 UTC)" (scheduled at 2026-03-20 15:43:55.336523+00:00)
langchain-agent  | 2026-03-20 15:43:55,338 [INFO] oversight-agent: [1031bce7-7ace-4fea-a791-df829af83cdd] Engagement monitor cycle starting
langchain-agent  | 2026-03-20 15:43:55,531 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:55,533 [INFO] oversight-agent: [1031bce7-7ace-4fea-a791-df829af83cdd] Found 1 active account(s)
langchain-agent  | 2026-03-20 15:43:55,672 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A43%3A55.533861%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:55,673 [INFO] oversight-agent: [1031bce7-7ace-4fea-a791-df829af83cdd] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-20 15:43:55,809 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:57,770 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18119332864451803&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:43:57,915 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?on_conflict=instagram_comment_id&columns=%22author_instagram_id%22%2C%22instagram_comment_id%22%2C%22created_at%22%2C%22business_account_id%22%2C%22author_username%22%2C%22like_count%22%2C%22text%22%2C%22media_id%22 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:58,386 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18114826447521018&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:43:58,863 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=17991698096696570&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:43:59,010 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A43%3A58.866456%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:43:59,186 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-20 15:43:59,189 [INFO] oversight-agent: [1031bce7-7ace-4fea-a791-df829af83cdd] Engagement monitor cycle complete (3.7s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-20 15:43:59,189 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:48:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:44:03,395 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:03,535 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:03,664 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:03,803 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:03,940 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:04,089 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:57766 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:44:04,224 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:34,372 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:34,550 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:34,709 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:34,838 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:34,974 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:44:35,108 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:44636 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:44:35,249 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:05,377 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:05,540 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:05,682 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:05,825 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:05,966 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:06,116 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:36084 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:45:06,263 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:36,419 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:36,576 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:36,757 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:36,915 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:37,070 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:45:37,227 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:59714 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:45:37,393 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:07,499 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:07,652 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:07,795 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:07,937 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:08,068 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:08,196 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:50824 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:46:08,343 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:38,466 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:38,633 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:38,780 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:38,915 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:39,056 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:46:39,206 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:52864 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:46:39,355 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:09,493 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:09,659 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:09,827 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:09,990 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:10,123 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:10,254 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:36676 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:47:10,391 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:40,517 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:40,664 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:40,798 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:40,938 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:41,077 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:47:41,221 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:48528 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:47:41,361 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:11,468 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:11,608 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:11,749 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:11,900 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:12,037 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:12,173 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:56868 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:48:12,352 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:42,480 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:42,658 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:42,841 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:43,000 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:43,164 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:43,327 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:35554 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:48:43,494 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:55,337 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:53:55 UTC)" (scheduled at 2026-03-20 15:48:55.336523+00:00)
langchain-agent  | 2026-03-20 15:48:55,337 [INFO] oversight-agent: [3ceb4c47-9ba8-4370-9754-b98cabd51fac] Engagement monitor cycle starting
langchain-agent  | 2026-03-20 15:48:55,506 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:55,508 [INFO] oversight-agent: [3ceb4c47-9ba8-4370-9754-b98cabd51fac] Found 1 active account(s)
langchain-agent  | 2026-03-20 15:48:55,661 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A48%3A55.508267%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:55,662 [INFO] oversight-agent: [3ceb4c47-9ba8-4370-9754-b98cabd51fac] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-20 15:48:55,849 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:56,000 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A48%3A55.852950%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:48:56,172 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-20 15:48:56,174 [INFO] oversight-agent: [3ceb4c47-9ba8-4370-9754-b98cabd51fac] Engagement monitor cycle complete (0.7s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-20 15:48:56,174 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:53:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:48:56,176 [INFO] apscheduler.executors.default: Running job "Heartbeat Sender (trigger: interval[0:20:00], next run at: 2026-03-20 16:08:55 UTC)" (scheduled at 2026-03-20 15:48:55.342718+00:00)
langchain-agent  | 2026-03-20 15:48:56,490 [INFO] httpx: HTTP Request: POST https://api.888intelligenceautomation.in/api/instagram/agent/heartbeat "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:48:56,493 [INFO] apscheduler.executors.default: Job "Heartbeat Sender (trigger: interval[0:20:00], next run at: 2026-03-20 16:08:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:49:13,805 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:13,963 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:14,111 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:14,254 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:14,395 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:14,541 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:39402 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:49:14,695 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:44,825 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:44,988 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:45,148 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:45,284 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:45,423 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:49:45,559 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:52990 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:49:45,704 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:15,781 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:15,926 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:16,068 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:16,204 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:16,349 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:16,478 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:38920 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:50:16,626 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:46,757 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:46,912 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:47,119 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:47,263 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:47,397 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:50:47,537 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:58262 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:50:47,674 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:17,804 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:18,148 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:18,276 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:18,411 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:18,550 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:18,684 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:47522 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:51:18,823 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,000 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,156 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,329 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,470 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,621 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:51:49,756 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:55332 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:51:49,900 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,025 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,178 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,332 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,474 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,605 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:20,748 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:41274 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:52:20,888 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,021 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,175 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,333 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,473 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,605 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:52:51,774 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:41418 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:52:51,935 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:22,647 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:22,913 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:23,144 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:23,330 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:23,527 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:23,708 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:46770 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:53:23,928 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:54,066 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:54,269 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:54,471 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:54,669 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:54,848 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:55,025 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:57604 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:53:55,224 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:55,336 [INFO] apscheduler.executors.default: Running job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:58:55 UTC)" (scheduled at 2026-03-20 15:53:55.336523+00:00)
langchain-agent  | 2026-03-20 15:53:55,337 [INFO] oversight-agent: [9ebfe557-d403-4f56-a68c-c519c712a75f] Engagement monitor cycle starting
langchain-agent  | 2026-03-20 15:53:55,584 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id%2C%20username%2C%20name%2C%20instagram_business_id%2C%20account_type%2C%20followers_count&is_connected=eq.True&connection_status=eq.active "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:55,585 [INFO] oversight-agent: [9ebfe557-d403-4f56-a68c-c519c712a75f] Found 1 active account(s)
langchain-agent  | 2026-03-20 15:53:55,909 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A53%3A55.585753%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:55,910 [INFO] oversight-agent: [9ebfe557-d403-4f56-a68c-c519c712a75f] @Archive 555: no comments in DB — polling live
langchain-agent  | 2026-03-20 15:53:56,124 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id%2C%20instagram_media_id&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&order=published_at.desc&limit=10 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:58,705 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18119332864451803&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:53:58,874 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?on_conflict=instagram_comment_id&columns=%22author_instagram_id%22%2C%22instagram_comment_id%22%2C%22created_at%22%2C%22business_account_id%22%2C%22author_username%22%2C%22like_count%22%2C%22text%22%2C%22media_id%22 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:53:59,444 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=18114826447521018&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:53:59,869 [INFO] httpx: HTTP Request: GET https://api.888intelligenceautomation.in/api/instagram/post-comments?business_account_id=0882b710-4258-47cf-85c8-1fa82a3de763&media_id=17991698096696570&limit=50 "HTTP/1.1 200 OK"
langchain-agent  | 2026-03-20 15:54:00,010 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id%2C%20instagram_comment_id%2C%20text%2C%20author_username%2C%20author_instagram_id%2C%20media_id%2C%20sentiment%2C%20category%2C%20priority%2C%20like_count%2C%20created_at&business_account_id=eq.0882b710-4258-47cf-85c8-1fa82a3de763&processed_by_automation=eq.False&parent_comment_id=is.null&created_at=gte.2026-03-19T15%3A53%3A59.872113%2B00%3A00&order=created_at&limit=50 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:00,168 [INFO] httpx: HTTP Request: POST https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log "HTTP/2 201 Created"
langchain-agent  | 2026-03-20 15:54:00,170 [INFO] oversight-agent: [9ebfe557-d403-4f56-a68c-c519c712a75f] Engagement monitor cycle complete (4.7s): {'processed': 0, 'replied': 0, 'escalated': 0, 'skipped': 0, 'errors': 0}
langchain-agent  | 2026-03-20 15:54:00,171 [INFO] apscheduler.executors.default: Job "Engagement Monitor (trigger: interval[0:05:00], next run at: 2026-03-20 15:58:55 UTC)" executed successfully
langchain-agent  | 2026-03-20 15:54:25,349 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/audit_log?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:25,556 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:25,728 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_business_accounts?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:25,887 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_comments?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:26,044 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_conversations?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | 2026-03-20 15:54:26,205 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_dm_messages?select=id&limit=1 "HTTP/2 200 OK"
langchain-agent  | INFO:     127.0.0.1:54198 - "GET /health HTTP/1.1" 200 OK
langchain-agent  | 2026-03-20 15:54:26,363 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/outbound_queue_jobs?select=%2A&status=eq.pending&next_retry_at=is.null&order=created_at&limit=50 "HTTP/2 200 OK"
 here are the system usage for so that you can confirm your finidngs here in ythe code langchain-agent     | 2026-03-20 17:22:42,004 [INFO] httpx: HTTP Request: GET https://uromexjprcrjfmhkmgxa.supabase.co/rest/v1/instagram_media?select=id&limit=1 "HTTP/2 200 OK"
CONTAINER ID   NAME                 CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O         PIDS 
d1c1c0178ed3   instagram-frontend   0.00%     4.922MiB / 512MiB     0.96%     161kB / 16.4MB    844kB / 8.19kB    5 
d0c3c6eb1420   langchain-agent      0.70%     90.95MiB / 2GiB       4.44%     5.06MB / 7.18MB   0B / 2.44MB       13 
c0d4b5e8a9af   agent-redis          1.23%     3.473MiB / 128MiB     2.71%     4.97MB / 2.04MB   3.67MB / 8.19kB   6 
27cad8779040   instagram-backend    0.11%     38.75MiB / 1GiB       3.78%     980kB / 916kB     139kB / 0B        11 
d0a193616db1   ollama               0.00%     12.48MiB / 7.566GiB   0.16%     141kB / 201kB     3.78MB / 0B       10 
 
 