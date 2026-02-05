"""
Execution Outcome Logging
==========================
Receives feedback from backend after Instagram API call completes.
Enables learning from outcomes (success/failure patterns).

Endpoints:
  POST /log-outcome - Log execution result for feedback loop
"""

from fastapi import APIRouter, Request

from services.validation import ExecutionOutcome
from services.supabase_service import SupabaseService

log_outcome_router = APIRouter()


@log_outcome_router.post("/log-outcome")
async def log_execution_outcome(outcome: ExecutionOutcome, request: Request):
    """Log execution result for feedback loop.

    Called by backend after Instagram API response.
    Tracks: success rate, error patterns, response times.

    This enables:
    - Understanding which reply types succeed/fail
    - Detecting API rate limit patterns
    - Improving suggested replies based on outcomes
    """
    request_id = getattr(request.state, "request_id", "unknown")

    SupabaseService.log_decision(
        event_type=f"{outcome.resource_type}_execution_outcome",
        action="success" if outcome.success else "failed",
        resource_type=outcome.resource_type,
        resource_id=outcome.resource_id,
        user_id="system",
        details={
            "execution_id": outcome.execution_id,
            "success": outcome.success,
            "error_code": outcome.error_code,
            "error_message": outcome.error_message,
            "instagram_response": outcome.instagram_response,
            "request_id": request_id,
        },
        ip_address=request.client.host if request.client else "unknown",
    )

    return {"logged": True, "request_id": request_id}
