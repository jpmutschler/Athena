"""Diagnostic API routes: eye, LTSSM, loopback, pattern, injection, EQ."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field, field_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.rate_limit import injection_limiter
from serialcables_switchtec.bindings.constants import (
    DiagEnd,
    DiagLink,
    DiagLtssmSpeed,
    DiagPatternLinkRate,
)
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

    @field_validator("lane_mask")
    @classmethod
    def validate_lane_mask_values(cls, v: list[int]) -> list[int]:
        for i, val in enumerate(v):
            if not (0 <= val <= 0xFFFFFFFF):
                raise ValueError(f"lane_mask[{i}] must be 0-0xFFFFFFFF")
        return v


@router.post(
    "/{device_id}/diag/eye/start",
    responses={
        400: {
            "description": "Invalid parameter such as out-of-range lane_mask "
            "word, x/y step values, or step_interval.",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error -- the MRPC command "
            "to initiate the eye scan failed.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while starting the eye capture.",
        },
    },
)
def eye_start(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: EyeStartRequest = ...,
) -> dict[str, str]:
    """Start an eye diagram capture on the device.

    Initiates an asynchronous eye diagram scan across the specified lanes.
    The capture runs in firmware and must be polled via the `eye_fetch`
    endpoint until all pixels are returned.

    **lane_mask** is a 4-element array of 32-bit unsigned integers that
    together form a 128-bit bitmask selecting which physical lanes to scan.
    Each bit position corresponds to a lane number (bit 0 of word 0 = lane 0,
    bit 31 of word 3 = lane 127). Set `[1, 0, 0, 0]` (the default) to scan
    only lane 0.

    **x_start / x_end / x_step** define the horizontal (timing) sweep grid
    in UI fractions. The range -128..128 covers one full Unit Interval.
    Larger step values produce a coarser but faster scan.

    **y_start / y_end / y_step** define the vertical (voltage) sweep grid.
    The range -512..512 covers the full voltage swing. A `y_step` of 2
    (default) balances resolution and scan time.

    **step_interval** controls the dwell time per grid point in
    firmware-defined units (1-1000). Higher values improve BER accuracy
    at each pixel but increase total scan time.

    Returns `{"status": "started"}` on success. Only one eye capture may be
    active per device at a time; start a new capture to override the
    previous one, or call `eye_cancel` to abort.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
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
    responses={
        400: {
            "description": "Invalid pixel_count value.",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while fetching "
            "eye data from the device firmware.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during the fetch operation.",
        },
    },
)
def eye_fetch(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    pixel_count: int = Query(default=4096, ge=1, le=1_000_000),
) -> EyeData:
    """Fetch eye diagram data from an in-progress capture.

    Retrieves up to `pixel_count` BER measurement pixels from the
    firmware's eye scan buffer. This endpoint should be polled
    repeatedly after calling `eye_start` until all data is received.

    **pixel_count** (default 4096) controls how many pixel values to
    request in a single call. Larger values reduce round-trips but
    increase response payload size.

    The response contains:
    - **lane_id**: The physical lane number this data belongs to.
    - **x_range**: The horizontal (timing) sweep parameters
      (start, end, step) as configured in the start request.
    - **y_range**: The vertical (voltage) sweep parameters
      (start, end, step) as configured in the start request.
    - **pixels**: A flat list of floating-point BER values ordered
      row-major (y varies first within each x position). A value of
      0.0 indicates no errors detected at that grid point.

    If the capture is still in progress, only the pixels completed
    so far are returned. Poll again to retrieve additional data.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        return diag.eye_fetch(pixel_count)
    except Exception as e:
        raise_on_error(e, "eye_fetch")


@router.post(
    "/{device_id}/diag/eye/cancel",
    responses={
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while sending the "
            "cancel command to the device.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while cancelling the eye capture.",
        },
    },
)
def eye_cancel(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Cancel a running eye diagram capture on the device.

    Sends an abort command to the firmware to stop the in-progress eye
    scan. Any partial pixel data already captured is discarded. This is
    safe to call even if no capture is currently running -- the firmware
    will acknowledge the cancel regardless.

    Returns `{"status": "cancelled"}` on success.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        diag.eye_cancel()
        return {"status": "cancelled"}
    except Exception as e:
        raise_on_error(e, "eye_cancel")


# --- LTSSM ---------------------------------------------------------------


@router.get(
    "/{device_id}/diag/ltssm/{port_id}",
    response_model=list[LtssmLogEntry],
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or invalid "
            "max_entries value.",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while reading the "
            "LTSSM state log from the device.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while reading LTSSM data.",
        },
    },
)
def ltssm_log(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    max_entries: int = Query(default=64, ge=1, le=1024),
) -> list[LtssmLogEntry]:
    """Retrieve the LTSSM state transition log for a physical port.

    Returns the most recent Link Training and Status State Machine
    (LTSSM) state transitions recorded by the switch firmware for the
    specified port. This is essential for diagnosing link training
    failures, speed negotiation issues, and unexpected link-down events.

    **port_id** is the physical port number (0-59).

    **max_entries** (default 64) limits how many log entries to return.
    The firmware maintains a circular buffer; older entries are
    overwritten when the buffer is full.

    Each entry in the response contains:
    - **timestamp**: Firmware timestamp counter value at the transition.
    - **link_rate**: Negotiated link rate in GT/s (e.g., 8.0 for Gen3,
      16.0 for Gen4, 32.0 for Gen5, 64.0 for Gen6).
    - **link_state**: Numeric LTSSM state code. The encoding differs by
      PCIe generation: Gen3/Gen4 uses a 16-bit format where the upper
      byte is the minor state and the lower byte is the major state;
      Gen5 uses a similar format with additional sub-states; Gen6 uses
      a flat 8-bit encoding (0x00-0x23).
    - **link_state_str**: Human-readable LTSSM state name decoded from
      the appropriate generation-specific lookup table (e.g.,
      "Recovery (EQ_PH2)", "L0 (ACTIVE)").
    - **link_width**: Negotiated link width in lanes (e.g., 1, 2, 4,
      8, 16).
    - **tx_minor_state**: TX-side minor state detail.
    - **rx_minor_state**: RX-side minor state detail.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        return diag.ltssm_log(port_id, max_entries=max_entries)
    except Exception as e:
        raise_on_error(e, "ltssm_log")


