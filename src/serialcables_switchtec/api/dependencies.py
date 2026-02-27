"""Shared API dependencies: device lookup helper and constants."""

from __future__ import annotations

from fastapi import HTTPException

from serialcables_switchtec.api.state import get_device_registry
from serialcables_switchtec.core.device import SwitchtecDevice

DEVICE_ID_PATTERN = r"^[a-zA-Z0-9_-]{1,64}$"


def get_device(device_id: str) -> SwitchtecDevice:
    """Look up a device from the registry or raise 404.

    Args:
        device_id: Device identifier in the registry.

    Returns:
        The SwitchtecDevice instance.

    Raises:
        HTTPException: 404 if device not found.
    """
    registry = get_device_registry()
    entry = registry.get(device_id)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Device {device_id} not found"
        )
    dev, _path = entry
    return dev
