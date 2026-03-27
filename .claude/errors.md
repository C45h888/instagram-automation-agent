  Trap 1: sender_id vs customer_instagram_id — Parameter Name Drift
The Root Cause
The parameter is called sender_id everywhere in the DM tool layer and call sites. But the Supabase database column it maps to is called customer_instagram_id. The word sender_id never appears in the schema.

What Makes This Dangerous
The LLM sees sender_id in the @tool description. The LLM has no concept of Supabase column names — but the internal developers see sender_id in the code and may refactor it without understanding it maps to customer_instagram_id. When a developer sees sender_id in the code, there's no indication it's anything other than what it says. If someone rewrites get_dm_history and calls the parameter ig_user_id, the @tool description needs updating. If they update the description without updating the DB query, the tool silently breaks.

The Call Graph

Meta sends: { "sender": { "id": "1234567890" } }
                    ↓
webhook_dm.py parses → parsed.sender_id = "1234567890"
                    ↓
DMService.get_dm_history(sender_id="1234567890", ...)
                    ↓
supabase.table("instagram_dm_conversations")
    .eq("customer_instagram_id", sender_id)   ← parameter name diverges from column name here
                    ↓
Supabase returns conversation UUID
All Files That Need Changing for Trap 1
File	Line	Change
_dms.py	23	Parameter name sender_id → customer_instagram_id
_dms.py	82	Parameter name sender_id → customer_instagram_id
_dms.py	38	DB query .eq("customer_instagram_id", sender_id) → same variable name after rename
_dms.py	92	Same as above
_dm_tools.py	17, 25	Parameter rename + @tool description stays consistent
_dm_tools.py	31, 38	Same
webhook_dm.py	114, 115, 142, 143	All call sites already use parsed.sender_id — rename the Pydantic model field
dm_monitor.py	211, 215	Local variable customer_ig_id is already correct name — just needs @tool update
prompts.py	85-86, 96	Prompts reference sender_id in few-shot examples
supabase_tools.py	—	Already uses _dm_tools — no change needed
The Fix Strategy
Step 1: Rename the parameter in DMService.get_dm_history and DMService.get_dm_conversation_context from sender_id to customer_instagram_id. Update the DB query comment to say customer_instagram_id is the column. Keep the DB column name unchanged in the query.

Step 2: Update _dm_tools.py parameter name to match. The @tool description already says "Instagram numeric ID" — no description change needed, just the Python parameter name.

Step 3: Update webhook_dm.py Pydantic model field name from sender_id to customer_instagram_id. Check if this field is referenced in any API contracts or external webhooks — if the webhook payload from Meta uses sender.id, the Pydantic field should match what Meta sends, which means sender_id might be the right name at the webhook boundary. If the Pydantic model field needs to match Meta's payload, keep sender_id there and rename only inside the service call site.

Step 4: Update prompts in prompts.py that reference sender_id.

Trap 2: Two ID Spaces Everywhere — No Type Tagging
The Root Cause
Every function in the system works with one of two completely different ID types:


ID Space A — Meta/Instagram IDs (strings, from webhooks and IG API)
    post_id: "17841475450533073_1234567890"     ← Instagram media ID
    sender_id: "12345678901234567"              ← Instagram user ID
    ig_page_id: "17841475450533073"            ← Instagram Business Account ID

ID Space B — Supabase UUIDs (strings, internal FKs)
    media_uuid: "a3f8c9d2-b4e1-..."
    account_uuid: "f47ac10b-58cc-4372-..."
    conversation_uuid: "e9d1a2b3-c4f5-..."
What Makes This Dangerous
A developer who adds a new call to get_post_context(media_uuid="17841475450533073_1234567890") — passing a Meta ID where a Supabase UUID is expected — will silently get result.data back as None, and the system will return {}. The LLM proceeds without context. The failure is completely silent. There is no type at runtime.

Every Function With Dual-ID Exposure

get_post_context(post_id: str)
    ↑ Meta IG media ID (Instagram IDs)
    
get_post_context_by_uuid(media_uuid: str)
    ↑ Supabase UUID
    
get_account_uuid_by_instagram_id(instagram_business_id: str)
    ↑ Meta IG user ID → returns Supabase UUID

get_account_info(business_account_id: str)
    ↑ Supabase UUID
    
get_dm_history(customer_instagram_id: str, ...)
    ↑ Meta user ID

get_dm_conversation_context(customer_instagram_id: str, ...)
    ↑ Meta user ID
The Fix Strategy
Create a typed ID wrapper that makes invalid ID spaces a runtime assertion:


# services/ids.py
class InstagramId(str):
    """A Meta/Instagram numeric string ID (from webhooks, IG API).
    Distinguishes Meta's ID space from Supabase UUID space.
    """
    pass

class SupabaseUUID(str):
    """A Supabase UUID. Used for all internal FK relationships.
    Never sent to Meta's API or received from Meta's webhooks.
    """
    pass
Then update function signatures to use them:


def get_post_context(post_id: InstagramId) -> dict: ...

def get_post_context_by_uuid(media_uuid: SupabaseUUID) -> dict: ...
Any caller passing the wrong type raises TypeError at call time.

Trap 3: No Return Type Enforcement @tool → LLM
The Root Cause
@tool captures the function's return annotation for LangChain's schema generation. But LangChain only uses it to tell the LLM what the tool promises to return. Nothing enforces that the actual Supabase query actually returns that type.


@tool("Fetch post details...")
def get_post_context(post_id: str) -> dict:   # annotation says dict
    data = supabase.table("...").execute()
    return result.data[0]   # could be None if not found
What Makes This Dangerous
If Supabase returns an empty result set and result.data is [], then result.data[0] raises IndexError. If it returns None, the @tool description says dict, LangChain tells the LLM "you'll get a dict", the LLM tries to access data["caption"] and fails silently. If the function returns None, LangChain has no schema for None — the LLM gets an unexpected payload and doesn't know what to do.

The Fix Strategy
Use a @enforce_return decorator that asserts the return matches the annotation:


from functools import wraps

def enforce_return(return_type):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if result is None:
                raise ValueError(f"{func.__name__} returned None — expected {return_type}")
            if not isinstance(result, return_type):
                raise TypeError(f"{func.__name__} returned {type(result).__name__} — expected {return_type}")
            return result
        return wrapper
    return decorator
Then on every @tool-decorated function, wrap the return type validation in a single line.

What to Change in Priority Order

1. Trap 1 (sender_id)     — rename the parameter, update prompts, update Pydantic model
                            Low risk, high clarity. All callers are internal.

2. Trap 2 (typed IDs)     — create ids.py, annotate function signatures
                            Medium risk (all call sites must be checked). 
                            Start with just the two most dangerous: 
                            get_post_context and get_post_context_by_uuid.

3. Trap 3 (return types)  — decorator pattern is cleanest approach
                            Add enforce_return decorator to _infra.py, apply to all @tool functions.