@router.delete(
    "/{device_id}/diag/ltssm/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while clearing the "
            "LTSSM log buffer.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while clearing LTSSM data.",
        },
    },
)
def ltssm_clear(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Clear the LTSSM state transition log for a physical port.

    Resets the firmware's circular LTSSM log buffer for the given port,
    discarding all recorded state transitions. Use this before
    triggering a link re-training event to capture a clean trace of the
    training sequence.

    **port_id** is the physical port number (0-59).

    Returns `{"status": "cleared"}` on success.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
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
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while querying "
            "loopback status.",
        },
    },
)
def loopback_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> LoopbackStatus:
    """Get the current loopback configuration for a physical port.

    Queries the switch to determine whether loopback is active on the
    specified port and, if so, at what speed.

    **port_id** is the physical port number (0-59).

    The response contains:
    - **port_id**: The physical port number queried.
    - **enabled**: Loopback enable bitmask. The bits map to loopback
      modes: bit 0 = RX-to-TX (retimer-style, data received on RX is
      looped back out TX), bit 1 = TX-to-RX (data transmitted is
      looped back to the local receiver), bit 2 = LTSSM loopback
      (entered via the PCIe LTSSM Loopback state), bit 3 = PIPE
      loopback (loopback at the PIPE/PHY interface level). A value of
      0 means loopback is disabled.
    - **ltssm_speed**: The link speed used for loopback, encoded as a
      DiagLtssmSpeed value: 0 = Gen1 (2.5 GT/s), 1 = Gen2 (5 GT/s),
      2 = Gen3 (8 GT/s), 3 = Gen4 (16 GT/s), 4 = Gen5 (32 GT/s),
      5 = Gen6 (64 GT/s).
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        return diag.loopback_get(port_id)
    except Exception as e:
        raise_on_error(e, "loopback_get")


@router.post(
    "/{device_id}/diag/loopback/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or invalid "
            "ltssm_speed value (must be 0-5).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while configuring "
            "loopback on the port.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while setting loopback.",
        },
    },
)
def loopback_set(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: LoopbackSetRequest = ...,
) -> dict[str, str]:
    """Enable or disable loopback on a physical port.

    Configures the switch port to enter or exit loopback mode at the
    specified link speed. Loopback is used for BER testing and link
    validation without requiring a remote endpoint.

    **port_id** is the physical port number (0-59).

    **enable** (default true) controls whether loopback is turned on
    or off. Set to false to disable loopback and return the port to
    normal operation.

    **ltssm_speed** (default 3 = Gen4) selects the target link speed
    for the loopback session:
    - 0 = Gen1 (2.5 GT/s)
    - 1 = Gen2 (5.0 GT/s)
    - 2 = Gen3 (8.0 GT/s)
    - 3 = Gen4 (16.0 GT/s)
    - 4 = Gen5 (32.0 GT/s)
    - 5 = Gen6 (64.0 GT/s)

    The port will re-train at the requested speed when loopback is
    enabled. Returns `{"status": "ok"}` on success.

    **Warning**: Enabling loopback will disrupt any active PCIe traffic
    on the port. Ensure no host or endpoint depends on this link before
    enabling loopback.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
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
    pattern: int = Field(default=3, ge=0, le=0x1A)
    link_speed: int = Field(default=4, ge=1, le=6)


