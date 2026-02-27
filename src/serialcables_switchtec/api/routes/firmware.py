"""Firmware management API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.state import get_device_registry
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.firmware import FirmwareManager
from serialcables_switchtec.models.firmware import FwPartSummary

router = APIRouter()

_DEVICE_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"


def _get_dev(device_id: str) -> SwitchtecDevice:
    """Look up a device from the registry or raise 404."""
    registry = get_device_registry()
    entry = registry.get(device_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Device {device_id} not found"
        )
    dev, _path = entry
    return dev


class TogglePartitionRequest(BaseModel):
    toggle_bl2: bool = False
    toggle_key: bool = False
    toggle_fw: bool = True
    toggle_cfg: bool = True
    toggle_riotcore: bool = False


class SetBootRoRequest(BaseModel):
    read_only: bool = True


@router.get("/{device_id}/firmware/version")
def get_fw_version(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Get the current firmware version string."""
    dev = _get_dev(device_id)
    try:
        mgr = FirmwareManager(dev)
        version = mgr.get_fw_version()
        return {"version": version}
    except Exception as e:
        raise_on_error(e, "get_fw_version")


@router.post("/{device_id}/firmware/toggle")
def toggle_active_partition(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
    request: TogglePartitionRequest = ...,
) -> dict[str, str]:
    """Toggle the active firmware partition."""
    dev = _get_dev(device_id)
    try:
        mgr = FirmwareManager(dev)
        mgr.toggle_active_partition(
            toggle_bl2=request.toggle_bl2,
            toggle_key=request.toggle_key,
            toggle_fw=request.toggle_fw,
            toggle_cfg=request.toggle_cfg,
            toggle_riotcore=request.toggle_riotcore,
        )
        return {"status": "toggled"}
    except Exception as e:
        raise_on_error(e, "toggle_active_partition")


@router.get("/{device_id}/firmware/boot-ro")
def get_boot_ro(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
) -> dict[str, bool]:
    """Check if boot partition is read-only."""
    dev = _get_dev(device_id)
    try:
        mgr = FirmwareManager(dev)
        ro = mgr.is_boot_ro()
        return {"read_only": ro}
    except Exception as e:
        raise_on_error(e, "get_boot_ro")


@router.post("/{device_id}/firmware/boot-ro")
def set_boot_ro(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
    request: SetBootRoRequest = ...,
) -> dict[str, str]:
    """Set boot partition read-only flag."""
    dev = _get_dev(device_id)
    try:
        mgr = FirmwareManager(dev)
        mgr.set_boot_ro(read_only=request.read_only)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "set_boot_ro")


@router.get(
    "/{device_id}/firmware/summary",
    response_model=FwPartSummary,
)
def get_fw_summary(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
) -> FwPartSummary:
    """Get a summary of all firmware partitions."""
    dev = _get_dev(device_id)
    try:
        mgr = FirmwareManager(dev)
        return mgr.get_part_summary()
    except Exception as e:
        raise_on_error(e, "get_fw_summary")
