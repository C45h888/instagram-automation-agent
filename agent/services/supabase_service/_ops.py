"""
Ops Service
==========
Audit logging, system alerts, and account management.
Used by: all pipelines (audit_log), outbound queue (alerts, account ops).

All methods: @staticmethod
"""

from datetime import datetime, timezone
from pybreaker import CircuitBreakerError

from ._infra import execute, db_breaker, supabase, logger, is_valid_uuid


class OpsService:
    """Audit log, system alerts, and account management."""

    # ─────────────────────────────────────────
    # WRITE: Audit Log
    # ─────────────────────────────────────────
    @staticmethod
    def log_decision(
        event_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        user_id: str,
        details: dict,
        ip_address: str = "",
    ) -> bool:
        """Log agent decision to audit_log table.

        Validates resource_id and user_id as UUIDs — non-UUID originals
        are stored in details instead of failing the insert.
        No-op if Supabase is not connected.
        """
        if not supabase:
            logger.warning("Supabase not connected — skipping audit log")
            return False

        try:
            valid_resource_id = resource_id if is_valid_uuid(resource_id) else None
            enriched_details = dict(details)
            if resource_id and not valid_resource_id:
                enriched_details["original_resource_id"] = resource_id

            valid_user_id = user_id if is_valid_uuid(user_id) else None
            if user_id and not valid_user_id:
                enriched_details["original_user_id"] = user_id

            row = {
                "event_type": event_type,
                "action": action,
                "resource_type": resource_type,
                "resource_id": valid_resource_id,
                "details": enriched_details,
                "user_id": valid_user_id,
                "ip_address": ip_address or None,
                "success": True,
            }

            execute(
                supabase.table("audit_log").insert(row),
                table="audit_log",
                operation="insert",
            )
            return True

        except CircuitBreakerError:
            logger.error("Circuit breaker OPEN — failed to log decision to audit_log")
            return False
        except Exception as e:
            logger.error(f"Failed to log decision to audit_log: {e}")
            return False

    # ─────────────────────────────────────────
    # READ: Get Business Account
    # ─────────────────────────────────────────
    @staticmethod
    def get_business_account(business_account_id: str) -> dict:
        """Fetch a single business account by UUID.

        Returns: {id, username, is_connected, connection_status}
        Used by retry_dlq to check account connectivity before re-enqueuing.
        """
        if not supabase or not is_valid_uuid(business_account_id):
            return {}

        try:
            result = execute(
                supabase.table("instagram_business_accounts")
                .select("id, username, is_connected, connection_status")
                .eq("id", business_account_id)
                .limit(1),
                table="instagram_business_accounts",
                operation="select",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error(
                f"Circuit breaker OPEN — failed to fetch account {business_account_id}"
            )
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch business account {business_account_id}: {e}")
            return {}

    # ─────────────────────────────────────────
    # WRITE: Mark Account Disconnected
    # ─────────────────────────────────────────
    @staticmethod
    def mark_account_disconnected(business_account_id: str) -> bool:
        """Mark a business account as disconnected after an auth_failure.

        Sets is_connected=False, connection_status='disconnected'.
        Idempotent — safe to call even if already disconnected.
        """
        if not supabase or not business_account_id:
            return False

        update_data = {
            "is_connected": False,
            "connection_status": "disconnected",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            execute(
                supabase.table("instagram_business_accounts")
                .update(update_data)
                .eq("id", business_account_id),
                table="instagram_business_accounts",
                operation="update",
            )
            return True

        except CircuitBreakerError:
            logger.error(
                f"Circuit breaker OPEN — failed to mark account {business_account_id} disconnected"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to mark account {business_account_id} disconnected: {e}")
            return False

    # ─────────────────────────────────────────
    # WRITE: Create System Alert
    # ─────────────────────────────────────────
    @staticmethod
    def create_system_alert(
        alert_type: str,
        business_account_id: str,
        message: str,
        details: dict = None,
    ) -> dict:
        """Insert a system alert row into system_alerts.

        Used for operational alerts that surface in the dashboard.
        Returns the inserted row dict, or {} on failure.
        """
        if not supabase:
            return {}

        row = {
            "alert_type": alert_type,
            "business_account_id": (
                business_account_id if is_valid_uuid(business_account_id) else None
            ),
            "message": message,
            "details": details or {},
            "resolved": False,
        }

        try:
            result = execute(
                supabase.table("system_alerts").insert(row),
                table="system_alerts",
                operation="insert",
            )
            return result.data[0] if result.data else {}

        except CircuitBreakerError:
            logger.error(
                f"Circuit breaker OPEN — failed to create system_alert "
                f"(type={alert_type} account={business_account_id})"
            )
            return {}
        except Exception as e:
            logger.error(f"Failed to create system_alert: {e}")
            return {}