@router.post(
    "/{device_id}/diag/patgen/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id, pattern type, or link_speed "
            "value.",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while configuring "
            "the pattern generator.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while setting pattern generation.",
        },
    },
)
def pattern_gen_set(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: PatternGenRequest = ...,
) -> dict[str, str]:
    """Configure the PRBS pattern generator on a physical port.

    Starts or reconfigures the built-in pseudo-random bit sequence
    (PRBS) pattern generator on the specified port. The generated
    pattern is transmitted continuously on all active lanes and can be
    checked by the pattern monitor on the receiving end (local or
    remote) to measure bit error rate (BER).

    **port_id** is the physical port number (0-59).

    **pattern** (default 3) selects the PRBS polynomial. The valid
    values depend on the PCIe generation:

    *Gen3/Gen4 patterns (DiagPattern):*
    - 0 = PRBS-7
    - 1 = PRBS-11
    - 2 = PRBS-23
    - 3 = PRBS-31 (default, industry-standard for BER testing)
    - 4 = PRBS-9
    - 5 = PRBS-15
    - 6 = Disabled

    *Gen5 patterns (DiagPatternGen5):*
    - 0-5 = Same as Gen3/Gen4
    - 6 = PRBS-5
    - 7 = PRBS-20
    - 10 = Disabled

    *Gen6 patterns (DiagPatternGen6):*
    - 0 = PRBS-7
    - 1 = PRBS-9
    - 2 = PRBS-11
    - 3 = PRBS-13
    - 4 = PRBS-15
    - 5 = PRBS-23
    - 6 = PRBS-31
    - 0x19 = PCIe 52-UI jitter pattern
    - 0x1A = Disabled

    **link_speed** (default 4 = Gen4) sets the link rate for pattern
    generation: 1 = Gen1, 2 = Gen2, 3 = Gen3, 4 = Gen4, 5 = Gen5,
    6 = Gen6. Set to 0 to disable.

    Returns `{"status": "ok"}` on success.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        diag.pattern_gen_set(
            port_id,
            pattern=request.pattern,
            link_speed=DiagPatternLinkRate(request.link_speed),
        )
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "pattern_gen_set")


@router.get(
    "/{device_id}/diag/patmon/{port_id}/{lane_id}",
    response_model=PatternMonResult,
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or lane_id "
            "(must be 0-143).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while reading "
            "pattern monitor counters.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while reading monitor results.",
        },
    },
)
def pattern_mon_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    lane_id: int = Path(ge=0, le=143),
) -> PatternMonResult:
    """Read the pattern monitor error count for a specific lane.

    Retrieves the current state of the built-in PRBS pattern checker
    (monitor) on the specified port and lane. The monitor compares
    incoming data against the expected PRBS pattern and counts bit
    errors, providing a direct BER measurement.

    **port_id** is the physical port number (0-59).

    **lane_id** is the physical lane number within the port (0-143).
    Gen3/4/5 devices support up to 100 lanes; Gen6 devices support up
    to 144 lanes.

    The response contains:
    - **port_id**: The physical port number.
    - **lane_id**: The physical lane number.
    - **pattern_type**: The PRBS pattern type the monitor is locked to
      (see pattern_gen_set for the pattern type encoding).
    - **error_count**: The cumulative number of bit errors detected
      since the monitor was last reset or the pattern generator was
      started.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
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


