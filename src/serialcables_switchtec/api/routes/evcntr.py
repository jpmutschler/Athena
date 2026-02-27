"""Event counter API routes for BER testing and error monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.core.evcntr import EventCounterManager
from serialcables_switchtec.models.evcntr import (
    EvCntrSetupRequest,
    EvCntrSetupResult,
    EvCntrValue,
)

router = APIRouter()


@router.post("/{device_id}/evcntr/{stack_id}/{counter_id}/setup")
def evcntr_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    request: EvCntrSetupRequest = ...,
) -> dict[str, str]:
    """Configure an event counter."""
    dev = get_device(device_id)
    try:
        mgr = EventCounterManager(dev)
        mgr.setup(
            stack_id, counter_id,
            request.port_mask, request.type_mask,
            egress=request.egress, threshold=request.threshold,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "evcntr_setup")


@router.get(
    "/{device_id}/evcntr/{stack_id}/{counter_id}/setup",
    response_model=list[EvCntrSetupResult],
)
def evcntr_get_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
) -> list[EvCntrSetupResult]:
    """Read event counter setup configuration."""
    dev = get_device(device_id)
    try:
        mgr = EventCounterManager(dev)
        return mgr.get_setup(stack_id, counter_id, nr_counters)
    except Exception as e:
        raise_on_error(e, "evcntr_get_setup")


@router.get("/{device_id}/evcntr/{stack_id}/{counter_id}/counts")
def evcntr_get_counts(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
    clear: bool = Query(default=False),
) -> dict[str, list[dict[str, int]]]:
    """Read event counter values."""
    dev = get_device(device_id)
    try:
        mgr = EventCounterManager(dev)
        counts = mgr.get_counts(stack_id, counter_id, nr_counters, clear=clear)
        return {
            "counters": [
                {"id": counter_id + i, "count": c}
                for i, c in enumerate(counts)
            ],
        }
    except Exception as e:
        raise_on_error(e, "evcntr_get_counts")


@router.get(
    "/{device_id}/evcntr/{stack_id}/{counter_id}",
    response_model=list[EvCntrValue],
)
def evcntr_get_both(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
    clear: bool = Query(default=False),
) -> list[EvCntrValue]:
    """Read event counter values with setup configuration."""
    dev = get_device(device_id)
    try:
        mgr = EventCounterManager(dev)
        return mgr.get_both(stack_id, counter_id, nr_counters, clear=clear)
    except Exception as e:
        raise_on_error(e, "evcntr_get_both")
