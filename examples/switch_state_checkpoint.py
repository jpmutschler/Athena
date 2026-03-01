#!/usr/bin/env python3
"""Capture complete switch state to JSON, or diff two checkpoints.

In capture mode, reads all available switch state (summary, ports,
firmware, EQ, fabric, bandwidth) into a versioned JSON checkpoint file.

In diff mode, loads two checkpoint files and prints a structured
comparison highlighting changes in link state, temperatures,
equalization, and firmware.

Usage:
    python switch_state_checkpoint.py --device /dev/switchtec0 --output ./results
    python switch_state_checkpoint.py --diff checkpoint_A.json checkpoint_B.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError

SCHEMA_VERSION = 1
TEMP_DELTA_THRESHOLD = 5.0
EQ_CURSOR_DELTA_THRESHOLD = 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture switch state checkpoint or diff two checkpoints."
    )
    parser.add_argument("--device", "-d", default="/dev/switchtec0", help="Device path")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("FILE1", "FILE2"),
        help="Diff two checkpoint JSON files (no device needed)",
    )
    return parser.parse_args()


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _rate_str(rate: int) -> str:
    rate_map = {
        1: "2.5 GT/s",
        2: "5 GT/s",
        3: "8 GT/s",
        4: "16 GT/s",
        5: "32 GT/s",
        6: "64 GT/s",
    }
    return rate_map.get(rate, str(rate))


# ── Capture mode ───────────────────────────────────────────────────────


def _capture_device_info(dev: SwitchtecDevice) -> dict:
    _log("Reading device summary...")
    summary = dev.get_summary()
    return {
        "name": summary.name,
        "device_id": summary.device_id,
        "generation": summary.generation,
        "variant": summary.variant,
        "boot_phase": summary.boot_phase,
        "fw_version": summary.fw_version,
        "die_temperature": summary.die_temperature,
        "port_count": summary.port_count,
    }


def _capture_temperatures(dev: SwitchtecDevice) -> list[float]:
    _log("Reading die temperatures...")
    try:
        return dev.get_die_temperatures(5)
    except SwitchtecError as exc:
        _log(f"  WARNING: temperature read failed: {exc}")
        return []


def _capture_firmware(dev: SwitchtecDevice) -> dict:
    _log("Reading firmware info...")
    fw_version = dev.firmware.get_fw_version()
    boot_ro = dev.firmware.is_boot_ro()

    partitions: dict[str, dict] = {}
    try:
        part_summary = dev.firmware.get_part_summary()
        for name in ("boot", "img", "cfg", "map", "nvlog", "key", "bl2", "riot"):
            part_info = getattr(part_summary, name, None)
            if part_info is None:
                continue
            entry: dict = {}
            for slot in ("active", "inactive"):
                img = getattr(part_info, slot, None)
                if img is not None:
                    entry[slot] = {
                        "version": img.version,
                        "valid": img.valid,
                        "active": img.active,
                        "running": img.running,
                        "read_only": img.read_only,
                    }
            if entry:
                partitions[name] = entry
    except SwitchtecError as exc:
        _log(f"  WARNING: partition summary read failed: {exc}")

    return {
        "version": fw_version,
        "boot_ro": boot_ro,
        "partitions": partitions,
    }


def _capture_ports(dev: SwitchtecDevice) -> list[dict]:
    _log("Reading port status...")
    statuses = dev.get_status()
    return [
        {
            "phys_id": s.port.phys_id,
            "link_up": s.link_up,
            "link_rate": s.link_rate,
            "link_rate_str": _rate_str(s.link_rate) if s.link_up else "",
            "cfg_lnk_width": s.cfg_lnk_width,
            "neg_lnk_width": s.neg_lnk_width,
            "ltssm": s.ltssm,
            "ltssm_str": s.ltssm_str,
            "pci_bdf": s.pci_bdf or "",
            "first_act_lane": s.first_act_lane,
        }
        for s in statuses
    ]


def _capture_equalization(dev: SwitchtecDevice, ports: list[dict]) -> dict[str, dict]:
    eq_data: dict[str, dict] = {}
    active_ports = [p for p in ports if p["link_up"]]
    for idx, p in enumerate(active_ports):
        port_id = p["phys_id"]
        _log(f"Reading EQ for port {port_id} ({idx + 1}/{len(active_ports)})...")
        entry: dict = {}

        try:
            coeff = dev.diagnostics.port_eq_tx_coeff(port_id)
            entry["cursors"] = [
                {"lane": i, "pre": c.pre, "post": c.post} for i, c in enumerate(coeff.cursors)
            ]
        except SwitchtecError as exc:
            _log(f"  WARNING: EQ coeff failed on port {port_id}: {exc}")
            entry["cursors"] = []

        try:
            fslf = dev.diagnostics.port_eq_tx_fslf(port_id, lane_id=0)
            entry["fslf"] = {"fs": fslf.fs, "lf": fslf.lf}
        except SwitchtecError as exc:
            _log(f"  WARNING: FS/LF failed on port {port_id}: {exc}")
            entry["fslf"] = None

        eq_data[f"port_{port_id}"] = entry
    return eq_data


def _capture_fabric(dev: SwitchtecDevice, ports: list[dict]) -> dict[str, dict]:
    _log("Reading fabric port configs...")
    fabric_data: dict[str, dict] = {}
    for p in ports:
        port_id = p["phys_id"]
        try:
            config = dev.fabric.get_port_config(port_id)
            fabric_data[f"port_{port_id}"] = {
                "port_type": config.port_type,
                "clock_source": config.clock_source,
                "clock_sris": config.clock_sris,
                "hvd_inst": config.hvd_inst,
            }
        except SwitchtecError:
            pass
    return fabric_data


def _capture_bandwidth(dev: SwitchtecDevice, ports: list[dict]) -> dict[str, dict]:
    active_ids = [p["phys_id"] for p in ports if p["link_up"]]
    if not active_ids:
        return {}
    _log(f"Reading bandwidth counters for {len(active_ids)} active ports...")
    bw_data: dict[str, dict] = {}
    try:
        results = dev.performance.bw_get(active_ids, clear=False)
        for port_id, bw in zip(active_ids, results):
            bw_data[f"port_{port_id}"] = {
                "time_us": bw.time_us,
                "egress_total": bw.egress.total,
                "egress_posted": bw.egress.posted,
                "egress_comp": bw.egress.comp,
                "egress_nonposted": bw.egress.nonposted,
                "ingress_total": bw.ingress.total,
                "ingress_posted": bw.ingress.posted,
                "ingress_comp": bw.ingress.comp,
                "ingress_nonposted": bw.ingress.nonposted,
            }
    except SwitchtecError as exc:
        _log(f"  WARNING: bandwidth read failed: {exc}")
    return bw_data


def _do_capture(dev: SwitchtecDevice, output_dir: Path) -> None:
    device_info = _capture_device_info(dev)
    temperatures = _capture_temperatures(dev)
    firmware = _capture_firmware(dev)
    ports = _capture_ports(dev)
    eq_data = _capture_equalization(dev, ports)
    fabric = _capture_fabric(dev, ports)
    bandwidth = _capture_bandwidth(dev, ports)

    checkpoint = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "device": device_info,
        "temperatures": temperatures,
        "firmware": firmware,
        "ports": ports,
        "equalization": eq_data,
        "fabric": fabric,
        "bandwidth": bandwidth,
    }

    filename = datetime.now().strftime("checkpoint_%Y%m%d_%H%M%S.json")
    filepath = output_dir / filename
    filepath.write_text(
        json.dumps(checkpoint, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    up_count = sum(1 for p in ports if p["link_up"])
    print(f"\n{'=' * 56}")
    print(f"  CHECKPOINT CAPTURED: {device_info['name']}")
    print(f"  {device_info['generation']} {device_info['variant']}  FW {device_info['fw_version']}")
    print(f"  Ports: {len(ports)} total, {up_count} UP")
    print(f"  EQ data: {len(eq_data)} ports")
    print(f"  Fabric data: {len(fabric)} ports")
    print(f"  Bandwidth data: {len(bandwidth)} ports")
    print(f"  File: {filepath}")
    print(f"{'=' * 56}\n")


# ── Diff mode ──────────────────────────────────────────────────────────


def _load_checkpoint(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _diff_section_header(title: str) -> None:
    print(f"\n--- {title} {'─' * (50 - len(title))}")


def _diff_device(a: dict, b: dict) -> int:
    _diff_section_header("Device")
    changes = 0
    dev_a = a.get("device", {})
    dev_b = b.get("device", {})
    for key in ("name", "generation", "variant", "fw_version", "boot_phase"):
        val_a = dev_a.get(key, "")
        val_b = dev_b.get(key, "")
        if val_a != val_b:
            print(f"  CHANGED  {key}: {val_a!r} -> {val_b!r}")
            changes += 1
    if changes == 0:
        print("  No changes.")
    return changes


def _diff_temperatures(a: dict, b: dict) -> int:
    _diff_section_header("Temperatures")
    temps_a = a.get("temperatures", [])
    temps_b = b.get("temperatures", [])
    changes = 0
    max_len = max(len(temps_a), len(temps_b))
    if max_len == 0:
        print("  No temperature data in either checkpoint.")
        return 0
    for i in range(max_len):
        ta = temps_a[i] if i < len(temps_a) else None
        tb = temps_b[i] if i < len(temps_b) else None
        if ta is None or tb is None:
            print(f"  Sensor {i}: {ta} -> {tb}  (sensor count changed)")
            changes += 1
        else:
            delta = abs(tb - ta)
            if delta > TEMP_DELTA_THRESHOLD:
                print(f"  ALERT  Sensor {i}: {ta:.1f} C -> {tb:.1f} C  (delta: {delta:+.1f} C)")
                changes += 1
            else:
                print(f"         Sensor {i}: {ta:.1f} C -> {tb:.1f} C  (delta: {tb - ta:+.1f} C)")
    if changes == 0:
        print("  All sensors within threshold.")
    return changes


def _diff_ports(a: dict, b: dict) -> int:
    _diff_section_header("Ports")
    ports_a = {p["phys_id"]: p for p in a.get("ports", [])}
    ports_b = {p["phys_id"]: p for p in b.get("ports", [])}
    all_ids = sorted(set(ports_a) | set(ports_b))
    changes = 0

    header = (
        f"  {'Port':>6}  {'A Link':>7}  {'B Link':>7}  "
        f"{'A Rate':>10}  {'B Rate':>10}  "
        f"{'A Width':>7}  {'B Width':>7}  {'Status':>8}"
    )
    print(header)
    print(f"  {'-' * (len(header) - 2)}")

    for pid in all_ids:
        pa = ports_a.get(pid)
        pb = ports_b.get(pid)
        if pa is None:
            print(
                f"  {pid:>6}  {'---':>7}  {'UP' if pb and pb['link_up'] else 'DOWN':>7}  "
                f"{'':>10}  {'':>10}  {'':>7}  {'':>7}  {'NEW':>8}"
            )
            changes += 1
            continue
        if pb is None:
            print(
                f"  {pid:>6}  {'UP' if pa['link_up'] else 'DOWN':>7}  {'---':>7}  "
                f"{'':>10}  {'':>10}  {'':>7}  {'':>7}  {'REMOVED':>8}"
            )
            changes += 1
            continue

        link_a = "UP" if pa["link_up"] else "DOWN"
        link_b = "UP" if pb["link_up"] else "DOWN"
        rate_a = pa.get("link_rate_str", str(pa.get("link_rate", "")))
        rate_b = pb.get("link_rate_str", str(pb.get("link_rate", "")))
        width_a = f"x{pa['neg_lnk_width']}" if pa["link_up"] else "-"
        width_b = f"x{pb['neg_lnk_width']}" if pb["link_up"] else "-"

        changed = (
            pa["link_up"] != pb["link_up"]
            or pa.get("link_rate") != pb.get("link_rate")
            or pa.get("neg_lnk_width") != pb.get("neg_lnk_width")
        )
        status = "CHANGED" if changed else ""
        if changed:
            changes += 1

        print(
            f"  {pid:>6}  {link_a:>7}  {link_b:>7}  "
            f"{rate_a:>10}  {rate_b:>10}  "
            f"{width_a:>7}  {width_b:>7}  {status:>8}"
        )

    if changes == 0:
        print("  No port changes detected.")
    return changes


def _diff_equalization(a: dict, b: dict) -> int:
    _diff_section_header("Equalization")
    eq_a = a.get("equalization", {})
    eq_b = b.get("equalization", {})
    all_keys = sorted(set(eq_a) | set(eq_b))
    changes = 0

    if not all_keys:
        print("  No equalization data in either checkpoint.")
        return 0

    for key in all_keys:
        entry_a = eq_a.get(key, {})
        entry_b = eq_b.get(key, {})
        cursors_a = entry_a.get("cursors", [])
        cursors_b = entry_b.get("cursors", [])

        max_lanes = max(len(cursors_a), len(cursors_b))
        for lane_idx in range(max_lanes):
            ca = cursors_a[lane_idx] if lane_idx < len(cursors_a) else None
            cb = cursors_b[lane_idx] if lane_idx < len(cursors_b) else None
            if ca is None or cb is None:
                print(f"  {key} lane {lane_idx}: cursor count changed")
                changes += 1
                continue

            pre_delta = abs(cb["pre"] - ca["pre"])
            post_delta = abs(cb["post"] - ca["post"])
            if pre_delta > EQ_CURSOR_DELTA_THRESHOLD or post_delta > EQ_CURSOR_DELTA_THRESHOLD:
                print(
                    f"  CHANGED  {key} lane {lane_idx}: "
                    f"pre {ca['pre']}->{cb['pre']}  "
                    f"post {ca['post']}->{cb['post']}"
                )
                changes += 1

        fslf_a = entry_a.get("fslf")
        fslf_b = entry_b.get("fslf")
        if fslf_a != fslf_b:
            print(f"  CHANGED  {key} FS/LF: {fslf_a} -> {fslf_b}")
            changes += 1

    if changes == 0:
        print("  No EQ changes beyond threshold.")
    return changes


def _diff_firmware(a: dict, b: dict) -> int:
    _diff_section_header("Firmware")
    fw_a = a.get("firmware", {})
    fw_b = b.get("firmware", {})
    changes = 0

    for key in ("version", "boot_ro"):
        va = fw_a.get(key)
        vb = fw_b.get(key)
        if va != vb:
            print(f"  CHANGED  {key}: {va!r} -> {vb!r}")
            changes += 1

    parts_a = fw_a.get("partitions", {})
    parts_b = fw_b.get("partitions", {})
    all_parts = sorted(set(parts_a) | set(parts_b))
    for part_name in all_parts:
        pa = parts_a.get(part_name, {})
        pb = parts_b.get(part_name, {})
        if pa != pb:
            print(f"  CHANGED  partition '{part_name}'")
            for slot in ("active", "inactive"):
                sa = pa.get(slot, {})
                sb = pb.get(slot, {})
                if sa != sb:
                    ver_a = sa.get("version", "N/A")
                    ver_b = sb.get("version", "N/A")
                    print(f"           {slot}: version {ver_a} -> {ver_b}")
            changes += 1

    if changes == 0:
        print("  No firmware changes.")
    return changes


def _do_diff(file1: Path, file2: Path) -> None:
    _log(f"Loading checkpoint A: {file1}")
    cp_a = _load_checkpoint(file1)
    _log(f"Loading checkpoint B: {file2}")
    cp_b = _load_checkpoint(file2)

    ts_a = cp_a.get("timestamp", "unknown")
    ts_b = cp_b.get("timestamp", "unknown")
    name_a = cp_a.get("device", {}).get("name", "unknown")
    name_b = cp_b.get("device", {}).get("name", "unknown")

    print(f"\n{'=' * 60}")
    print("  CHECKPOINT DIFF")
    print(f"  A: {file1.name}  ({name_a}, {ts_a})")
    print(f"  B: {file2.name}  ({name_b}, {ts_b})")
    print(f"{'=' * 60}")

    total_changes = 0
    total_changes += _diff_device(cp_a, cp_b)
    total_changes += _diff_temperatures(cp_a, cp_b)
    total_changes += _diff_firmware(cp_a, cp_b)
    total_changes += _diff_ports(cp_a, cp_b)
    total_changes += _diff_equalization(cp_a, cp_b)

    print(f"\n{'=' * 60}")
    if total_changes > 0:
        print(f"  {total_changes} difference(s) detected.")
    else:
        print("  Checkpoints are identical.")
    print(f"{'=' * 60}\n")


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    if args.diff:
        file1 = Path(args.diff[0])
        file2 = Path(args.diff[1])
        for f in (file1, file2):
            if not f.exists():
                _log(f"ERROR: File not found: {f}")
                sys.exit(2)
        try:
            _do_diff(file1, file2)
        except KeyboardInterrupt:
            _log("\nInterrupted by user.")
            sys.exit(130)
        return

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        _do_capture(dev, output_dir)
    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