@router.post(
    "/{device_id}/diag/inject/dllp/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or DLLP data "
            "value out of range (must be 0-0xFFFFFFFF).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while injecting "
            "the DLLP.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during DLLP injection.",
        },
    },
)
def inject_dllp(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: DllpInjectRequest = ...,
) -> dict[str, str]:
    """Inject a raw Data Link Layer Packet (DLLP) on a physical port.

    Sends a single crafted DLLP with the specified 32-bit data payload
    out of the given port. This is used for testing how the link partner
    handles unexpected or malformed DLLPs (e.g., UpdateFC, Ack, Nak,
    PM messages).

    **port_id** is the physical port number (0-59).

    **data** is the raw 32-bit DLLP content (0x00000000 - 0xFFFFFFFF).
    The DLLP type is encoded in bits [31:24] per the PCIe specification:
    for example, 0x00 = Ack, 0x10 = Nak, 0x40-0x50 = UpdateFC types.

    This endpoint is rate-limited to 10 calls per 60-second window per
    device to prevent accidental link saturation.

    Returns `{"status": "injected"}` on success.

    **Warning**: Injecting arbitrary DLLPs on a live link can cause
    data corruption, link errors, or link-down events. Use only in
    controlled test environments.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_dllp(port_id, request.data)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_dllp")


@router.post(
    "/{device_id}/diag/inject/dllp-crc/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or rate value "
            "out of range (must be 0-65535).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while configuring "
            "DLLP CRC injection.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during DLLP CRC injection configuration.",
        },
    },
)
def inject_dllp_crc(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: DllpCrcInjectRequest = ...,
) -> dict[str, str]:
    """Enable or disable continuous DLLP CRC error injection on a port.

    When enabled, the switch firmware deliberately corrupts the CRC
    field of outgoing DLLPs at the configured rate. The link partner's
    data link layer will detect these as bad DLLPs and increment its
    BAD_DLLP error counter, triggering correctable error reporting.

    **port_id** is the physical port number (0-59).

    **enable** (default true) turns CRC corruption on or off. Set to
    false to stop injecting errors and restore normal DLLP CRC
    generation.

    **rate** (default 1) controls the injection frequency. A value of
    1 corrupts every DLLP; higher values corrupt every Nth DLLP (range
    0-65535, where 0 typically means inject on every packet).

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "ok"}` on success.

    **Warning**: DLLP CRC errors will trigger correctable error
    reporting (AER CE) on the link partner and may cause REPLAY_TIMER
    or REPLAY_NUM_ROLLOVER errors if sustained.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_dllp_crc(port_id, request.enable, request.rate)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "inject_dllp_crc")


@router.post(
    "/{device_id}/diag/inject/tlp-lcrc/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or rate value "
            "out of range (must be 0-255).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while configuring "
            "TLP LCRC injection.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during TLP LCRC injection configuration.",
        },
    },
)
def inject_tlp_lcrc(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: TlpLcrcInjectRequest = ...,
) -> dict[str, str]:
    """Enable or disable continuous TLP LCRC error injection on a port.

    When enabled, the switch firmware deliberately corrupts the Link
    CRC (LCRC) of outgoing Transaction Layer Packets at the configured
    rate. The link partner will detect these as bad TLPs and request
    retransmission via the data link layer replay mechanism.

    **port_id** is the physical port number (0-59).

    **enable** (default true) turns LCRC corruption on or off. Set to
    false to stop injecting errors and restore normal TLP CRC
    generation.

    **rate** (default 1) controls the injection frequency. A value of
    1 corrupts every TLP; higher values corrupt every Nth TLP (range
    0-255).

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "ok"}` on success.

    **Warning**: TLP LCRC errors trigger BAD_TLP correctable errors
    and data link layer replays. Sustained injection at high rates can
    exhaust the replay buffer, causing REPLAY_NUM_ROLLOVER and
    potentially a fatal link error.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_tlp_lcrc(port_id, request.enable, request.rate)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "inject_tlp_lcrc")


