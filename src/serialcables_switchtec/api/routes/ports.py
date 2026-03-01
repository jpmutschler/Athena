"""Port status API routes.

Provides read-only access to the link status and configuration of every
physical port on a Switchtec PCIe switch.  Each port is identified by its
physical port ID (0-59) and belongs to a partition/stack hierarchy within
the switch.

The PFF (Port Function Framework) index is the internal identifier the
firmware uses to map a physical port to its function within a given
partition.  Many firmware MRPC commands require the PFF index rather than
the physical port ID.
"""

from __future__ import annotations

from fastapi import APIRouter, Path

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.device import PortStatus

router = APIRouter()


@router.get("/{device_id}/ports", response_model=list[PortStatus])
def get_ports(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> list[PortStatus]:
    """Retrieve link status for every port on the device.

    Returns a JSON array of ``PortStatus`` objects, one per physical port.
    Each entry contains:

    - ``port`` -- a ``PortId`` sub-object with ``partition``, ``stack``,
      ``upstream`` (bool), ``stk_id``, ``phys_id``, and ``log_id``.
    - ``cfg_lnk_width`` -- the configured (maximum) PCIe link width.
    - ``neg_lnk_width`` -- the negotiated (current) link width after
      training; 0 when the link is down.
    - ``link_up`` -- ``true`` if the link is in L0 (active) state.
    - ``link_rate`` -- negotiated link speed encoded as a Gen number
      (e.g. 4 for Gen4, 5 for Gen5).
    - ``ltssm`` / ``ltssm_str`` -- current LTSSM state as a numeric code
      and human-readable string (e.g. ``"L0"``).
    - ``lane_reversal`` / ``lane_reversal_str`` -- lane reversal status.
    - ``first_act_lane`` -- index of the first active lane.
    - ``pci_bdf`` -- PCI bus/device/function if enumerated, else ``null``.
    - ``pci_dev`` -- associated PCI device name if available.
    - ``vendor_id`` / ``device_id`` -- PCI IDs of the connected endpoint,
      ``null`` when no device is enumerated.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Error responses:

    - **404 Not Found** -- no device with this ``device_id`` exists.
    - **500 Internal Server Error** -- the firmware status query failed.
    """
    dev = get_device(device_id)
    try:
        return dev.get_status()
    except Exception as e:
        raise_on_error(e, "get_ports")


@router.get("/{device_id}/ports/{phys_port_id}/pff")
def get_port_pff(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    phys_port_id: int = Path(ge=0, le=59),
) -> dict[str, int]:
    """Resolve a physical port ID to its PFF (Port Function Framework) index.

    The PFF index is the firmware-internal identifier that maps a physical
    port within a specific partition to the function handle used by MRPC
    commands such as bandwidth counters, event counters, and latency
    measurement.

    The mapping is performed for the partition that the API is currently
    attached to (i.e. ``dev.partition``).

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.
    - ``phys_port_id`` -- physical port number (0-59).

    Response format::

        {"phys_port_id": 2, "pff": 5}

    Error responses:

    - **404 Not Found** -- no device with this ``device_id`` exists.
    - **422 Unprocessable Entity** -- ``phys_port_id`` is out of range.
    - **500 Internal Server Error** -- the PFF lookup failed (port may not
      belong to the current partition).
    """
    dev = get_device(device_id)
    try:
        pff = dev.port_to_pff(dev.partition, phys_port_id)
        return {"phys_port_id": phys_port_id, "pff": pff}
    except Exception as e:
        raise_on_error(e, "get_port_pff")
