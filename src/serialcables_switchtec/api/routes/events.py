"""Event management API routes."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.events import EventSummaryResult

router = APIRouter()

_event_wait_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="event-wait")





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
        mgr = dev.events
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
        mgr = dev.events
        mgr.clear_all()
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "clear_events")


@router.post("/{device_id}/events/wait")
async def wait_for_event(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: WaitEventRequest = ...,
) -> dict[str, str]:
    """Wait for any event to occur.

    Uses a dedicated thread pool executor to avoid exhausting FastAPI's
    default thread pool, since the underlying C call can block for up
    to 300 seconds.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.events
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _event_wait_executor,
            partial(mgr.wait_for_event, timeout_ms=request.timeout_ms),
        )
        return {"status": "event_received"}
    except Exception as e:
        raise_on_error(e, "wait_for_event")
