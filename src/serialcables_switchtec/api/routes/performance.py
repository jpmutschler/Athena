"""Performance monitoring API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field, field_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.core.performance import PerformanceManager
from serialcables_switchtec.models.performance import BwCounterResult, LatencyResult

router = APIRouter()


class BwRequest(BaseModel):
    port_ids: list[int] = Field(min_length=1, max_length=60)
    clear: bool = False

    @field_validator("port_ids")
    @classmethod
    def validate_port_ids(cls, v: list[int]) -> list[int]:
        for pid in v:
            if not (0 <= pid <= 59):
                raise ValueError(f"port_id {pid} out of range 0-59")
        return v


@router.post(
    "/{device_id}/perf/bw",
    response_model=list[BwCounterResult],
)
def get_bandwidth(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: BwRequest = ...,
) -> list[BwCounterResult]:
    """Get bandwidth counters for specified ports."""
    dev = get_device(device_id)
    try:
        mgr = PerformanceManager(dev)
        return mgr.bw_get(request.port_ids, clear=request.clear)
    except Exception as e:
        raise_on_error(e, "bw_get")


class LatSetupRequest(BaseModel):
    egress_port_id: int = Field(ge=0, le=59)
    ingress_port_id: int = Field(ge=0, le=59)
    clear: bool = False


@router.post("/{device_id}/perf/latency/setup")
def latency_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: LatSetupRequest = ...,
) -> dict[str, str]:
    """Configure latency measurement between two ports."""
    dev = get_device(device_id)
    try:
        mgr = PerformanceManager(dev)
        mgr.lat_setup(
            request.egress_port_id,
            request.ingress_port_id,
            clear=request.clear,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "lat_setup")


@router.get(
    "/{device_id}/perf/latency/{egress_port_id}",
    response_model=LatencyResult,
)
def get_latency(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    egress_port_id: int = Path(ge=0, le=59),
    clear: bool = Query(default=False),
) -> LatencyResult:
    """Get latency measurement for an egress port."""
    dev = get_device(device_id)
    try:
        mgr = PerformanceManager(dev)
        return mgr.lat_get(egress_port_id, clear=clear)
    except Exception as e:
        raise_on_error(e, "lat_get")