@router.post(
    "/{device_id}/diag/inject/seq-num/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while injecting "
            "the TLP sequence number error.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during sequence number injection.",
        },
    },
)
def inject_seq_num(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Inject a single TLP sequence number error on a physical port.

    Forces the switch to transmit the next TLP with an incorrect data
    link layer sequence number. The link partner will detect the
    out-of-sequence TLP, NAK it, and trigger a replay of all TLPs from
    the last acknowledged sequence number onward.

    This is a one-shot injection -- only one TLP is affected per call.
    No request body is required.

    **port_id** is the physical port number (0-59).

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "injected"}` on success.

    **Warning**: Sequence number errors trigger a BAD_TLP event and
    data link replay. While a single injection is generally recoverable,
    repeated rapid injections may cause REPLAY_NUM_ROLLOVER.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_tlp_seq_num(port_id)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_seq_num")


@router.post(
    "/{device_id}/diag/inject/ack-nack/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59), seq_num "
            "(must be 0-65535), or count (must be 1-255).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while injecting "
            "ACK/NACK errors.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during ACK/NACK injection.",
        },
    },
)
def inject_ack_nack(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: AckNackInjectRequest = ...,
) -> dict[str, str]:
    """Inject ACK/NACK DLLP errors targeting a specific sequence number.

    Forces the switch to send malformed ACK or NACK DLLPs referencing
    the specified TLP sequence number. This simulates a data link layer
    acknowledgment failure and exercises the link partner's replay and
    error recovery logic.

    **port_id** is the physical port number (0-59).

    **seq_num** is the 16-bit TLP sequence number (0-65535) to reference
    in the injected ACK/NACK DLLPs.

    **count** (default 1) is the number of erroneous ACK/NACK DLLPs to
    inject (1-255). Multiple injections in a burst stress the replay
    buffer more aggressively.

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "injected"}` on success.

    **Warning**: ACK/NACK injection forces TLP replays and can trigger
    REPLAY_TIMER_TIMEOUT or NAK_RCVD correctable errors on the link
    partner. High counts may cause link degradation.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        injector = ErrorInjector(dev)
        injector.inject_ack_nack(port_id, request.seq_num, request.count)
        return {"status": "injected"}
    except Exception as e:
        raise_on_error(e, "inject_ack_nack")


