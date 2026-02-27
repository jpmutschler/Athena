"""Event management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.core.events import EventManager
from serialcables_switchtec.models.events import EventSummaryResult

router = APIRouter()





class WaitEventRequest(BaseModel):
    timeout_ms: int = Field(default=-1, ge=-1, le=300000)


@router.get(
    "/{device_id}/events/summary",
    response_model=EventSummaryResult,
)
def get_event_summary(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> EventSummaryResult:
    """Get a summary of all pending events."""
    dev = get_device(device_id)
    try:
        mgr = EventManager(dev)
        return mgr.get_summary()
    except Exception as e:
        raise_on_error(e, "get_event_summary")


@router.post("/{device_id}/events/clear")
def clear_events(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Clear all events."""
    dev = get_device(device_id)
    try:
        mgr = EventManager(dev)
        mgr.clear_all()
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "clear_events")


@router.post("/{device_id}/events/wait")
def wait_for_event(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: WaitEventRequest = ...,
) -> dict[str, str]:
    """Wait for any event to occur."""
    dev = get_device(device_id)
    try:
        mgr = EventManager(dev)
        mgr.wait_for_event(timeout_ms=request.timeout_ms)
        return {"status": "event_received"}
    except Exception as e:
        raise_on_error(e, "wait_for_event")
