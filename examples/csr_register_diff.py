#!/usr/bin/env python3
"""Snapshot PCIe config space registers and diff two snapshots.

In snapshot mode, reads standard PCI configuration header registers from
an endpoint via the Switchtec fabric CSR read interface and saves them to
a timestamped JSON file.  In diff mode, compares two previously captured
snapshot files and displays changed registers.

Usage:
    python csr_register_diff.py --snapshot --device /dev/switchtec0 --pdfid 0 --output ./results
    python csr_register_diff.py --diff snapshot_A.json snapshot_B.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


# ── Standard PCI config register map (Type 0/1 header) ────────────────

STANDARD_REGISTERS: dict[int, tuple[str, int]] = {
    0x00: ("Vendor ID", 16),
    0x02: ("Device ID", 16),
    0x04: ("Command", 16),
    0x06: ("Status", 16),
    0x08: ("Revision ID", 8),
    0x09: ("Class Code", 8),
    0x0A: ("Subclass", 8),
    0x0B: ("Base Class", 8),
    0x0C: ("Cache Line Size", 8),
    0x0D: ("Latency Timer", 8),
    0x0E: ("Header Type", 8),
    0x0F: ("BIST", 8),
    0x10: ("BAR0", 32),
    0x14: ("BAR1", 32),
    0x18: ("BAR2", 32),
    0x1C: ("BAR3", 32),
    0x20: ("BAR4", 32),
    0x24: ("BAR5", 32),
    0x28: ("CardBus CIS Pointer", 32),
    0x2C: ("Subsystem Vendor ID", 16),
    0x2E: ("Subsystem ID", 16),
    0x30: ("Expansion ROM BAR", 32),
    0x34: ("Capabilities Pointer", 8),
    0x3C: ("Interrupt Line", 8),
    0x3D: ("Interrupt Pin", 8),
}

# Full header offsets at 32-bit granularity for raw dump (0x00 to 0x3C).
HEADER_DWORD_OFFSETS: list[int] = list(range(0x00, 0x40, 4))


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PCIe CSR register snapshot and diff tool."
    )
    parser.add_argument(
        "--device", "-d", default="/dev/switchtec0", help="Device path"
    )
    parser.add_argument(
        "--output", "-o", default=".", help="Output directory"
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Capture mode: read registers and save to JSON",
    )
    parser.add_argument(
        "--pdfid",
        type=int,
        default=0,
        help="Endpoint PDFID to read from (default: 0)",
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Diff mode: compare two snapshot JSON files",
    )
    return parser.parse_args()


# ── Helpers ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _hex_val(value: int, width: int) -> str:
    """Format value as hex string with appropriate width."""
    if width == 8:
        return f"0x{value:02X}"
    if width == 16:
        return f"0x{value:04X}"
    return f"0x{value:08X}"


def _addr_str(addr: int) -> str:
    return f"0x{addr:02X}"


# ── Snapshot mode ──────────────────────────────────────────────────────


def _read_named_registers(
    dev: SwitchtecDevice, pdfid: int
) -> dict[str, dict]:
    """Read all named standard registers.

    Returns dict keyed by hex offset string, each value containing
    name, width, value, and error status.
    """
    registers: dict[str, dict] = {}

    for addr in sorted(STANDARD_REGISTERS):
        name, width = STANDARD_REGISTERS[addr]
        key = _addr_str(addr)
        try:
            value = dev.fabric.csr_read(pdfid, addr, width)
            registers[key] = {
                "name": name,
                "width": width,
                "value": value,
                "error": None,
            }
        except SwitchtecError as exc:
            _log(f"  WARNING: Failed to read {name} at {key}: {exc}")
            registers[key] = {
                "name": name,
                "width": width,
                "value": None,
                "error": str(exc),
            }

    return registers


def _read_raw_header(
    dev: SwitchtecDevice, pdfid: int
) -> dict[str, int | None]:
    """Read full header at 32-bit granularity (0x00-0x3C).

    Returns dict keyed by hex offset string with 32-bit values.
    """
    raw: dict[str, int | None] = {}
    for offset in HEADER_DWORD_OFFSETS:
        key = _addr_str(offset)
        try:
            value = dev.fabric.csr_read(pdfid, offset, 32)
            raw[key] = value
        except SwitchtecError:
            raw[key] = None
    return raw


def _build_snapshot(
    dev: SwitchtecDevice, pdfid: int
) -> dict:
    """Build a complete snapshot dict."""
    _log("Reading device summary...")
    try:
        summary = dev.get_summary()
        device_info = {
            "name": summary.name,
            "device_id": summary.device_id,
            "generation": summary.generation,
            "variant": summary.variant,
            "fw_version": summary.fw_version,
        }
    except SwitchtecError as exc:
        _log(f"WARNING: Could not read device summary: {exc}")
        device_info = {}

    _log(f"Reading named registers (PDFID={pdfid})...")
    registers = _read_named_registers(dev, pdfid)

    _log("Reading raw header dwords...")
    raw_header = _read_raw_header(dev, pdfid)

    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "timestamp": timestamp,
        "device": device_info,
        "pdfid": pdfid,
        "registers": registers,
        "raw_header": raw_header,
    }


def _write_snapshot(snapshot: dict, filepath: Path) -> None:
    """Write snapshot dict to JSON file."""
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, default=str)


def _print_register_dump(snapshot: dict) -> None:
    """Print register dump table to terminal."""
    registers = snapshot["registers"]
    pdfid = snapshot["pdfid"]

    hdr = (
        f"{'Offset':>8}  {'Name':<22}  {'Width':>5}  {'Value':>12}"
    )
    sep = "-" * len(hdr)

    print(f"\nCSR Register Dump (PDFID={pdfid})")
    print(sep)
    print(hdr)
    print(sep)

    for addr_key in sorted(registers, key=lambda k: int(k, 16)):
        entry = registers[addr_key]
        name = entry["name"]
        width = entry["width"]
        if entry["value"] is not None:
            val_str = _hex_val(entry["value"], width)
        else:
            val_str = "ERROR"
        print(f"{addr_key:>8}  {name:<22}  {width:>5}  {val_str:>12}")

    print(sep)

    # Raw header
    raw = snapshot.get("raw_header", {})
    if raw:
        print("\nRaw Header Dwords:")
        line_parts: list[str] = []
        for offset in HEADER_DWORD_OFFSETS:
            key = _addr_str(offset)
            val = raw.get(key)
            if val is not None:
                line_parts.append(f"{key}={val:08X}")
            else:
                line_parts.append(f"{key}=????????")
            if len(line_parts) == 4:
                print(f"  {' '.join(line_parts)}")
                line_parts = []
        if line_parts:
            print(f"  {' '.join(line_parts)}")

    print()


# ── Diff mode ──────────────────────────────────────────────────────────


def _load_snapshot(filepath: Path) -> dict:
    """Load a snapshot JSON file."""
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def _diff_snapshots(snap1: dict, snap2: dict) -> list[dict]:
    """Compare two snapshots. Returns list of changed register dicts."""
    regs1 = snap1.get("registers", {})
    regs2 = snap2.get("registers", {})

    all_keys = sorted(
        set(regs1) | set(regs2),
        key=lambda k: int(k, 16),
    )

    changes: list[dict] = []
    for key in all_keys:
        entry1 = regs1.get(key, {})
        entry2 = regs2.get(key, {})

        val1 = entry1.get("value")
        val2 = entry2.get("value")

        if val1 == val2:
            continue

        name = entry1.get("name") or entry2.get("name") or "Unknown"
        width = entry1.get("width") or entry2.get("width") or 32

        changes.append({
            "offset": key,
            "name": name,
            "width": width,
            "before": val1,
            "after": val2,
        })

    return changes


def _print_diff(
    changes: list[dict],
    file1: str,
    file2: str,
) -> None:
    """Print diff table to terminal."""
    print("\nCSR Register Diff")
    print(f"File 1: {file1}")
    print(f"File 2: {file2}")

    if not changes:
        print("\nNo register changes detected.")
        print()
        return

    hdr = (
        f"{'Offset':>8} | {'Name':<22} | "
        f"{'Before':>12} | {'After':>12}"
    )
    sep = "-" * len(hdr)

    print(sep)
    print(hdr)
    print(sep)

    for c in changes:
        width = c["width"]
        if c["before"] is not None:
            before_str = _hex_val(c["before"], width)
        else:
            before_str = "N/A"
        if c["after"] is not None:
            after_str = _hex_val(c["after"], width)
        else:
            after_str = "N/A"

        print(
            f"{c['offset']:>8} | {c['name']:<22} | "
            f"{before_str:>12} | {after_str:>12}"
        )

    print(sep)
    print(f"\n{len(changes)} register(s) changed.")

    # Also diff raw header dwords
    # (shown as a supplementary section if any differ)
    print()


def _diff_raw_headers(snap1: dict, snap2: dict) -> None:
    """Print raw header dword differences if any."""
    raw1 = snap1.get("raw_header", {})
    raw2 = snap2.get("raw_header", {})

    all_offsets = sorted(
        set(raw1) | set(raw2),
        key=lambda k: int(k, 16),
    )

    diffs: list[tuple[str, int | None, int | None]] = []
    for key in all_offsets:
        v1 = raw1.get(key)
        v2 = raw2.get(key)
        if v1 != v2:
            diffs.append((key, v1, v2))

    if not diffs:
        return

    print("Raw Header Dword Changes:")
    for key, v1, v2 in diffs:
        s1 = f"{v1:08X}" if v1 is not None else "????????"
        s2 = f"{v2:08X}" if v2 is not None else "????????"
        print(f"  {key}: {s1} -> {s2}")
    print()


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    if not args.snapshot and not args.diff:
        _log("ERROR: Must specify either --snapshot or --diff mode.")
        _log("  --snapshot: Capture registers to JSON")
        _log("  --diff FILE1 FILE2: Compare two snapshots")
        sys.exit(2)

    if args.snapshot and args.diff:
        _log("ERROR: Cannot use --snapshot and --diff at the same time.")
        sys.exit(2)

    # ── Diff mode ──────────────────────────────────────────────────
    if args.diff:
        file1_path = Path(args.diff[0])
        file2_path = Path(args.diff[1])

        if not file1_path.exists():
            _log(f"ERROR: File not found: {file1_path}")
            sys.exit(2)
        if not file2_path.exists():
            _log(f"ERROR: File not found: {file2_path}")
            sys.exit(2)

        _log(f"Loading {file1_path}...")
        snap1 = _load_snapshot(file1_path)
        _log(f"Loading {file2_path}...")
        snap2 = _load_snapshot(file2_path)

        changes = _diff_snapshots(snap1, snap2)
        _print_diff(changes, str(file1_path), str(file2_path))
        _diff_raw_headers(snap1, snap2)
        return

    # ── Snapshot mode ──────────────────────────────────────────────
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        snapshot = _build_snapshot(dev, args.pdfid)

        _print_register_dump(snapshot)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"csr_snapshot_{timestamp}.json"
        filepath = output_dir / filename
        _write_snapshot(snapshot, filepath)
        _log(f"Snapshot written to {filepath}")

    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
