"""Device management API routes.

Provides lifecycle management for Switchtec PCIe switch devices.  Devices
must be explicitly opened via POST /{device_id}/open before any other
endpoint can interact with them.  The device registry is an in-memory
dictionary keyed by a caller-chosen ``device_id`` (alphanumeric, hyphens,
underscores, 1-64 characters matching ``^[a-zA-Z0-9_-]{1,64}$``).

Device paths are validated against the pattern
``/dev/switchtec\\d+`` (Linux), ``\\\\.\\switchtec\\d+`` (Windows), or a
bare numeric index before the device is opened.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field, field_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.rate_limit import hard_reset_limiter
from serialcables_switchtec.api.state import (
    DEVICE_PATH_PATTERN,
    get_device_registry,
    get_registry_lock,
)
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.models.device import DeviceSummary
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()



class OpenDeviceRequest(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def validate_device_path(cls, v: str) -> str:
        if not DEVICE_PATH_PATTERN.match(v):
            raise ValueError(f"Invalid device path format: {v}")
        return v


class DeviceEntry(BaseModel):
    id: str
    path: str
    name: str


@router.get("/", response_model=list[DeviceEntry])
def list_open_devices() -> list[DeviceEntry]:
    """List all currently open devices in the in-memory registry.

    Returns a JSON array of ``DeviceEntry`` objects, each containing the
    caller-assigned ``id``, the OS-level ``path`` that was used to open the
    device, and the human-readable ``name`` reported by the switch firmware.

    An empty array is returned when no devices have been opened.

    Response format::

        [
            {"id": "sw0", "path": "/dev/switchtec0", "name": "PSX 48XG3"}
        ]
    """
    registry = get_device_registry()
    return [
        DeviceEntry(id=dev_id, path=path, name=dev.name)
        for dev_id, (dev, path) in registry.items()
    ]


@router.get("/discover")
def discover_devices() -> list[dict]:
    """Discover available Switchtec devices visible to the host OS.

    Scans for all Switchtec devices accessible through the system driver and
    returns their metadata.  This does **not** open the devices or add them
    to the registry; use ``POST /{device_id}/open`` afterward.

    Each entry in the response array contains:

    - ``name`` -- driver-level device name.
    - ``description`` -- human-readable product description.
    - ``pci_dev`` -- PCI bus/device/function address (e.g. ``0000:03:00.0``).
    - ``product_id`` / ``product_rev`` -- Microchip product identifiers.
    - ``fw_version`` -- currently running firmware version string.
    - ``path`` -- OS path suitable for passing to the open endpoint.

    Raises 500 if the host driver is not loaded or device enumeration fails.
    """
    try:
        devices = SwitchtecDevice.list_devices()
        return [d.model_dump() for d in devices]
    except Exception as e:
        raise_on_error(e, "discover_devices")


@router.post(
    "/{device_id}/open",
    response_model=DeviceSummary,
)
def open_device(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: OpenDeviceRequest = ...,
) -> DeviceSummary:
    """Open a Switchtec device handle and register it under ``device_id``.

    The ``device_id`` path parameter is a caller-chosen identifier that will
    be used in all subsequent API calls to address this device.  It must
    match ``^[a-zA-Z0-9_-]{1,64}$``.

    The request body must contain a ``path`` field with the OS-level device
    path (e.g. ``/dev/switchtec0`` on Linux, ``\\\\.\\switchtec0`` on Windows,
    or a bare numeric index).

    On success the response is a ``DeviceSummary`` with fields including
    ``name``, ``generation``, ``variant``, ``fw_version``, ``die_temperature``,
    ``port_count``, and ``partition``.

    Error responses:

    - **409 Conflict** -- a device with this ``device_id`` is already open.
    - **422 Unprocessable Entity** -- the ``path`` does not match the
      allowed device-path pattern.
    - **500 Internal Server Error** -- the underlying C library failed to
      open the device (check that the path exists and the driver is loaded).
    """
    registry = get_device_registry()
    lock = get_registry_lock()

    with lock:
        if device_id in registry:
            raise HTTPException(
                status_code=409,
                detail="Device already open",
            )

        try:
            dev = SwitchtecDevice.open(request.path)
            registry[device_id] = (dev, request.path)
            return dev.get_summary()
        except Exception as e:
            raise_on_error(e, "open_device")


@router.delete("/{device_id}")
def close_device(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Close an open device handle and remove it from the registry.

    Releases the underlying OS file descriptor and removes the entry from
    the in-memory registry.  If the low-level close fails (e.g. the device
    was already physically removed), the registry entry is still removed
    and the error is logged server-side but **not** surfaced to the caller.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Response format::

        {"status": "closed", "device_id": "sw0"}

    Error responses:

    - **404 Not Found** -- no device with this ``device_id`` exists in the
      registry.
    """
    registry = get_device_registry()
    lock = get_registry_lock()

    with lock:
        entry = registry.pop(device_id, None)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail="Device not found",
            )

    dev, _path = entry
    try:
        dev.close()
    except Exception as e:
        logger.error(
            "device_close_failed", device_id=device_id, error=str(e)
        )
    return {"status": "closed", "device_id": device_id}


