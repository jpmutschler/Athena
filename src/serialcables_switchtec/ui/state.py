"""Shared UI state: active device tracking and data access.

NOTE: Single-device global state. This module assumes a single operator.
All browser sessions share the same device connection. If multi-user
support is needed, migrate to NiceGUI's app.storage.user or per-session state.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice
    from serialcables_switchtec.models.device import (
        DeviceInfo,
        DeviceSummary,
        PortStatus,
    )

logger = get_logger(__name__)

_active_device: SwitchtecDevice | None = None
_active_path: str = ""
_cached_summary: DeviceSummary | None = None
_state_lock = threading.Lock()


def connect_device(path: str) -> DeviceSummary:
    """Open a device and set it as the active device.

    Device open and summary are performed outside the lock to avoid
    blocking reads during slow I/O. Only the reference swap is locked.

    Args:
        path: Device path (e.g., "/dev/switchtec0").

    Returns:
        DeviceSummary for the newly connected device.

    Raises:
        SwitchtecError: If the device cannot be opened.
    """
    global _active_device, _active_path, _cached_summary
    from serialcables_switchtec.core.device import SwitchtecDevice

    # Open new device OUTSIDE the lock (I/O operation)
    new_dev = SwitchtecDevice.open(path)
    try:
        summary = new_dev.get_summary()
    except Exception:
        new_dev.close()
        raise

    # Swap references UNDER the lock (fast)
    with _state_lock:
        old_dev = _active_device
        _active_device = new_dev
        _active_path = path
        _cached_summary = summary

    # Close old device OUTSIDE the lock
    if old_dev is not None:
        try:
            old_dev.close()
        except Exception:
            logger.warning("device_close_failed", exc_info=True)

    logger.info("ui_device_connected", path=path)
    return summary


def disconnect_device() -> None:
    """Close the active device connection."""
    global _active_device, _active_path, _cached_summary
    with _state_lock:
        old_dev = _active_device
        _active_device = None
        _active_path = ""
        _cached_summary = None

    if old_dev is not None:
        try:
            old_dev.close()
        except Exception:
            logger.warning("device_close_failed", exc_info=True)
        logger.info("ui_device_disconnected")


def get_active_device() -> SwitchtecDevice | None:
    """Return the active device, or None if not connected."""
    with _state_lock:
        return _active_device


def get_active_path() -> str:
    """Return the path of the active device."""
    with _state_lock:
        return _active_path


def is_connected() -> bool:
    """Check if a device is currently connected."""
    with _state_lock:
        return _active_device is not None


def get_summary() -> DeviceSummary | None:
    """Get the cached device summary. Fast (no I/O)."""
    with _state_lock:
        return _cached_summary


def refresh_summary() -> DeviceSummary | None:
    """Re-read the device summary from hardware and update the cache."""
    global _cached_summary
    with _state_lock:
        dev = _active_device
    if dev is None:
        return None
    try:
        summary = dev.get_summary()
        with _state_lock:
            _cached_summary = summary
        return summary
    except SwitchtecError:
        logger.exception("summary_refresh_failed")
        return None


def get_port_status() -> list[PortStatus]:
    """Get port status from the active device."""
    with _state_lock:
        dev = _active_device
    if dev is None:
        return []
    try:
        return dev.get_status()
    except SwitchtecError:
        logger.exception("port_status_failed")
        return []


def scan_devices() -> list[DeviceInfo]:
    """Scan for available Switchtec devices."""
    from serialcables_switchtec.core.device import SwitchtecDevice

    try:
        return SwitchtecDevice.list_devices()
    except SwitchtecError:
        logger.exception("device_scan_failed")
        return []
