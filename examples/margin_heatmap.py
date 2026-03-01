#!/usr/bin/env python3
"""Run cross-hair margin measurement on all lanes and produce an ASCII heatmap.

Measures horizontal and vertical eye margins for every lane on specified
(or all active) ports using the Switchtec cross-hair diagnostic.  Results
are written to a timestamped CSV and displayed as an ASCII heatmap in the
terminal with PASS/FAIL verdicts based on configurable thresholds.

Usage:
    python margin_heatmap.py --device /dev/switchtec0 --output ./results
    python margin_heatmap.py -d /dev/switchtec0 --ports 0,4,20 --h-warn 25
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross-hair margin measurement with ASCII heatmap."
    )
    parser.add_argument(
        "--device", "-d", default="/dev/switchtec0", help="Device path"
    )
    parser.add_argument(
        "--output", "-o", default=".", help="Output directory"
    )
    parser.add_argument(
        "--ports",
        default="auto",
        help="Comma-separated port IDs or 'auto' for all active (default: auto)",
    )
    parser.add_argument(
        "--h-warn",
        type=int,
        default=20,
        help="Horizontal margin warning threshold (default: 20)",
    )
    parser.add_argument(
        "--v-warn",
        type=int,
        default=30,
        help="Vertical margin warning threshold (default: 30)",
    )
    parser.add_argument(
        "--timeout-per-lane",
        type=float,
        default=15.0,
        help="Timeout in seconds per lane measurement (default: 15.0)",
    )
    return parser.parse_args()


# ── Helpers ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _verdict(value: int, threshold: int) -> str:
    return "PASS" if value >= threshold else "FAIL"


# ── Port discovery ─────────────────────────────────────────────────────


def _discover_ports(
    dev: SwitchtecDevice, ports_arg: str
) -> list[dict]:
    """Return list of port dicts with phys_id, neg_lnk_width, first_act_lane."""
    statuses = dev.get_status()
    active = [s for s in statuses if s.link_up]

    if ports_arg == "auto":
        return [
            {
                "phys_id": s.port.phys_id,
                "neg_lnk_width": s.neg_lnk_width,
                "first_act_lane": s.first_act_lane,
            }
            for s in active
        ]

    requested_ids = set()
    for token in ports_arg.split(","):
        token = token.strip()
        if token:
            requested_ids.add(int(token))

    active_map = {s.port.phys_id: s for s in active}
    result: list[dict] = []
    for pid in sorted(requested_ids):
        if pid not in active_map:
            _log(f"WARNING: Port {pid} is not active, skipping.")
            continue
        s = active_map[pid]
        result.append({
            "phys_id": s.port.phys_id,
            "neg_lnk_width": s.neg_lnk_width,
            "first_act_lane": s.first_act_lane,
        })
    return result


# ── Margin measurement ─────────────────────────────────────────────────


def _measure_lane(
    dev: SwitchtecDevice,
    lane_id: int,
    timeout: float,
) -> dict | None:
    """Run cross-hair on a single lane. Returns result dict or None on error."""
    try:
        dev.diagnostics.cross_hair_enable(lane_id)
    except SwitchtecError as exc:
        _log(f"  WARNING: cross_hair_enable failed lane {lane_id}: {exc}")
        return None

    try:
        deadline = time.monotonic() + timeout
        result = None
        while time.monotonic() < deadline:
            time.sleep(0.5)
            try:
                results = dev.diagnostics.cross_hair_get(lane_id, 1)
            except SwitchtecError:
                continue
            if not results:
                continue
            ch = results[0]
            if "DONE" in ch.state_name or "ERROR" in ch.state_name:
                result = ch
                break
        return result
    finally:
        try:
            dev.diagnostics.cross_hair_disable()
        except SwitchtecError as exc:
            _log(f"  WARNING: cross_hair_disable failed: {exc}")


def _measure_port(
    dev: SwitchtecDevice,
    port_info: dict,
    h_warn: int,
    v_warn: int,
    timeout: float,
) -> list[dict]:
    """Measure all lanes on one port. Returns list of result rows."""
    port_id = port_info["phys_id"]
    lane_count = port_info["neg_lnk_width"]
    first_lane = port_info["first_act_lane"]
    rows: list[dict] = []

    for i in range(lane_count):
        lane_id = first_lane + i
        _log(
            f"  Port {port_id}, Lane {i + 1}/{lane_count} "
            f"(abs lane {lane_id})..."
        )

        ch = _measure_lane(dev, lane_id, timeout)

        if ch is None or "ERROR" in ch.state_name:
            _log(
                f"    WARNING: measurement failed or timed out for "
                f"lane {lane_id}"
            )
            rows.append({
                "port_id": port_id,
                "lane_id": lane_id,
                "h_margin": 0,
                "v_margin": 0,
                "eye_left": 0,
                "eye_right": 0,
                "eye_bot_left": 0,
                "eye_bot_right": 0,
                "eye_top_left": 0,
                "eye_top_right": 0,
                "h_verdict": "FAIL",
                "v_verdict": "FAIL",
            })
            continue

        h_margin = ch.eye_left_lim + ch.eye_right_lim
        v_top = min(ch.eye_top_left_lim, ch.eye_top_right_lim)
        v_bot = min(ch.eye_bot_left_lim, ch.eye_bot_right_lim)
        v_margin = v_top + v_bot

        h_v = _verdict(h_margin, h_warn)
        v_v = _verdict(v_margin, v_warn)

        overall = "PASS" if h_v == "PASS" and v_v == "PASS" else "FAIL"
        _log(
            f"    Port {port_id}, Lane {i + 1}/{lane_count}: "
            f"h={h_margin} v={v_margin} {overall}"
        )

        rows.append({
            "port_id": port_id,
            "lane_id": lane_id,
            "h_margin": h_margin,
            "v_margin": v_margin,
            "eye_left": ch.eye_left_lim,
            "eye_right": ch.eye_right_lim,
            "eye_bot_left": ch.eye_bot_left_lim,
            "eye_bot_right": ch.eye_bot_right_lim,
            "eye_top_left": ch.eye_top_left_lim,
            "eye_top_right": ch.eye_top_right_lim,
            "h_verdict": h_v,
            "v_verdict": v_v,
        })

    return rows


# ── CSV output ─────────────────────────────────────────────────────────


_CSV_FIELDS = [
    "port_id",
    "lane_id",
    "h_margin",
    "v_margin",
    "eye_left",
    "eye_right",
    "eye_bot_left",
    "eye_bot_right",
    "eye_top_left",
    "eye_top_right",
    "h_verdict",
    "v_verdict",
]


def _write_csv(rows: list[dict], filepath: Path) -> None:
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ── ASCII heatmap ──────────────────────────────────────────────────────


def _format_margin_value(val: int, threshold: int) -> str:
    """Format a single margin value with FAIL marker if below threshold."""
    return f"[{val:>3}]"


def _build_fail_markers(
    values: list[int], threshold: int
) -> str:
    """Build a line of ^^^ markers under failing values."""
    parts: list[str] = []
    has_fail = False
    for val in values:
        if val < threshold:
            parts.append("^FAIL")
            has_fail = True
        else:
            parts.append("     ")
    if not has_fail:
        return ""
    return "         " + "".join(parts)


def _print_heatmap(
    all_rows: list[dict],
    h_warn: int,
    v_warn: int,
) -> None:
    """Print ASCII heatmap grouped by port."""
    port_groups: dict[int, list[dict]] = {}
    for row in all_rows:
        pid = row["port_id"]
        port_groups.setdefault(pid, []).append(row)

    print("\nMargin Heatmap (H=horizontal, V=vertical)")
    print("=" * 70)

    for pid in sorted(port_groups):
        lanes = port_groups[pid]
        lane_count = len(lanes)
        bar = "#" * (lane_count * 3)
        print(f"\nPort {pid:>2}: {bar}  ({lane_count} lanes)")

        # Horizontal row
        h_vals = [r["h_margin"] for r in lanes]
        h_strs = " ".join(_format_margin_value(v, h_warn) for v in h_vals)
        h_all_pass = all(v >= h_warn for v in h_vals)
        h_summary = "all PASS" if h_all_pass else "HAS FAIL"
        print(f"  H: {h_strs}    {h_summary}")

        h_fail_line = _build_fail_markers(h_vals, h_warn)
        if h_fail_line:
            print(h_fail_line)

        # Vertical row
        v_vals = [r["v_margin"] for r in lanes]
        v_strs = " ".join(_format_margin_value(v, v_warn) for v in v_vals)
        v_all_pass = all(v >= v_warn for v in v_vals)
        v_summary = "all PASS" if v_all_pass else "HAS FAIL"
        print(f"  V: {v_strs}    {v_summary}")

        v_fail_line = _build_fail_markers(v_vals, v_warn)
        if v_fail_line:
            print(v_fail_line)

    print()


def _print_worst_case(all_rows: list[dict]) -> None:
    """Print the worst-case lane across all ports."""
    if not all_rows:
        return

    worst_h = min(all_rows, key=lambda r: r["h_margin"])
    worst_v = min(all_rows, key=lambda r: r["v_margin"])

    print("Worst-Case Lanes:")
    print(
        f"  Horizontal: Port {worst_h['port_id']}, "
        f"Lane {worst_h['lane_id']}, "
        f"h_margin={worst_h['h_margin']}"
    )
    print(
        f"  Vertical:   Port {worst_v['port_id']}, "
        f"Lane {worst_v['lane_id']}, "
        f"v_margin={worst_v['v_margin']}"
    )

    total = len(all_rows)
    h_fail = sum(1 for r in all_rows if r["h_verdict"] == "FAIL")
    v_fail = sum(1 for r in all_rows if r["v_verdict"] == "FAIL")
    print(
        f"  Total lanes: {total}, "
        f"H fails: {h_fail}, V fails: {v_fail}"
    )
    print()


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        _log("Discovering ports...")
        ports = _discover_ports(dev, args.ports)
        if not ports:
            _log("No active ports to measure.")
            return

        total_lanes = sum(p["neg_lnk_width"] for p in ports)
        _log(
            f"  {len(ports)} port(s), {total_lanes} total lanes to measure."
        )

        all_rows: list[dict] = []
        for port_info in ports:
            pid = port_info["phys_id"]
            _log(f"Measuring port {pid}...")
            rows = _measure_port(
                dev, port_info, args.h_warn, args.v_warn,
                args.timeout_per_lane,
            )
            all_rows.extend(rows)

        if not all_rows:
            _log("No margin data collected.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"margin_{timestamp}.csv"
        filepath = output_dir / filename
        _write_csv(all_rows, filepath)
        _log(f"CSV written to {filepath}")

        _print_heatmap(all_rows, args.h_warn, args.v_warn)
        _print_worst_case(all_rows)

    except KeyboardInterrupt:
        _log("\nInterrupted by user. Disabling cross-hair...")
        try:
            dev.diagnostics.cross_hair_disable()
        except SwitchtecError:
            pass
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
