"""
DM Service
==========
DM conversations, messages, and window status.
Used by: DM monitor, webhooks, LangChain tools.

All methods: @staticmethod
"""

from datetime import datetime, timezone, timedelta
from pybreaker import CircuitBreakerError

from ._infra import execute, db_breaker, supabase, logger


class DMService:
    """DM conversations and messages."""

    # ─────────────────────────────────────────
    # READ: DM History (two-table structure)
    # ─────────────────────────────────────────
    @staticmethod
    def get_dm_history(customer_instagram_id: str, business_account_id: str, limit: int = 5) -> list:
        """Fetch DM conversation history for a sender.

        Two-step: find conversation by customer_instagram_id + business_account_id,
        then fetch messages from that conversation.
        Maps to backward-compatible keys: direction (inbound/outbound), etc.

        Args:
            customer_instagram_id: Instagram numeric ID of the DM sender (matches DB column customer_instagram_id)
            business_account_id: UUID of the Instagram business account
            limit: Number of recent messages to fetch
        """
        if not supabase or not customer_instagram_id:
            return []

        try:
            conv_result = execute(
                supabase.table("instagram_dm_conversations")
                .select("id, conversation_status, within_window, window_expires_at")
                .eq("business_account_id", business_account_id)
                .eq("customer_instagram_id", customer_instagram_id)
                .limit(1),
                table="instagram_dm_conversations",
                operation="select",
            )

            if not conv_result.data:
                return []

            conversation = conv_result.data[0]
            conversation_id = conversation["id"]

            msg_result = execute(
                supabase.table("instagram_dm_messages")
                .select("message_text, message_type, is_from_business, sent_at, send_status")
                .eq("conversation_id", conversation_id)
                .order("sent_at", desc=True)
                .limit(limit),
                table="instagram_dm_messages",
                operation="select",
            )

            messages = []
            for m in (msg_result.data or []):
                messages.append({
                    "message_text": m.get("message_text", ""),
                    "direction": "outbound" if m.get("is_from_business") else "inbound",
                    "status": m.get("send_status", "unknown"),
                    "created_at": m.get("sent_at", ""),
                    "message_type": m.get("message_type", "text"),
                })
            return messages

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DM history fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch DM history for {customer_instagram_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # READ: DM Conversation Context
    # ─────────────────────────────────────────
    @staticmethod
    def get_dm_conversation_context(customer_instagram_id: str, business_account_id: str) -> dict:
        """Fetch conversation-level metadata: window status, message count.

        Args:
            customer_instagram_id: Instagram numeric ID of the DM sender (matches DB column customer_instagram_id)
            business_account_id: UUID of the Instagram business account
        """
        if not supabase or not customer_instagram_id:
            return {}

        try:
            result = execute(
                supabase.table("instagram_dm_conversations")
                .select("within_window, window_expires_at, conversation_status, message_count, last_message_at")
                .eq("business_account_id", business_account_id)
                .eq("customer_instagram_id", customer_instagram_id)
                .limit(1),
                table="instagram_dm_conversations",
                operation="select",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping DM conversation context fetch")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch DM conversation context for {customer_instagram_id}: {e}")
            return {}

    # ─────────────────────────────────────────
    # READ: Unprocessed Inbound DMs
    # ─────────────────────────────────────────
    @staticmethod
    def get_unprocessed_dms(
        business_account_id: str, limit: int = 20, hours_back: int = 24
    ) -> list:
        """Fetch inbound DMs not yet processed, enriched with conversation metadata.

        Filters: is_from_business=False, processed_by_automation=False,
        sent_at > now - hours_back. Returns oldest-first (FIFO).
        """
        if not supabase or not business_account_id:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

        try:
            msg_result = execute(
                supabase.table("instagram_dm_messages")
                .select(
                    "id, instagram_message_id, message_text, sent_at, "
                    "conversation_id, business_account_id"
                )
                .eq("business_account_id", business_account_id)
                .eq("is_from_business", False)
                .eq("processed_by_automation", False)
                .gte("sent_at", cutoff)
                .order("sent_at", desc=False)
                .limit(limit),
                table="instagram_dm_messages",
                operation="select",
            )
            messages = msg_result.data or []
            if not messages:
                return []

            conv_ids = list({m["conversation_id"] for m in messages if m.get("conversation_id")})
            conv_map = {}
            if conv_ids:
                conv_result = execute(
                    supabase.table("instagram_dm_conversations")
                    .select("id, customer_username, customer_instagram_id, instagram_thread_id")
                    .in_("id", conv_ids),
                    table="instagram_dm_conversations",
                    operation="select",
                )
                conv_map = {c["id"]: c for c in (conv_result.data or [])}

            for msg in messages:
                conv = conv_map.get(msg.get("conversation_id"), {})
                msg["customer_username"] = conv.get("customer_username", "")
                msg["customer_instagram_id"] = conv.get("customer_instagram_id", "")
                msg["instagram_thread_id"] = conv.get("instagram_thread_id", "")

            return messages

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — skipping unprocessed DMs fetch")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch unprocessed DMs for {business_account_id}: {e}")
            return []

    # ─────────────────────────────────────────
    # WRITE: Mark DM Processed
    # ─────────────────────────────────────────
    @staticmethod
    def mark_dm_processed(
        message_id: str, response_text: str = None, was_replied: bool = False
    ) -> bool:
        """Update instagram_dm_messages to mark as processed by automation."""
        if not supabase or not message_id:
            return False

        update_data = {"processed_by_automation": True}
        if was_replied and response_text:
            update_data["automated_response_sent"] = True
            update_data["response_text"] = response_text
            update_data["response_sent_at"] = datetime.now(timezone.utc).isoformat()

        try:
            execute(
                supabase.table("instagram_dm_messages")
                .update(update_data)
                .eq("id", message_id),
                table="instagram_dm_messages",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to mark DM processed")
            return False
        except Exception as e:
            logger.error(f"Failed to mark DM {message_id} as processed: {e}")
            return False

    # ─────────────────────────────────────────
    # WRITE: Save Live Conversation Messages
    # ─────────────────────────────────────────
    @staticmethod
    def save_live_conversation_messages(
        messages: list,
        conversation_id: str,
        business_account_id: str,
        business_ig_user_id: str,
    ) -> int:
        """Upsert DM messages from /conversation-messages backend proxy.

        is_from_business derived by comparing from.id to business_ig_user_id.
        Returns count upserted.
        """
        if not supabase or not messages:
            return 0

        records = [
            {
                "instagram_message_id": m["id"],
                "message_text": m.get("message", ""),
                "conversation_id": conversation_id,
                "business_account_id": business_account_id,
                "is_from_business": m.get("from", {}).get("id") == business_ig_user_id,
                "recipient_instagram_id": m.get("from", {}).get("id") or "",
                "sent_at": m.get("created_time"),
                "send_status": "delivered",
            }
            for m in messages if m.get("id")
        ]
        if not records:
            return 0

        try:
            result = execute(
                supabase.table("instagram_dm_messages")
                .upsert(records, on_conflict="instagram_message_id"),
                table="instagram_dm_messages",
                operation="upsert",
            )
            return len(result.data or [])

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to save live conversation messages")
            return 0
        except Exception as e:
            logger.error(f"Failed to save live conversation messages: {e}")
            return 0
