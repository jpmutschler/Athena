"""Port status API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.state import get_device_registry
from serialcables_switchtec.models.device import PortStatus

router = APIRouter()

_DEVICE_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"


def _get_dev(device_id: str):
    """Look up a device from the registry or raise 404."""
    from serialcables_switchtec.core.device import SwitchtecDevice

    registry = get_device_registry()
    entry = registry.get(device_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Device {device_id} not found"
        )
    dev, _path = entry
    return dev


@router.get("/{device_id}/ports", response_model=list[PortStatus])
async def get_ports(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
) -> list[PortStatus]:
    """Get status of all ports for an open device."""
    dev = _get_dev(device_id)
    try:
        return dev.get_status()
    except Exception as e:
        raise_on_error(e, "get_ports")


@router.get("/{device_id}/ports/{phys_port_id}/pff")
async def get_port_pff(
    device_id: str = Path(pattern=_DEVICE_ID_PATTERN),
    phys_port_id: int = Path(ge=0, le=59),
) -> dict[str, int]:
    """Get PFF index for a port."""
    dev = _get_dev(device_id)
    try:
        pff = dev.port_to_pff(dev.partition, phys_port_id)
        return {"phys_port_id": phys_port_id, "pff": pff}
    except Exception as e:
        raise_on_error(e, "get_port_pff")
