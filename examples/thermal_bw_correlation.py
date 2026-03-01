#!/usr/bin/env python3
"""Simultaneously log bandwidth and die temperature for thermal throttling analysis.

Captures time-aligned bandwidth counters and temperature sensor readings,
then computes Pearson correlation to detect thermal throttling effects on
PCIe bandwidth. No external dependencies required -- correlation is computed
using running accumulators.

Usage:
    python thermal_bw_correlation.py --device /dev/switchtec0 --output ./results
    python thermal_bw_correlation.py --ports 0,4 --duration 600 --interval 2
    python thermal_bw_correlation.py --sensors 3 --duration 120
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Log bandwidth and temperature for thermal correlation analysis."
        )
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
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between samples (default: 1.0)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Total seconds to run (default: 300)",
    )
    parser.add_argument(
        "--sensors",
        type=int,
        default=5,
        help="Number of temperature sensors to read (default: 5)",
    )
    return parser.parse_args()


def _discover_active_ports(dev: SwitchtecDevice) -> list[int]:
    """Return physical port IDs for all link-up ports."""
    statuses = dev.get_status()
    return [s.port.phys_id for s in statuses if s.link_up]


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _pearson_r(
    n: int,
    sum_x: float,
    sum_y: float,
    sum_xy: float,
    sum_x2: float,
    sum_y2: float,
) -> float:
    """Compute Pearson correlation coefficient from running accumulators.

    Returns 0.0 if the denominator is zero (constant series).
    """
    if n < 2:
        return 0.0
    numerator = n * sum_xy - sum_x * sum_y
    denom_x = n * sum_x2 - sum_x * sum_x
    denom_y = n * sum_y2 - sum_y * sum_y
    if denom_x <= 0.0 or denom_y <= 0.0:
        return 0.0
    return numerator / math.sqrt(denom_x * denom_y)


class _CorrAccumulator:
    """Running accumulator for Pearson correlation between two series."""

    __slots__ = ("n", "sum_x", "sum_y", "sum_xy", "sum_x2", "sum_y2")

    def __init__(self) -> None:
        self.n = 0
        self.sum_x = 0.0
        self.sum_y = 0.0
        self.sum_xy = 0.0
        self.sum_x2 = 0.0
        self.sum_y2 = 0.0

    def update(self, x: float, y: float) -> None:
        self.n += 1
        self.sum_x += x
        self.sum_y += y
        self.sum_xy += x * y
        self.sum_x2 += x * x
        self.sum_y2 += y * y

    def r(self) -> float:
        return _pearson_r(
            self.n,
            self.sum_x,
            self.sum_y,
            self.sum_xy,
            self.sum_x2,
            self.sum_y2,
        )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dev = SwitchtecDevice.open(args.device)
    csv_file = None
    port_ids: list[int] = []

    # Per-port tracking
    port_bw_egress: dict[int, list[int]] = {}
    port_bw_ingress: dict[int, list[int]] = {}
    temp_history: list[float] = []
    corr_egress: dict[int, _CorrAccumulator] = {}
    corr_ingress: dict[int, _CorrAccumulator] = {}
    sample_count = 0

    try:
        # Discover ports
        if args.ports == "auto":
            port_ids = _discover_active_ports(dev)
            if not port_ids:
                print("ERROR: No active ports found.", file=sys.stderr)
                sys.exit(1)
            print(
                f"Auto-discovered active ports: {port_ids}",
                file=sys.stderr,
            )
        else:
            port_ids = [int(p.strip()) for p in args.ports.split(",")]

        for pid in port_ids:
            port_bw_egress[pid] = []
            port_bw_ingress[pid] = []
            corr_egress[pid] = _CorrAccumulator()
            corr_ingress[pid] = _CorrAccumulator()

        # Open CSV
        timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = output_dir / f"thermal_bw_{timestamp_str}.csv"
        csv_file = open(csv_path, "w", newline="")

        header = ["timestamp", "elapsed_s"]
        header.extend(f"sensor_{i}" for i in range(args.sensors))
        for pid in port_ids:
            header.extend([f"port_{pid}_egress", f"port_{pid}_ingress"])
        writer = csv.writer(csv_file)
        writer.writerow(header)

        print(f"Logging to: {csv_path}", file=sys.stderr)
        print(
            f"Ports: {port_ids} | Sensors: {args.sensors} | "
            f"Interval: {args.interval}s | Duration: {args.duration}s",
            file=sys.stderr,
        )

        # Initial clear read for bandwidth baseline
        try:
            dev.performance.bw_get(port_ids, clear=True)
        except SwitchtecError as exc:
            print(f"WARNING: Initial BW clear failed: {exc}", file=sys.stderr)

        start_time = time.monotonic()

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= args.duration:
                break

            time.sleep(args.interval)
            elapsed = time.monotonic() - start_time
            now_ts = time.time()

            # Read temperatures
            try:
                temps = dev.get_die_temperatures(nr_sensors=args.sensors)
            except SwitchtecError:
                temps = [0.0] * args.sensors

            avg_temp = sum(temps) / len(temps) if temps else 0.0
            temp_history.append(avg_temp)

            # Read bandwidth (clear-on-read for delta)
            try:
                bw_results = dev.performance.bw_get(port_ids, clear=True)
            except SwitchtecError:
                bw_results = None

            # Build CSV row
            row: list[str] = [f"{now_ts:.6f}", f"{elapsed:.3f}"]
            row.extend(f"{t:.1f}" for t in temps)

            for i, pid in enumerate(port_ids):
                if bw_results is not None and i < len(bw_results):
                    eg = bw_results[i].egress.total
                    ig = bw_results[i].ingress.total
                else:
                    eg = 0
                    ig = 0

                row.extend([str(eg), str(ig)])
                port_bw_egress[pid].append(eg)
                port_bw_ingress[pid].append(ig)

                # Update correlation accumulators (temp vs bw)
                corr_egress[pid].update(avg_temp, float(eg))
                corr_ingress[pid].update(avg_temp, float(ig))

            writer.writerow(row)
            sample_count += 1

            # Periodic flush and ticker
            if sample_count % 10 == 0:
                csv_file.flush()

            bw_parts = []
            for pid in port_ids:
                eg = port_bw_egress[pid][-1] if port_bw_egress[pid] else 0
                ig = port_bw_ingress[pid][-1] if port_bw_ingress[pid] else 0
                bw_parts.append(f"P{pid}:eg={eg}/ig={ig}")
            print(
                f"[{_format_elapsed(elapsed)}] "
                f"Temp={avg_temp:.1f}C | {' '.join(bw_parts)}",
                file=sys.stderr,
            )

        # Duration complete
        _print_summary(
            port_ids,
            args.sensors,
            port_bw_egress,
            port_bw_ingress,
            temp_history,
            corr_egress,
            corr_ingress,
            sample_count,
        )

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        _print_summary(
            port_ids,
            args.sensors,
            port_bw_egress,
            port_bw_ingress,
            temp_history,
            corr_egress,
            corr_ingress,
            sample_count,
        )

    finally:
        if csv_file is not None:
            csv_file.flush()
            csv_file.close()
        dev.close()


def _print_summary(
    port_ids: list[int],
    nr_sensors: int,
    port_bw_egress: dict[int, list[int]],
    port_bw_ingress: dict[int, list[int]],
    temp_history: list[float],
    corr_egress: dict[int, _CorrAccumulator],
    corr_ingress: dict[int, _CorrAccumulator],
    sample_count: int,
) -> None:
    """Print correlation analysis summary to stdout."""
    print("\n" + "=" * 64)
    print("THERMAL-BANDWIDTH CORRELATION ANALYSIS")
    print("=" * 64)
    print(f"Total samples: {sample_count}")

    # Temperature range
    if temp_history:
        print(
            f"Temperature: min={min(temp_history):.1f}C  "
            f"max={max(temp_history):.1f}C  "
            f"avg={sum(temp_history) / len(temp_history):.1f}C"
        )
        temp_range = max(temp_history) - min(temp_history)
    else:
        print("Temperature: no data")
        temp_range = 0.0

    print()
    print("--- Per-Port Analysis ---")
    print(
        f"{'Port':>6}  {'Avg Egress':>12}  {'Egress Range':>14}  "
        f"{'Avg Ingress':>12}  {'Ingress Range':>14}  "
        f"{'r(eg)':>7}  {'r(ig)':>7}  {'Flag':>6}"
    )
    print("-" * 100)

    for pid in port_ids:
        eg_list = port_bw_egress.get(pid, [])
        ig_list = port_bw_ingress.get(pid, [])

        if not eg_list:
            print(f"{pid:>6}  {'no data':>12}")
            continue

        avg_eg = sum(eg_list) // len(eg_list)
        avg_ig = sum(ig_list) // len(ig_list)
        min_eg = min(eg_list)
        max_eg = max(eg_list)
        min_ig = min(ig_list)
        max_ig = max(ig_list)

        r_eg = corr_egress[pid].r()
        r_ig = corr_ingress[pid].r()

        # Flag if BW dropped >10% while temp rose >10C AND the
        # correlation is negative (BW decreasing as temp increases)
        flag = ""
        if max_eg > 0 and temp_range > 10.0 and r_eg < -0.3:
            bw_drop_pct = ((max_eg - min_eg) / max_eg) * 100.0
            if bw_drop_pct > 10.0:
                flag = "THROT"

        print(
            f"{pid:>6}  {avg_eg:>12}  "
            f"{min_eg:>6}-{max_eg:<6}  "
            f"{avg_ig:>12}  "
            f"{min_ig:>6}-{max_ig:<6}  "
            f"{r_eg:>7.3f}  {r_ig:>7.3f}  {flag:>6}"
        )

    print()
    print("Correlation key: r > 0 means BW increases with temp,")
    print("                 r < 0 means BW decreases with temp (throttling).")
    print("THROT flag: BW dropped >10% while temp rose >10C and r < -0.3.")
    print("=" * 64)


if __name__ == "__main__":
    main()
