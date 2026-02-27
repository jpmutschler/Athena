"""Device management API routes."""

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
    """List all currently open devices."""
    registry = get_device_registry()
    return [
        DeviceEntry(id=dev_id, path=path, name=dev.name)
        for dev_id, (dev, path) in registry.items()
    ]


@router.get("/discover")
def discover_devices() -> list[dict]:
    """Discover available Switchtec devices on the system."""
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
    """Open a Switchtec device and add it to the registry."""
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
    """Close an open device and remove it from the registry."""
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
    """Get summary information for an open device."""
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
    """Hard-reset the Switchtec device.

    WARNING: This resets the switch chip and all connected PCIe devices.
    The device handle becomes invalid and the device is removed from the registry.
    Requires ``confirm: true`` in the request body.
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
    """Get die temperature for an open device."""
    dev = get_device(device_id)
    try:
        return {"temperature_c": dev.die_temperature}
    except Exception as e:
        raise_on_error(e, "get_temperature")
