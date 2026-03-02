"""PCIe extended capability enumeration.

Walks the linked list of extended capabilities starting at offset 0x100
in PCIe extended configuration space (0x100-0xFFF per ECAM, or up to
0xFFFF via Switchtec MRPC tunneled config access).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Well-known PCIe extended capability IDs (PCIe Base Spec 6.0, Table 7-100)
PCIE_EXT_CAP_IDS: dict[int, str] = {
    0x0001: "AER",
    0x0002: "VC (Virtual Channel)",
    0x0003: "Device Serial Number",
    0x0004: "Power Budgeting",
    0x0005: "Root Complex Link Declaration",
    0x0006: "Root Complex Internal Link Control",
    0x0007: "Root Complex Event Collector",
    0x0008: "MFVC",
    0x0009: "VC (MFVC)",
    0x000A: "RCRB Header",
    0x000B: "Vendor Specific",
    0x000C: "CAC",
    0x000D: "ACS",
    0x000E: "ARI",
    0x000F: "ATS",
    0x0010: "SR-IOV",
    0x0011: "MR-IOV",
    0x0012: "Multicast",
    0x0013: "Page Request",
    0x0015: "Resizable BAR",
    0x0016: "DPA",
    0x0017: "TPH Requester",
    0x0018: "LTR",
    0x0019: "Secondary PCIe Capability",
    0x001A: "PMUX",
    0x001B: "PASID",
    0x001C: "LN Requester",
    0x001D: "DPC",
    0x001E: "L1 PM Substates",
    0x001F: "Precision Time Measurement",
    0x0020: "PB3",
    0x0021: "VF Resizable BAR",
    0x0022: "DOE",
    0x0023: "Designated Vendor-Specific",
    0x0024: "Device 3 Extended",
    0x0025: "Data Link Feature",
    0x0026: "Physical Layer 16.0 GT/s",
    0x0027: "Lane Margining at Receiver",
    0x0028: "Hierarchy ID",
    0x0029: "NPEM",
    0x002A: "Physical Layer 32.0 GT/s",
    0x002B: "Alternate Protocol",
    0x002C: "SFI",
    0x002D: "IDE",
    0x002E: "Physical Layer 32.0 GT/s Margining",
    0x002F: "Shadow Functions",
    0x0030: "Physical Layer 64.0 GT/s",
    0x0031: "FLIT Logging",
    0x0032: "FLIT Performance",
    0x0033: "FLIT Error Injection",
}

_EXT_CAP_START = 0x100
_EXT_CAP_END = 0xFFC  # last valid DWORD-aligned offset in extended cap space
_MAX_CAPS = 256  # safety limit to avoid infinite loops


@dataclass(frozen=True)
class ExtCapEntry:
    """A discovered PCIe extended capability."""

    cap_id: int
    cap_name: str
    version: int
    offset: int


def walk_extended_caps(
    read_fn: Callable[[int], int],
) -> list[ExtCapEntry]:
    """Walk the extended capability linked list.

    Args:
        read_fn: A callable that reads a 32-bit value from a given config
            space offset.  Signature: ``read_fn(offset) -> int``.

    Returns:
        List of discovered extended capabilities in traversal order.
        Empty list if no capabilities are present (header reads as 0).
    """
    caps: list[ExtCapEntry] = []
    offset = _EXT_CAP_START
    visited: set[int] = set()

    for _ in range(_MAX_CAPS):
        if offset < _EXT_CAP_START or offset > _EXT_CAP_END:
            break
        if offset in visited:
            break  # circular linked list guard
        visited.add(offset)

        header = read_fn(offset)
        if header == 0 or header == 0xFFFFFFFF:
            break

        cap_id = header & 0xFFFF
        version = (header >> 16) & 0xF
        next_offset = (header >> 20) & 0xFFC

        cap_name = PCIE_EXT_CAP_IDS.get(cap_id, f"Unknown (0x{cap_id:04X})")
        caps.append(ExtCapEntry(
            cap_id=cap_id,
            cap_name=cap_name,
            version=version,
            offset=offset,
        ))

        if next_offset == 0:
            break
        offset = next_offset

    return caps
