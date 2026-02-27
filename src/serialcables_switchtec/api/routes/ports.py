"""Port status API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.device import PortStatus

router = APIRouter()


@router.get("/{device_id}/ports", response_model=list[PortStatus])
async def get_ports(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> list[PortStatus]:
    """Get status of all ports for an open device."""
    dev = get_device(device_id)
    try:
        return dev.get_status()
    except Exception as e:
        raise_on_error(e, "get_ports")


@router.get("/{device_id}/ports/{phys_port_id}/pff")
async def get_port_pff(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    phys_port_id: int = Path(ge=0, le=59),
) -> dict[str, int]:
    """Get PFF index for a port."""
    dev = get_device(device_id)
    try:
        pff = dev.port_to_pff(dev.partition, phys_port_id)
        return {"phys_port_id": phys_port_id, "pff": pff}
    except Exception as e:
        raise_on_error(e, "get_port_pff")