@router.post(
    "/{device_id}/diag/inject/cto/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. Error injection endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while injecting "
            "the completion timeout.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during completion timeout injection.",
        },
    },
)
def inject_cto(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> dict[str, str]:
    """Inject a completion timeout (CTO) error on a physical port.

    Forces a completion timeout condition by suppressing the completion
    for the next non-posted request (e.g., a memory read or
    configuration read) transiting the specified port. The requester
    will observe a completion timeout, which is an uncorrectable
    non-fatal error that triggers AER reporting.

    This is a one-shot injection -- only one transaction is affected
    per call. No request body is required.

    **port_id** is the physical port number (0-59).

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "injected"}` on success.

    **Warning**: Completion timeout is an uncorrectable (non-fatal)
    error. Depending on the host OS AER policy, this may trigger error
    logging, device recovery, or function-level reset. Use only in
    controlled test environments.
    """
    injection_limiter.check(device_id)
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
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59) or lane_id "
            "(must be 0-143).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while reading "
            "receiver calibration data.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while reading receiver data.",
        },
    },
)
def rcvr_obj(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    lane_id: int = Path(ge=0, le=143),
    link: Literal["current", "previous"] = "current",
) -> ReceiverObject:
    """Dump the receiver calibration object for a specific lane.

    Reads the receiver's analog front-end calibration state for the
    given port and lane, including CTLE and DFE tap settings that
    were determined during link training equalization. This data is
    essential for diagnosing signal integrity issues and verifying
    that the receiver has converged to an optimal configuration.

    **port_id** is the physical port number (0-59).

    **lane_id** is the physical lane number (0-143). Gen3/4/5 devices
    support up to 100 lanes; Gen6 devices support up to 144 lanes.

    **link** (default "current") selects whether to read calibration
    data from the currently active link or the previous link session
    (before the most recent re-training). Use "previous" to compare
    receiver state before and after a link re-training event.

    The response contains:
    - **port_id**: The physical port number.
    - **lane_id**: The physical lane number.
    - **ctle**: Continuous Time Linear Equalizer setting. This is the
      analog high-frequency boost applied at the receiver input to
      compensate for channel loss. Higher values indicate more
      aggressive equalization for lossier channels.
    - **target_amplitude**: The target signal amplitude the receiver
      AGC (Automatic Gain Control) is aiming for, in firmware-defined
      units.
    - **speculative_dfe**: The speculative Decision Feedback Equalizer
      tap value. DFE removes post-cursor inter-symbol interference by
      subtracting a weighted version of previously decided bits.
    - **dynamic_dfe**: A list of dynamic DFE tap coefficient values.
      Each element represents a tap weight (tap1, tap2, etc.). More
      taps provide finer ISI cancellation at higher link speeds.
    """
    dev = get_device(device_id)
    link_enum = (
        DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
    )
    try:
        diag = dev.diagnostics
        return diag.rcvr_obj(port_id, lane_id, link=link_enum)
    except Exception as e:
        raise_on_error(e, "rcvr_obj")


@router.get(
    "/{device_id}/diag/eq/{port_id}",
    response_model=PortEqCoeff,
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while reading "
            "equalization coefficients.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while reading equalization data.",
        },
    },
)
def port_eq_coeff(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    end: Literal["local", "far_end"] = "local",
    link: Literal["current", "previous"] = "current",
) -> PortEqCoeff:
    """Get the TX equalization coefficients for all lanes on a port.

    Reads the transmitter pre-cursor and post-cursor de-emphasis
    coefficients that were negotiated during PCIe link equalization
    (Gen3+). These coefficients control the TX output waveform to
    compensate for channel insertion loss and improve the eye opening
    at the receiver.

    **port_id** is the physical port number (0-59).

    **end** (default "local") selects which end of the link to query:
    - "local" returns the TX coefficients applied by this switch port's
      transmitter (i.e., the values the local TX is using to drive the
      channel toward the link partner).
    - "far_end" returns the TX coefficients reported by the link
      partner's transmitter (i.e., the values the remote device is
      using to drive the channel toward this switch).

    **link** (default "current") selects whether to read coefficients
    from the currently active link or the previous link session. Use
    "previous" to compare equalization results before and after a
    re-training event.

    The response contains:
    - **lane_count**: Number of active lanes on this port.
    - **cursors**: A list of EqCursor objects, one per lane, each
      containing:
      - **pre**: The pre-cursor de-emphasis coefficient (controls the
        amplitude of the bit transmitted before the cursor bit). Higher
        pre-cursor values reduce pre-shoot but cost signal amplitude.
      - **post**: The post-cursor de-emphasis coefficient (controls the
        amplitude of the bit transmitted after the cursor bit). Higher
        post-cursor values reduce inter-symbol interference from
        previous bits.

    The coefficient values are in hardware-specific units. Typical
    Gen3/Gen4 ranges are 0-10 for pre-cursor and 0-20 for post-cursor,
    though exact ranges depend on the PHY implementation.
    """
    dev = get_device(device_id)
    end_enum = DiagEnd.LOCAL if end == "local" else DiagEnd.FAR_END
    link_enum = (
        DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
    )
    try:
        diag = dev.diagnostics
        return diag.port_eq_tx_coeff(port_id, end=end_enum, link=link_enum)
    except Exception as e:
        raise_on_error(e, "port_eq_tx_coeff")


