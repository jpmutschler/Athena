"""SSE streaming endpoints for link health monitoring."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.core.monitor import LinkHealthMonitor
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

_EXHAUSTED = object()  # Sentinel for generator exhaustion


def _next_sample(gen):
    """Advance generator, returning sentinel on exhaustion.

    StopIteration does not propagate correctly through
    asyncio.run_in_executor, so we catch it here.
    """
    try:
        return next(gen)
    except StopIteration:
        return _EXHAUSTED


async def _stream_bw(
    monitor: LinkHealthMonitor,
    port_ids: list[int],
    interval: float,
    count: int,
) -> AsyncGenerator[str, None]:
    """Yield SSE events from bandwidth generator."""
    loop = asyncio.get_event_loop()
    gen = monitor.watch_bw(port_ids, interval=interval, count=count)
    try:
        while True:
            sample = await loop.run_in_executor(None, _next_sample, gen)
            if sample is _EXHAUSTED:
                break
            yield f"data: {sample.model_dump_json()}\n\n"
    except asyncio.CancelledError:
        gen.close()
        raise
    finally:
        gen.close()


async def _stream_evcntr(
    monitor: LinkHealthMonitor,
    stack_id: int,
    counter_id: int,
    nr_counters: int,
    interval: float,
    count: int,
) -> AsyncGenerator[str, None]:
    """Yield SSE events from event counter generator."""
    loop = asyncio.get_event_loop()
    gen = monitor.watch_evcntr(
        stack_id, counter_id, nr_counters,
        interval=interval, count=count,
    )
    try:
        while True:
            sample = await loop.run_in_executor(None, _next_sample, gen)
            if sample is _EXHAUSTED:
                break
            yield f"data: {sample.model_dump_json()}\n\n"
    except asyncio.CancelledError:
        gen.close()
        raise
    finally:
        gen.close()


@router.get("/{device_id}/monitor/bw")
def monitor_bandwidth(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_ids: str = Query(
        description="Comma-separated physical port IDs (0-59).",
        examples=["0,4"],
    ),
    interval: float = Query(
        default=1.0, ge=0.1, le=60.0,
        description="Seconds between samples.",
    ),
    count: int = Query(
        default=60, ge=0, le=86400,
        description="Number of samples (0 = infinite).",
    ),
) -> StreamingResponse:
    """Stream bandwidth counter samples as SSE events.

    Each event is a JSON-encoded BwSample with fields: timestamp,
    elapsed_s, iteration, port_id, time_us, egress_total, ingress_total,
    and per-category breakdowns (posted, comp, nonposted).

    Use `count=0` for continuous monitoring. The stream ends when
    `count` samples have been sent or the client disconnects.
    """
    parsed_ids = _parse_port_ids(port_ids)
    dev = get_device(device_id)
    monitor = LinkHealthMonitor(dev)

    return StreamingResponse(
        _stream_bw(monitor, parsed_ids, interval, count),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{device_id}/monitor/evcntr")
def monitor_event_counters(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Query(ge=0, le=7, description="Stack ID."),
    counter_id: int = Query(ge=0, description="Starting counter ID."),
    nr_counters: int = Query(
        default=1, ge=1, le=64,
        description="Number of consecutive counters.",
    ),
    interval: float = Query(
        default=1.0, ge=0.1, le=60.0,
        description="Seconds between samples.",
    ),
    count: int = Query(
        default=60, ge=0, le=86400,
        description="Number of samples (0 = infinite).",
    ),
) -> StreamingResponse:
    """Stream event counter samples as SSE events.

    Each event is a JSON-encoded EvCntrSample with fields: timestamp,
    elapsed_s, iteration, stack_id, counter_id, count, delta.

    Uses clear-on-read so each sample shows the delta since last read.
    """
    dev = get_device(device_id)
    monitor = LinkHealthMonitor(dev)

    return StreamingResponse(
        _stream_evcntr(monitor, stack_id, counter_id, nr_counters, interval, count),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _parse_port_ids(port_ids_str: str) -> list[int]:
    """Parse comma-separated port IDs with validation."""
    try:
        ids = [int(p.strip()) for p in port_ids_str.split(",") if p.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid port_ids format: {exc}",
        ) from exc

    if not ids:
        raise HTTPException(
            status_code=400,
            detail="At least one port_id is required.",
        )

    for pid in ids:
        if not (0 <= pid <= 59):
            raise HTTPException(
                status_code=400,
                detail=f"port_id {pid} out of range 0-59.",
            )

    return ids
