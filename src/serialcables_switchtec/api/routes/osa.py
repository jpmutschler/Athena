"""Ordered Set Analyzer (OSA) API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.core.osa import OrderedSetAnalyzer

router = APIRouter()


class OsaConfigTypeRequest(BaseModel):
    direction: int = Field(ge=0, le=1)
    lane_mask: int = Field(ge=0, le=0xFFFFFFFF)
    link_rate: int = Field(ge=0, le=6)
    os_types: int = Field(ge=0, le=0xFFFFFFFF)


class OsaConfigPatternRequest(BaseModel):
    direction: int = Field(ge=0, le=1)
    lane_mask: int = Field(ge=0, le=0xFFFFFFFF)
    link_rate: int = Field(ge=0, le=6)
    value_data: list[int] = Field(min_length=4, max_length=4)
    mask_data: list[int] = Field(min_length=4, max_length=4)


class OsaCaptureControlRequest(BaseModel):
    lane_mask: int = Field(ge=0, le=0xFFFFFFFF)
    direction: int = Field(ge=0, le=1)
    drop_single_os: int = Field(default=0, ge=0, le=1)
    stop_mode: int = Field(default=0, ge=0, le=0xFFFFFFFF)
    snapshot_mode: int = Field(default=0, ge=0, le=0xFFFFFFFF)
    post_trigger: int = Field(default=0, ge=0, le=0xFFFFFFFF)
    os_types: int = Field(default=0, ge=0, le=0xFFFFFFFF)


@router.post("/{device_id}/osa/{stack_id}/start")
def osa_start(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
) -> dict[str, str]:
    """Start OSA capture on a stack."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        osa.start(stack_id)
        return {"status": "started"}
    except Exception as e:
        raise_on_error(e, "osa_start")


@router.post("/{device_id}/osa/{stack_id}/stop")
def osa_stop(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
) -> dict[str, str]:
    """Stop OSA capture on a stack."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        osa.stop(stack_id)
        return {"status": "stopped"}
    except Exception as e:
        raise_on_error(e, "osa_stop")


@router.post("/{device_id}/osa/{stack_id}/config-type")
def osa_config_type(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    request: OsaConfigTypeRequest = ...,
) -> dict[str, str]:
    """Configure OSA ordered set type filter."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        osa.configure_type(
            stack_id, request.direction, request.lane_mask,
            request.link_rate, request.os_types,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "osa_config_type")


@router.post("/{device_id}/osa/{stack_id}/config-pattern")
def osa_config_pattern(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    request: OsaConfigPatternRequest = ...,
) -> dict[str, str]:
    """Configure OSA pattern match filter."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        osa.configure_pattern(
            stack_id, request.direction, request.lane_mask,
            request.link_rate, request.value_data, request.mask_data,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "osa_config_pattern")


@router.post("/{device_id}/osa/{stack_id}/capture")
def osa_capture_control(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    request: OsaCaptureControlRequest = ...,
) -> dict[str, str]:
    """Configure and start OSA capture control."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        osa.capture_control(
            stack_id, request.lane_mask, request.direction,
            request.drop_single_os, request.stop_mode,
            request.snapshot_mode, request.post_trigger,
            request.os_types,
        )
        return {"status": "capture_started"}
    except Exception as e:
        raise_on_error(e, "osa_capture_control")


@router.get("/{device_id}/osa/{stack_id}/data/{lane_id}")
def osa_capture_data(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    lane_id: int = Path(ge=0, le=143),
    direction: int = Query(default=0, ge=0, le=1),
) -> dict[str, int]:
    """Read captured OSA data for a lane."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        result = osa.capture_data(stack_id, lane_id, direction)
        return {"status": 0, "result": result}
    except Exception as e:
        raise_on_error(e, "osa_capture_data")


@router.get("/{device_id}/osa/{stack_id}/dump-config")
def osa_dump_config(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
) -> dict[str, int]:
    """Dump current OSA configuration."""
    dev = get_device(device_id)
    try:
        osa = OrderedSetAnalyzer(dev)
        result = osa.dump_config(stack_id)
        return {"status": 0, "result": result}
    except Exception as e:
        raise_on_error(e, "osa_dump_config")