# --- Cross Hair -----------------------------------------------------------


@router.post(
    "/{device_id}/diag/crosshair/enable/{lane_id}",
    responses={
        400: {
            "description": "Invalid lane_id (must be 0-143).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while enabling "
            "cross-hair measurement.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while enabling cross-hair mode.",
        },
    },
)
def crosshair_enable(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    lane_id: int = Path(ge=0, le=143),
) -> dict[str, str]:
    """Enable cross-hair eye margin measurement on a specific lane.

    Activates the firmware's cross-hair measurement mode for the given
    lane. Cross-hair measurement is a fast, non-intrusive technique
    that measures the horizontal and vertical eye opening at the
    receiver's sampling point by scanning outward from the center
    until bit errors are detected in each direction (left, right,
    top-left, top-right, bottom-left, bottom-right).

    The typical workflow is:
    1. Call this endpoint to enable measurement on the target lane.
    2. Poll `crosshair_get` until the state transitions through the
       measurement phases and reaches "DONE" (state 21).
    3. Read the final eye margin limits from the response.
    4. Call `crosshair_disable` to release the measurement hardware.

    **lane_id** is the physical lane number (0-143). Only one lane can
    be measured at a time; enabling a new lane implicitly disables any
    prior measurement.

    Returns `{"status": "enabled"}` on success.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        diag.cross_hair_enable(lane_id)
        return {"status": "enabled"}
    except Exception as e:
        raise_on_error(e, "crosshair_enable")


@router.post(
    "/{device_id}/diag/crosshair/disable",
    responses={
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        502: {
            "description": "Hardware communication error while disabling "
            "cross-hair measurement.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while disabling cross-hair mode.",
        },
    },
)
def crosshair_disable(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Disable cross-hair eye margin measurement on the device.

    Stops any in-progress cross-hair measurement and releases the
    measurement hardware. This should be called after retrieving
    results from `crosshair_get` to return the receiver to normal
    operation.

    This is safe to call even if no measurement is currently active.

    Returns `{"status": "disabled"}` on success.
    """
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        diag.cross_hair_disable()
        return {"status": "disabled"}
    except Exception as e:
        raise_on_error(e, "crosshair_disable")


