"""
Heartbeat Sender
================
Sends a periodic liveness ping to the backend so the backend can detect
when the agent is unreachable and trigger its own failover logic.

Schedule: every HEARTBEAT_INTERVAL_MINUTES (default 20 min)
Endpoint: POST {BACKEND_API_URL}/api/instagram/agent/heartbeat
Auth:      X-API-Key header (same key used by the outbound queue worker)
"""

import logging
import os
from datetime import datetime, timezone

import httpx

from config import BACKEND_API_URL, HEARTBEAT_AGENT_ID
from metrics import HEARTBEAT_SENDS
from services.supabase_service import SupabaseService

logger = logging.getLogger(__name__)

_HEARTBEAT_ENDPOINT = f"{BACKEND_API_URL}/api/instagram/agent/heartbeat"


def _backend_headers() -> dict:
    """Auth headers — mirrors queue_worker.py backend_headers()."""
    return {
        "X-API-Key": os.getenv("AGENT_API_KEY", ""),
        "X-User-ID": "agent-service",
        "Content-Type": "application/json",
    }


async def heartbeat_sender_run() -> None:
    """Send a single heartbeat ping to the backend.

    On success: increments success counter, logs debug.
    On failure: increments error counter, logs warning, writes to audit_log
                so the dashboard can surface agent connectivity issues.
    """
    payload = {
        "agent_id": HEARTBEAT_AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _HEARTBEAT_ENDPOINT,
                json=payload,
                headers=_backend_headers(),
            )
            resp.raise_for_status()

        HEARTBEAT_SENDS.labels(status="success").inc()
        logger.debug(f"[Heartbeat] ping OK → {_HEARTBEAT_ENDPOINT}")

    except Exception as exc:
        HEARTBEAT_SENDS.labels(status="error").inc()
        logger.warning(f"[Heartbeat] ping failed: {exc}")

        try:
            await SupabaseService.log_decision(
                event_type="heartbeat_failed",
                action="heartbeat_send",
                resource_type="agent_heartbeats",
                resource_id=HEARTBEAT_AGENT_ID,
                details={"error": str(exc), "endpoint": _HEARTBEAT_ENDPOINT},
                success=False,
            )
        except Exception:
            pass
