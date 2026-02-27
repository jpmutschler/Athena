"""Diagnostic API routes: eye, LTSSM, loopback, pattern, injection, EQ."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.bindings.constants import (
    DiagEnd,
    DiagLink,
    DiagLtssmSpeed,
    DiagPattern,
    DiagPatternLinkRate,
)
from serialcables_switchtec.core.diagnostics import DiagnosticsManager
from serialcables_switchtec.core.error_injection import ErrorInjector
from serialcables_switchtec.models.diagnostics import (
    CrossHairResult,
    EyeData,
    LoopbackStatus,
    LtssmLogEntry,
    PatternMonResult,
    PortEqCoeff,
    ReceiverObject,
)

router = APIRouter()


# --- Eye Diagram ---------------------------------------------------------


class EyeStartRequest(BaseModel):
    lane_mask: list[int] = Field(
        default=[1, 0, 0, 0], min_length=4, max_length=4
    )
    x_start: int = Field(default=-64, ge=-128, le=0)
    x_end: int = Field(default=64, ge=0, le=128)
    x_step: int = Field(default=1, ge=1, le=16)
    y_start: int = Field(default=-255, ge=-512, le=0)
    y_end: int = Field(default=255, ge=0, le=512)
    y_step: int = Field(default=2, ge=1, le=16)
    step_interval: int = Field(default=10, ge=1, le=1000)


@router.post("/{device_id}/diag/eye/start")
async def eye_start(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: EyeStartRequest = ...,
) -> dict[str, str]:
    """Start eye diagram capture."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.eye_start(
            lane_mask=request.lane_mask,
            x_start=request.x_start,
            x_end=request.x_end,
            x_step=request.x_step,
            y_start=request.y_start,
            y_end=request.y_end,
            y_step=request.y_step,
            step_interval=request.step_interval,
        )
        return {"status": "started"}
    except Exception as e:
        raise_on_error(e, "eye_start")


@router.get(
    "/{device_id}/diag/eye/fetch",
    response_model=EyeData,
)
async def eye_fetch(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    pixel_count: int = Query(default=4096, ge=1, le=1_000_000),
) -> EyeData:
    """Fetch eye diagram data from an in-progress capture."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        return diag.eye_fetch(pixel_count)
    except Exception as e:
        raise_on_error(e, "eye_fetch")


@router.post("/{device_id}/diag/eye/cancel")
async def eye_cancel(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Cancel eye diagram capture."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.eye_cancel()
        return {"status": "cancelled"}
    except Exception as e:
        raise_on_error(e, "eye_cancel")


# --- LTSSM ---------------------------------------------------------------


@router.get(
    "/{device_id}/diag/ltssm/{port_id}",
    response_model=list[LtssmLogEntry],
)
async def ltssm_log(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    max_entries: int = Query(default=64, ge=1, le=1024),
) -> list[LtssmLogEntry]:
    """Get LTSSM state log for a port."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        return diag.ltssm_log(port_id, max_entries=max_entries)
    except Exception as e:
        raise_on_error(e, "ltssm_log")


@router.delete("/{device_id}/diag/ltssm/{port_id}")
async def ltssm_clear(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Clear LTSSM log for a port."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.ltssm_clear(port_id)
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "ltssm_clear")


# --- Loopback ------------------------------------------------------------


class LoopbackSetRequest(BaseModel):
    enable: bool = True
    ltssm_speed: int = Field(default=3, ge=0, le=5)


@router.get(
    "/{device_id}/diag/loopback/{port_id}",
    response_model=LoopbackStatus,
)
async def loopback_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> LoopbackStatus:
    """Get loopback status for a port."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        return diag.loopback_get(port_id)
    except Exception as e:
        raise_on_error(e, "loopback_get")


@router.post("/{device_id}/diag/loopback/{port_id}")
async def loopback_set(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: LoopbackSetRequest = ...,
) -> dict[str, str]:
    """Set loopback on a port."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.loopback_set(
            port_id,
            enable=request.enable,
            ltssm_speed=DiagLtssmSpeed(request.ltssm_speed),
        )
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "loopback_set")


# --- Pattern Gen/Mon -----------------------------------------------------


class PatternGenRequest(BaseModel):
    pattern: int = Field(default=3, ge=0, le=6)
    link_speed: int = Field(default=4, ge=1, le=6)


@router.post("/{device_id}/diag/patgen/{port_id}")
async def pattern_gen_set(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: PatternGenRequest = ...,
) -> dict[str, str]:
    """Set pattern generator on a port."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.pattern_gen_set(
            port_id,
            pattern=DiagPattern(request.pattern),
            link_speed=DiagPatternLinkRate(request.link_speed),
        )
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "pattern_gen_set")


@router.get(
    "/{device_id}/diag/patmon/{port_id}/{lane_id}",
    response_model=PatternMonResult,
)
async def pattern_mon_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    lane_id: int = Path(ge=0, le=143),
) -> PatternMonResult:
    """Get pattern monitor results."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        return diag.pattern_mon_get(port_id, lane_id)
    except Exception as e:
        raise_on_error(e, "pattern_mon_get")


