#!/usr/bin/env python3
"""Capture TX equalization coefficients and FS/LF for all active ports to CSV.

Reads per-lane equalization data (pre/post cursors, FS, LF) from every
link-up port on a Switchtec Gen6 switch.  Optionally captures RX receiver
object data (CTLE, DFE taps).  Produces a timestamped CSV file and prints
a terminal summary with per-port statistics and outlier warnings.

Usage:
    python eq_coefficient_snapshot.py --device /dev/switchtec0 --output ./results
    python eq_coefficient_snapshot.py -d /dev/switchtec0 --with-rx
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture TX equalization coefficients to CSV."
    )
    parser.add_argument(
        "--device", "-d", default="/dev/switchtec0", help="Device path"
    )
    parser.add_argument(
        "--output", "-o", default=".", help="Output directory"
    )
    parser.add_argument(
        "--with-rx",
        action="store_true",
        help="Also capture RX receiver object data (CTLE, DFE)",
    )
    return parser.parse_args()


# ── Helpers ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _mean(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stddev(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


# ── Data collection ────────────────────────────────────────────────────


def _collect_active_ports(dev: SwitchtecDevice) -> list[dict]:
    """Return list of dicts for each link-up port."""
    statuses = dev.get_status()
    active: list[dict] = []
    for s in statuses:
        if s.link_up:
            active.append({
                "phys_id": s.port.phys_id,
                "neg_lnk_width": s.neg_lnk_width,
                "first_act_lane": s.first_act_lane,
            })
    return active


def _capture_port(
    dev: SwitchtecDevice,
    port_id: int,
    with_rx: bool,
) -> list[dict]:
    """Capture EQ data for all lanes on a single port.

    Returns a list of row dicts, one per lane.
    """
    rows: list[dict] = []

    try:
        coeff = dev.diagnostics.port_eq_tx_coeff(port_id)
    except SwitchtecError as exc:
        _log(f"  WARNING: TX coeff read failed on port {port_id}: {exc}")
        return rows

    lane_count = coeff.lane_count
    for lane_idx in range(lane_count):
        cursor = coeff.cursors[lane_idx]
        row: dict = {
            "port_id": port_id,
            "lane_id": lane_idx,
            "pre_cursor": cursor.pre,
            "post_cursor": cursor.post,
        }

        # FS / LF
        try:
            fslf = dev.diagnostics.port_eq_tx_fslf(port_id, lane_id=lane_idx)
            row["fs"] = fslf.fs
            row["lf"] = fslf.lf
        except SwitchtecError as exc:
            _log(
                f"  WARNING: FS/LF read failed on port {port_id} "
                f"lane {lane_idx}: {exc}"
            )
            row["fs"] = ""
            row["lf"] = ""

        # Optional RX receiver object
        if with_rx:
            try:
                rx = dev.diagnostics.rcvr_obj(port_id, lane_idx)
                row["ctle"] = rx.ctle
                row["target_amplitude"] = rx.target_amplitude
                row["speculative_dfe"] = rx.speculative_dfe
                for i in range(7):
                    row[f"dfe_{i}"] = rx.dynamic_dfe[i]
            except SwitchtecError as exc:
                _log(
                    f"  WARNING: RX obj read failed on port {port_id} "
                    f"lane {lane_idx}: {exc}"
                )
                row["ctle"] = ""
                row["target_amplitude"] = ""
                row["speculative_dfe"] = ""
                for i in range(7):
                    row[f"dfe_{i}"] = ""

        rows.append(row)

    return rows


# ── CSV writing ────────────────────────────────────────────────────────


def _csv_header(with_rx: bool) -> list[str]:
    base = ["port_id", "lane_id", "pre_cursor", "post_cursor", "fs", "lf"]
    if with_rx:
        base.extend([
            "ctle",
            "target_amplitude",
            "speculative_dfe",
            "dfe_0",
            "dfe_1",
            "dfe_2",
            "dfe_3",
            "dfe_4",
            "dfe_5",
            "dfe_6",
        ])
    return base


def _write_csv(
    rows: list[dict], filepath: Path, with_rx: bool
) -> None:
    header = _csv_header(with_rx)
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


# ── Statistics & outlier detection ─────────────────────────────────────


def _compute_stats(
    all_rows: list[dict],
) -> dict[int, dict]:
    """Compute per-port mean/stddev for pre and post cursors.

    Returns {port_id: {"pre_mean", "pre_std", "post_mean", "post_std",
                        "lane_count", "outliers": [(lane, field, val)]}}.
    """
    port_rows: dict[int, list[dict]] = {}
    for row in all_rows:
        pid = row["port_id"]
        port_rows.setdefault(pid, []).append(row)

    stats: dict[int, dict] = {}
    for pid in sorted(port_rows):
        lanes = port_rows[pid]
        pre_vals = [r["pre_cursor"] for r in lanes if isinstance(r["pre_cursor"], int)]
        post_vals = [r["post_cursor"] for r in lanes if isinstance(r["post_cursor"], int)]

        pre_mean = _mean(pre_vals)
        pre_std = _stddev(pre_vals)
        post_mean = _mean(post_vals)
        post_std = _stddev(post_vals)

        outliers: list[tuple[int, str, int]] = []
        for r in lanes:
            lane = r["lane_id"]
            if isinstance(r["pre_cursor"], int) and pre_std > 0:
                if abs(r["pre_cursor"] - pre_mean) > 2 * pre_std:
                    outliers.append((lane, "pre_cursor", r["pre_cursor"]))
            if isinstance(r["post_cursor"], int) and post_std > 0:
                if abs(r["post_cursor"] - post_mean) > 2 * post_std:
                    outliers.append((lane, "post_cursor", r["post_cursor"]))

        stats[pid] = {
            "lane_count": len(lanes),
            "pre_mean": pre_mean,
            "pre_std": pre_std,
            "post_mean": post_mean,
            "post_std": post_std,
            "outliers": outliers,
        }

    return stats


# ── Terminal output ────────────────────────────────────────────────────


def _print_summary(stats: dict[int, dict]) -> None:
    hdr = (
        f"{'Port':>6}  {'Lanes':>5}  "
        f"{'Pre Mean':>9}  {'Pre Std':>8}  "
        f"{'Post Mean':>10}  {'Post Std':>9}  "
        f"{'Outliers':>8}"
    )
    sep = "-" * len(hdr)

    print("\nEqualization Coefficient Summary")
    print(sep)
    print(hdr)
    print(sep)

    total_outliers = 0
    for pid in sorted(stats):
        s = stats[pid]
        n_out = len(s["outliers"])
        total_outliers += n_out
        out_str = str(n_out) if n_out > 0 else "-"
        print(
            f"{pid:>6}  {s['lane_count']:>5}  "
            f"{s['pre_mean']:>9.2f}  {s['pre_std']:>8.2f}  "
            f"{s['post_mean']:>10.2f}  {s['post_std']:>9.2f}  "
            f"{out_str:>8}"
        )
    print(sep)

    if total_outliers > 0:
        print(f"\nWARNING: {total_outliers} outlier lane(s) detected "
              f"(>2 stddev from port mean):")
        for pid in sorted(stats):
            for lane, field, val in stats[pid]["outliers"]:
                s = stats[pid]
                if field == "pre_cursor":
                    mean = s["pre_mean"]
                    std = s["pre_std"]
                else:
                    mean = s["post_mean"]
                    std = s["post_std"]
                print(
                    f"  Port {pid}, Lane {lane}: {field}={val} "
                    f"(mean={mean:.2f}, std={std:.2f})"
                )
    else:
        print("\nNo outlier lanes detected.")
    print()


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        _log("Discovering active ports...")
        active_ports = _collect_active_ports(dev)
        if not active_ports:
            _log("No active ports found. Nothing to capture.")
            return

        _log(f"  {len(active_ports)} active port(s) found.")
        all_rows: list[dict] = []

        for idx, port_info in enumerate(active_ports):
            port_id = port_info["phys_id"]
            _log(
                f"Capturing port {port_id} "
                f"({idx + 1}/{len(active_ports)})..."
            )
            rows = _capture_port(dev, port_id, args.with_rx)
            all_rows.extend(rows)
            if rows:
                _log(f"  Port {port_id}: {len(rows)} lanes captured")
            else:
                _log(f"  Port {port_id}: no data captured")

        if not all_rows:
            _log("No equalization data captured.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eq_snapshot_{timestamp}.csv"
        filepath = output_dir / filename
        _write_csv(all_rows, filepath, args.with_rx)
        _log(f"CSV written to {filepath}")

        stats = _compute_stats(all_rows)
        _print_summary(stats)

    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
