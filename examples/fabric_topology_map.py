#!/usr/bin/env python3
"""Discover and visualize full fabric topology as JSON and ASCII diagram.

Enumerates all ports on a Switchtec switch, queries fabric port
configuration where available, and outputs a structured JSON topology
file alongside an ASCII box diagram printed to the terminal.

The JSON output can be used as reference data for link_width_rate_audit.py
by converting the "ports" array to the expected topology format:
  jq '{expected: [.ports[] | {port_id: .phys_port_id, gen: .link_rate, width: .width}]}' topology.json

Usage:
    python fabric_topology_map.py --device /dev/switchtec0 --output ./results
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError

# Port type integer to string mapping.
# Values are based on common Switchtec fabric port type definitions.
_PORT_TYPE_MAP: dict[int, str] = {
    0: "USP",
    1: "DSP",
    2: "ISP",
    3: "FABRIC",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and map fabric topology (JSON + ASCII).")
    parser.add_argument("--device", "-d", default="/dev/switchtec0", help="Device path")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    return parser.parse_args()


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _rate_str(rate: int) -> str:
    rate_map = {
        1: "2.5GT/s",
        2: "5GT/s",
        3: "8GT/s",
        4: "16GT/s",
        5: "32GT/s",
        6: "64GT/s",
    }
    return rate_map.get(rate, str(rate))


def _port_type_str(port_type: int) -> str:
    return _PORT_TYPE_MAP.get(port_type, f"T{port_type}")


# ── Data collection ────────────────────────────────────────────────────


def _collect_switch_info(dev: SwitchtecDevice) -> dict:
    _log("Reading device summary...")
    summary = dev.get_summary()
    return {
        "name": summary.name,
        "generation": summary.generation,
        "variant": summary.variant,
        "fw_version": summary.fw_version,
        "die_temperature": summary.die_temperature,
        "device_id": summary.device_id,
        "port_count": summary.port_count,
    }


def _collect_ports(dev: SwitchtecDevice) -> list[dict]:
    _log("Reading port status...")
    statuses = dev.get_status()

    ports: list[dict] = []
    for idx, s in enumerate(statuses):
        phys_id = s.port.phys_id
        _log(f"  Port {phys_id} ({idx + 1}/{len(statuses)})...")

        # Try to read fabric port config
        port_type_str = "unknown"
        port_type_int: int | None = None
        try:
            fab_config = dev.fabric.get_port_config(phys_id)
            port_type_int = fab_config.port_type
            port_type_str = _port_type_str(fab_config.port_type)
        except SwitchtecError:
            # Non-fabric devices may not support this call
            pass

        port_entry: dict = {
            "phys_port_id": phys_id,
            "link_up": s.link_up,
            "link_rate": _rate_str(s.link_rate) if s.link_up else "",
            "width": s.neg_lnk_width if s.link_up else 0,
            "cfg_width": s.cfg_lnk_width,
            "port_type": port_type_str,
            "ltssm": s.ltssm_str,
            "pci_bdf": s.pci_bdf or "",
            "first_act_lane": s.first_act_lane,
        }
        if port_type_int is not None:
            port_entry["port_type_raw"] = port_type_int

        ports.append(port_entry)

    ports.sort(key=lambda p: p["phys_port_id"])
    return ports


# ── JSON output ────────────────────────────────────────────────────────


def _build_topology_json(switch_info: dict, ports: list[dict]) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "switch": {
            "name": switch_info["name"],
            "generation": switch_info["generation"],
            "variant": switch_info["variant"],
            "fw_version": switch_info["fw_version"],
            "device_id": switch_info["device_id"],
        },
        "timestamp": timestamp,
        "ports": ports,
    }


# ── ASCII diagram ──────────────────────────────────────────────────────

# Box-drawing characters
_TL = "\u250c"  # top-left
_TR = "\u2510"  # top-right
_BL = "\u2514"  # bottom-left
_BR = "\u2518"  # bottom-right
_H = "\u2500"  # horizontal
_V = "\u2502"  # vertical
_HJ = "\u251c"  # left-tee
_HR = "\u2524"  # right-tee
_DOT_FILLED = "\u25cf"  # filled circle (UP)
_DOT_EMPTY = "\u25cb"  # empty circle (DOWN)


def _print_ascii_diagram(switch_info: dict, ports: list[dict]) -> None:
    box_width = 42
    inner = box_width - 2

    # Header
    title = (
        f"Switchtec {switch_info['variant']} "
        f"{switch_info['generation']}  "
        f"(FW: {switch_info['fw_version']})"
    )
    temp_line = f"Temperature: {switch_info['die_temperature']:.1f} C"

    print(f"\n{_TL}{_H * inner}{_TR}")
    print(f"{_V}  {title:<{inner - 2}}{_V}")
    print(f"{_V}  {temp_line:<{inner - 2}}{_V}")
    print(f"{_HJ}{_H * inner}{_HR}")

    # Port lines
    for p in ports:
        port_id = p["phys_port_id"]
        ptype = p["port_type"].upper()
        ptype_tag = f"[{ptype}]" if ptype != "UNKNOWN" else "[---]"

        if p["link_up"]:
            dot = _DOT_FILLED
            status = "UP"
            rate = p["link_rate"]
            width = f"x{p['width']}"
            detail = f"{status}   {rate} {width}"
        else:
            dot = _DOT_EMPTY
            detail = "DOWN"

        line = f" Port {port_id:>2} {ptype_tag:<8} {dot} {detail}"
        print(f"{_V}{line:<{inner}}{_V}")

    print(f"{_BL}{_H * inner}{_BR}")

    # Summary
    up_count = sum(1 for p in ports if p["link_up"])
    down_count = len(ports) - up_count
    print(f"  {len(ports)} ports total: {up_count} UP, {down_count} DOWN\n")


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        switch_info = _collect_switch_info(dev)
        ports = _collect_ports(dev)
    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()

    topology = _build_topology_json(switch_info, ports)

    # Write JSON
    filename = datetime.now().strftime("topology_%Y%m%d_%H%M%S.json")
    filepath = output_dir / filename
    filepath.write_text(
        json.dumps(topology, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _log(f"Topology JSON written to {filepath}")

    # Print ASCII diagram to stdout
    _print_ascii_diagram(switch_info, ports)


if __name__ == "__main__":
    main()