# --- Error Injection -----------------------------------------------------


class DllpInjectRequest(BaseModel):
    data: int = Field(ge=0, le=0xFFFFFFFF)


class DllpCrcInjectRequest(BaseModel):
    enable: bool = True
    rate: int = Field(default=1, ge=0, le=65535)


class TlpLcrcInjectRequest(BaseModel):
    enable: bool = True
    rate: int = Field(default=1, ge=0, le=255)


class AckNackInjectRequest(BaseModel):
    seq_num: int = Field(ge=0, le=0xFFFF)
    count: int = Field(default=1, ge=1, le=255)


@router.post("/{device_id}/diag/inject/dllp/{port_id}")
async def inject_dllp(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: DllpInjectRequest = ...,
) -> dict[str, str]:
    """Inject a DLLP."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_dllp(port_id, request.data)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_dllp")


@router.post("/{device_id}/diag/inject/dllp-crc/{port_id}")
async def inject_dllp_crc(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: DllpCrcInjectRequest = ...,
) -> dict[str, str]:
    """Enable/disable DLLP CRC error injection."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_dllp_crc(port_id, request.enable, request.rate)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "inject_dllp_crc")


@router.post("/{device_id}/diag/inject/tlp-lcrc/{port_id}")
async def inject_tlp_lcrc(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: TlpLcrcInjectRequest = ...,
) -> dict[str, str]:
    """Enable/disable TLP LCRC error injection."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_tlp_lcrc(port_id, request.enable, request.rate)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "inject_tlp_lcrc")


@router.post("/{device_id}/diag/inject/seq-num/{port_id}")
async def inject_seq_num(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Inject a TLP sequence number error."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_tlp_seq_num(port_id)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_seq_num")


@router.post("/{device_id}/diag/inject/ack-nack/{port_id}")
async def inject_ack_nack(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: AckNackInjectRequest = ...,
) -> dict[str, str]:
    """Inject ACK/NACK errors."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_ack_nack(port_id, request.seq_num, request.count)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_ack_nack")


@router.post("/{device_id}/diag/inject/cto/{port_id}")
async def inject_cto(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Inject completion timeout."""
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_cto(port_id)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_cto")


# --- Receiver / EQ -------------------------------------------------------


@router.get(
    "/{device_id}/diag/rcvr/{port_id}/{lane_id}",
    response_model=ReceiverObject,
)
async def rcvr_obj(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    lane_id: int = Path(ge=0, le=143),
    link: Literal["current", "previous"] = "current",
) -> ReceiverObject:
    """Dump receiver calibration object."""
    dev = get_device(device_id)
    link_enum = (
        DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
    )
    try:
        diag = DiagnosticsManager(dev)
        return diag.rcvr_obj(port_id, lane_id, link=link_enum)
    except Exception as e:
        raise_on_error(e, "rcvr_obj")


@router.get(
    "/{device_id}/diag/eq/{port_id}",
    response_model=PortEqCoeff,
)
async def port_eq_coeff(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    end: Literal["local", "far_end"] = "local",
    link: Literal["current", "previous"] = "current",
) -> PortEqCoeff:
    """Get port equalization TX coefficients."""
    dev = get_device(device_id)
    end_enum = DiagEnd.LOCAL if end == "local" else DiagEnd.FAR_END
    link_enum = (
        DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
    )
    try:
        diag = DiagnosticsManager(dev)
        return diag.port_eq_tx_coeff(port_id, end=end_enum, link=link_enum)
    except Exception as e:
        raise_on_error(e, "port_eq_tx_coeff")


# --- Cross Hair -----------------------------------------------------------


@router.post("/{device_id}/diag/crosshair/enable/{lane_id}")
async def crosshair_enable(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    lane_id: int = Path(ge=0, le=143),
) -> dict[str, str]:
    """Enable cross-hair measurement."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.cross_hair_enable(lane_id)
        return {"status": "enabled"}
    except Exception as e:
        raise_on_error(e, "crosshair_enable")


@router.post("/{device_id}/diag/crosshair/disable")
async def crosshair_disable(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Disable cross-hair measurement."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        diag.cross_hair_disable()
        return {"status": "disabled"}
    except Exception as e:
        raise_on_error(e, "crosshair_disable")


@router.get(
    "/{device_id}/diag/crosshair",
    response_model=list[CrossHairResult],
)
async def crosshair_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    start_lane: int = Query(default=0, ge=0, le=143),
    num_lanes: int = Query(default=1, ge=1, le=64),
) -> list[CrossHairResult]:
    """Get cross-hair measurement results."""
    dev = get_device(device_id)
    try:
        diag = DiagnosticsManager(dev)
        return diag.cross_hair_get(start_lane, num_lanes)
    except Exception as e:
        raise_on_error(e, "crosshair_get")