@router.get(
    "/{device_id}/diag/crosshair",
    response_model=list[CrossHairResult],
    responses={
        400: {
            "description": "Invalid start_lane or num_lanes values.",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        422: {
            "description": "start_lane + num_lanes exceeds the maximum of "
            "144 lanes.",
        },
        502: {
            "description": "Hardware communication error while reading "
            "cross-hair results.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period while reading cross-hair data.",
        },
    },
)
def crosshair_get(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    start_lane: int = Query(default=0, ge=0, le=143),
    num_lanes: int = Query(default=1, ge=1, le=64),
) -> list[CrossHairResult]:
    """Get cross-hair eye margin measurement results for one or more lanes.

    Reads the current cross-hair measurement state and results for a
    contiguous range of lanes. Poll this endpoint after calling
    `crosshair_enable` to track measurement progress and retrieve
    final eye margin values.

    **start_lane** (default 0) is the first lane number to query.

    **num_lanes** (default 1, max 64) is the number of consecutive
    lanes to read starting from start_lane. The sum of start_lane +
    num_lanes must not exceed 144.

    Each element in the response list contains:
    - **lane_id**: The physical lane number.
    - **state**: Numeric measurement state code from
      DiagCrossHairState. Key values: 0 = DISABLED (no measurement
      active), 2 = WAITING (measurement queued), 3-20 = intermediate
      measurement phases scanning in each direction, 21 = DONE
      (measurement complete, results valid), 22 = ERROR (measurement
      failed).
    - **state_name**: Human-readable state name (e.g., "DONE",
      "FIRST_ERROR_RIGHT", "ERROR").
    - **eye_left_lim**: Horizontal eye opening to the left of the
      sampling point, in firmware timing units. Larger values indicate
      more timing margin.
    - **eye_right_lim**: Horizontal eye opening to the right of the
      sampling point.
    - **eye_bot_left_lim**: Vertical eye opening below and to the left
      of center.
    - **eye_bot_right_lim**: Vertical eye opening below and to the
      right of center.
    - **eye_top_left_lim**: Vertical eye opening above and to the left
      of center.
    - **eye_top_right_lim**: Vertical eye opening above and to the
      right of center.

    All limit values are zero until the corresponding measurement
    phase has completed. Once state reaches DONE, all six limit
    fields contain valid margin data.
    """
    dev = get_device(device_id)
    if start_lane + num_lanes > 144:
        raise HTTPException(
            status_code=422,
            detail="start_lane + num_lanes must not exceed 144",
        )
    try:
        diag = dev.diagnostics
        return diag.cross_hair_get(start_lane, num_lanes)
    except Exception as e:
        raise_on_error(e, "crosshair_get")


# --- AER Event Generation ---------------------------------------------------


class AerEventGenRequest(BaseModel):
    error_id: int = Field(ge=0, le=0xFFFF)
    trigger: int = Field(default=0, ge=0, le=0xFFFF)


@router.post(
    "/{device_id}/diag/aer-gen/{port_id}",
    responses={
        400: {
            "description": "Invalid port_id (must be 0-59), error_id "
            "(must be 0-0xFFFF), or trigger (must be 0-0xFFFF).",
        },
        404: {
            "description": "The specified device_id was not found in the "
            "device registry.",
        },
        429: {
            "description": "Rate limit exceeded. AER generation endpoints "
            "are limited to 10 calls per 60-second window per device.",
        },
        502: {
            "description": "Hardware communication error while generating "
            "the AER event.",
        },
        504: {
            "description": "The device did not respond within the timeout "
            "period during AER event generation.",
        },
    },
)
def aer_event_gen(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: AerEventGenRequest = ...,
) -> dict[str, str]:
    """Generate a synthetic Advanced Error Reporting (AER) event on a port.

    Triggers an AER error event on the specified port, causing the
    switch to report the error to the host OS via the PCIe AER
    capability. This is used to test host-side AER handling, error
    logging infrastructure, and recovery procedures without requiring
    an actual hardware error condition.

    **port_id** is the physical port number (0-59).

    **error_id** is a 16-bit error identifier (0-0xFFFF) that selects
    which AER error type to generate. Common PCIe AER error bit
    positions include: correctable errors (receiver error, bad TLP,
    bad DLLP, replay timer timeout, replay num rollover) and
    uncorrectable errors (data link protocol error, surprise down,
    poisoned TLP, completion timeout, unexpected completion, malformed
    TLP). Refer to the PCIe specification AER capability registers for
    the full mapping.

    **trigger** (default 0) is an optional 16-bit trigger parameter
    that provides additional context for the error event. The
    interpretation depends on the error_id.

    This endpoint is rate-limited to 10 calls per 60-second window per
    device.

    Returns `{"status": "generated"}` on success.

    **Warning**: AER events are visible to the host OS and may trigger
    error recovery actions including function-level reset, link
    re-training, or device removal depending on the OS AER policy.
    Use only in controlled test environments.
    """
    injection_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        diag = dev.diagnostics
        diag.aer_event_gen(port_id, request.error_id, request.trigger)
        return {"status": "generated"}
    except Exception as e:
        raise_on_error(e, "aer_event_gen")
