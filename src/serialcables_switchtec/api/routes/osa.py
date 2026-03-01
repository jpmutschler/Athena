"""Ordered Set Analyzer (OSA) API routes.

The Ordered Set Analyzer is a hardware debug facility in Switchtec Gen4/Gen5
switches that captures PCIe Physical Layer ordered sets (OS) as they
traverse the link.  This is used for link training debug, LTSSM analysis,
equalization tuning, and protocol-level diagnostics.

Typical capture workflow:

1. **Configure** -- set up the type filter (``config-type``) or pattern
   match filter (``config-pattern``) to select which ordered sets to
   capture and on which lanes.
2. **Set capture parameters** -- use the ``capture`` endpoint to configure
   lane mask, direction, stop mode, snapshot mode, post-trigger depth,
   and OS type filter for the capture engine.
3. **Start** -- begin the capture with ``start``.
4. **Stop** -- stop the capture with ``stop`` (or wait for the stop
   condition configured in step 2).
5. **Read data** -- retrieve captured data per lane with ``data/{lane_id}``.
6. **Dump config** -- optionally read back the active configuration with
   ``dump-config``.

Each stack (0-7) has its own independent OSA engine.  Lane IDs range
from 0 to 143 (covering up to x16 ports across multiple stacks).
Direction is encoded as 0 for RX (ingress) and 1 for TX (egress).
Link rate values: 0=Gen1, 1=Gen2, 2=Gen3, 3=Gen4, 4=Gen5, 5=Gen6.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error

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
    """Start the OSA capture engine on the specified stack.

    The capture filter and parameters should be configured before calling
    this endpoint (via ``config-type``, ``config-pattern``, or ``capture``).
    Once started, the OSA engine records ordered sets that match the
    configured filter until stopped or the stop condition is met.

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": "started"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- stack_id out of range.
    - **500 Internal Server Error** -- OSA start command failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
        osa.start(stack_id)
        return {"status": "started"}
    except Exception as e:
        raise_on_error(e, "osa_start")


@router.post("/{device_id}/osa/{stack_id}/stop")
def osa_stop(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
) -> dict[str, str]:
    """Stop a running OSA capture on the specified stack.

    Halts the capture engine.  Captured data is retained in the hardware
    buffer and can be read with the ``data/{lane_id}`` endpoint.

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": "stopped"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- stack_id out of range.
    - **500 Internal Server Error** -- OSA stop command failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
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
    """Configure the OSA type-based filter for ordered set capture.

    Selects which ordered set types to capture based on a bitmask, the
    direction (RX or TX), lane selection, and the link rate to decode at.

    Request body fields:

    - ``direction`` -- ``0`` for RX (ingress), ``1`` for TX (egress).
    - ``lane_mask`` -- 32-bit bitmask selecting which lanes within the
      stack to monitor.
    - ``link_rate`` -- the PCIe generation to decode: 0=Gen1, 1=Gen2,
      2=Gen3, 3=Gen4, 4=Gen5, 5=Gen6.
    - ``os_types`` -- 32-bit bitmask selecting which ordered set types to
      capture (TS1, TS2, EIEOS, SKP, etc.).

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": "configured"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- configuration command failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
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
    """Configure the OSA pattern-match filter for ordered set capture.

    Instead of filtering by OS type, this endpoint allows capture of
    ordered sets whose data fields match a specific bit pattern with a
    configurable mask.  This is useful for isolating specific training
    sequences with known TS1/TS2 field values.

    Request body fields:

    - ``direction`` -- ``0`` for RX (ingress), ``1`` for TX (egress).
    - ``lane_mask`` -- 32-bit bitmask selecting which lanes to monitor.
    - ``link_rate`` -- PCIe generation: 0=Gen1 through 5=Gen6.
    - ``value_data`` -- list of exactly 4 integers defining the pattern
      to match against the ordered set data fields.
    - ``mask_data`` -- list of exactly 4 integers defining which bits of
      ``value_data`` are significant (1 = must match, 0 = don't care).

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": "configured"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range or wrong
      array length.
    - **500 Internal Server Error** -- configuration command failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
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
    """Configure the OSA capture engine parameters and arm the capture.

    This endpoint sets the capture mode, trigger conditions, and lane
    selection for the OSA engine on the specified stack.  The capture
    does not start recording until ``start`` is called.

    Request body fields:

    - ``lane_mask`` -- 32-bit bitmask selecting which lanes to capture.
    - ``direction`` -- ``0`` for RX (ingress), ``1`` for TX (egress).
    - ``drop_single_os`` -- ``1`` to drop isolated single ordered sets
      (noise filter), ``0`` to keep all.  Default ``0``.
    - ``stop_mode`` -- capture stop condition bitmask.  ``0`` means manual
      stop only (via the ``stop`` endpoint).  Default ``0``.
    - ``snapshot_mode`` -- snapshot trigger mode bitmask.  Default ``0``.
    - ``post_trigger`` -- number of ordered sets to capture after the
      trigger condition is met.  Default ``0``.
    - ``os_types`` -- additional OS type filter bitmask applied during
      capture.  Default ``0`` (accept all types matching the configured
      type or pattern filter).

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": "capture_started"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- capture control command failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
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
    """Read the captured ordered set data for a specific lane.

    Returns the raw capture buffer contents for the specified lane from the
    most recent capture session.  The capture should be stopped before
    reading data to ensure a consistent snapshot.

    Parameters:

    - ``device_id`` (path) -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).
    - ``lane_id`` (path) -- lane number within the stack (0-143).
    - ``direction`` (query) -- ``0`` for RX (ingress), ``1`` for TX
      (egress).  Default ``0``.

    Response format::

        {"status": 0, "result": <firmware-returned integer>}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- lane_id or stack_id out of range.
    - **500 Internal Server Error** -- capture data read failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
        result = osa.capture_data(stack_id, lane_id, direction)
        return {"status": 0, "result": result}
    except Exception as e:
        raise_on_error(e, "osa_capture_data")


@router.get("/{device_id}/osa/{stack_id}/dump-config")
def osa_dump_config(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
) -> dict[str, int]:
    """Read back the current OSA configuration for a stack.

    Returns the active filter and capture parameters that were set via
    ``config-type``, ``config-pattern``, and ``capture`` endpoints.  This
    is useful for verifying configuration before starting a capture or for
    diagnostic logging.

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` (path) -- stack index (0-7).

    Response format::

        {"status": 0, "result": <firmware-returned configuration integer>}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- stack_id out of range.
    - **500 Internal Server Error** -- configuration dump failed.
    """
    dev = get_device(device_id)
    try:
        osa = dev.osa
        result = osa.dump_config(stack_id)
        return {"status": 0, "result": result}
    except Exception as e:
        raise_on_error(e, "osa_dump_config")