@router.get("/{device_id}", response_model=DeviceSummary)
def get_device_info(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> DeviceSummary:
    """Retrieve a ``DeviceSummary`` snapshot for an open device.

    The summary includes hardware identification (``name``, ``device_id``,
    ``generation``, ``variant``), firmware state (``fw_version``,
    ``boot_phase``), thermal data (``die_temperature`` in degrees Celsius),
    and topology metadata (``partition``, ``port_count``).

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Error responses:

    - **404 Not Found** -- no device with this ``device_id`` exists.
    - **500 Internal Server Error** -- the device handle is stale or the
      MRPC call to retrieve the summary failed.
    """
    dev = get_device(device_id)
    try:
        return dev.get_summary()
    except Exception as e:
        raise_on_error(e, "get_device_info")


class HardResetRequest(BaseModel):
    confirm: bool = Field(
        description="Must be true to confirm the hard reset operation.",
    )


@router.post("/{device_id}/hard-reset")
def hard_reset(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: HardResetRequest = ...,
) -> dict[str, str]:
    """Hard-reset the Switchtec switch chip.

    **WARNING:** This performs a full hardware reset of the switch ASIC and
    every PCIe endpoint behind it.  All in-flight TLPs are dropped, link
    training restarts on every port, and downstream devices will see a
    surprise-removal event.  The device handle becomes invalid and the
    device is automatically removed from the registry.

    The request body must contain ``confirm: true`` as a safety guard.
    Sending ``confirm: false`` (or omitting it) returns 400.

    Parameters:

    - ``device_id`` -- the identifier of the device to reset.
    - ``confirm`` (body) -- must be ``true`` to acknowledge the destructive
      operation.

    Rate limit: 1 call per device per 60 seconds.  Exceeding the limit
    returns 429.

    Response format::

        {"status": "reset", "device_id": "sw0"}

    Error responses:

    - **400 Bad Request** -- ``confirm`` is not ``true``.
    - **404 Not Found** -- no device with this ``device_id`` exists.
    - **429 Too Many Requests** -- rate limit exceeded for this device.
    - **500 Internal Server Error** -- the reset MRPC command failed.
    """
    hard_reset_limiter.check(device_id)

    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Hard reset requires confirm=true in request body",
        )

    registry = get_device_registry()
    lock = get_registry_lock()

    with lock:
        entry = registry.pop(device_id, None)
        if entry is None:
            raise HTTPException(
                status_code=404, detail="Device not found"
            )

    dev, _path = entry
    try:
        dev.hard_reset()
        return {"status": "reset", "device_id": device_id}
    except Exception as e:
        raise_on_error(e, "hard_reset")


@router.get("/{device_id}/temperature")
def get_temperature(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, float]:
    """Read the current die temperature of the switch ASIC.

    Returns the junction temperature in degrees Celsius as reported by the
    on-die thermal sensor.  This is a point-in-time reading; there is no
    averaging or hysteresis applied.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Response format::

        {"temperature_c": 42.5}

    Error responses:

    - **404 Not Found** -- no device with this ``device_id`` exists.
    - **500 Internal Server Error** -- temperature read failed.
    """
    dev = get_device(device_id)
    try:
        return {"temperature_c": dev.die_temperature}
    except Exception as e:
        raise_on_error(e, "get_temperature")
