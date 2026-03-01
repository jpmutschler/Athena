#!/usr/bin/env python3
"""Continuously log bandwidth counters for selected ports to a timestamped CSV.

Records egress/ingress bandwidth broken down by TLP type (posted, completion,
non-posted) for one or more physical ports on a Switchtec Gen6 switch.
Optionally includes die temperature readings alongside each sample.

Usage:
    python bw_traffic_logger.py --device /dev/switchtec0 --output ./results
    python bw_traffic_logger.py -d /dev/switchtec0 --ports 0,4,8 --interval 0.5
    python bw_traffic_logger.py --with-temp --duration 300
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Log bandwidth counters to CSV with optional temperature."
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
        default=0,
        help="Total seconds to run, 0 = infinite (default: 0)",
    )
    parser.add_argument(
        "--with-temp",
        action="store_true",
        help="Also log die temperature sensors in each row",
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


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dev = SwitchtecDevice.open(args.device)
    csv_file = None
    writer = None
    stats: dict[int, dict[str, list[int]]] = {}
    sample_count = 0
    port_ids: list[int] = []

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

        # Determine sample count
        count = 0
        if args.duration > 0:
            count = max(1, int(args.duration / args.interval))

        # Detect temperature sensor count
        nr_sensors = 0
        if args.with_temp:
            try:
                temps = dev.get_die_temperatures(nr_sensors=5)
                nr_sensors = len(temps)
            except SwitchtecError as exc:
                print(
                    f"WARNING: Cannot read temperatures: {exc}",
                    file=sys.stderr,
                )
                nr_sensors = 0

        # Open CSV
        timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = output_dir / f"bw_log_{timestamp_str}.csv"
        csv_file = open(csv_path, "w", newline="")

        header = [
            "timestamp",
            "elapsed_s",
            "port_id",
            "egress_posted",
            "egress_comp",
            "egress_nonposted",
            "egress_total",
            "ingress_posted",
            "ingress_comp",
            "ingress_nonposted",
            "ingress_total",
        ]
        if nr_sensors > 0:
            header.extend(f"temp_{i}" for i in range(nr_sensors))

        writer = csv.writer(csv_file)
        writer.writerow(header)

        print(f"Logging to: {csv_path}", file=sys.stderr)
        print(
            f"Ports: {port_ids} | Interval: {args.interval}s | "
            f"Duration: {'infinite' if args.duration == 0 else f'{args.duration}s'}",
            file=sys.stderr,
        )

        # Accumulators for summary statistics
        stats: dict[int, dict[str, list[int]]] = {
            pid: {"egress": [], "ingress": []} for pid in port_ids
        }
        sample_count = 0
        ticker_interval = max(1, len(port_ids))
        last_temp_iteration = -1
        cached_temps: list[float] = []

        # Stream bandwidth samples
        for sample in dev.monitor.watch_bw(
            port_ids, interval=args.interval, count=count
        ):
            row = [
                f"{sample.timestamp:.6f}",
                f"{sample.elapsed_s:.3f}",
                sample.port_id,
                sample.egress_posted,
                sample.egress_comp,
                sample.egress_nonposted,
                sample.egress_total,
                sample.ingress_posted,
                sample.ingress_comp,
                sample.ingress_nonposted,
                sample.ingress_total,
            ]

            if nr_sensors > 0 and sample.iteration != last_temp_iteration:
                try:
                    cached_temps = dev.get_die_temperatures(nr_sensors)
                except SwitchtecError:
                    cached_temps = [0.0] * nr_sensors
                last_temp_iteration = sample.iteration

            if nr_sensors > 0:
                row.extend(f"{t:.1f}" for t in cached_temps)

            writer.writerow(row)
            sample_count += 1

            # Track stats
            stats[sample.port_id]["egress"].append(sample.egress_total)
            stats[sample.port_id]["ingress"].append(sample.ingress_total)

            # Ticker: print once per iteration (after all ports for that iteration)
            if sample_count % ticker_interval == 0:
                parts = []
                for pid in port_ids:
                    eg = stats[pid]["egress"][-1] if stats[pid]["egress"] else 0
                    ig = stats[pid]["ingress"][-1] if stats[pid]["ingress"] else 0
                    parts.append(f"Port {pid}: egress={eg} ingress={ig}")
                elapsed_str = _format_elapsed(sample.elapsed_s)
                print(
                    f"[{elapsed_str}] {' | '.join(parts)}",
                    file=sys.stderr,
                )
                csv_file.flush()

        # Duration complete
        _print_summary(stats, sample_count, port_ids)

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        _print_summary(stats, sample_count, port_ids)

    finally:
        if csv_file is not None:
            csv_file.flush()
            csv_file.close()
        dev.close()


def _print_summary(
    stats: dict[int, dict[str, list[int]]],
    sample_count: int,
    port_ids: list[int],
) -> None:
    """Print min/max/avg bandwidth summary to stdout."""
    print("\n--- Bandwidth Summary ---")
    print(f"Total samples: {sample_count}")
    for pid in port_ids:
        eg = stats[pid]["egress"]
        ig = stats[pid]["ingress"]
        if not eg:
            print(f"Port {pid}: no data collected")
            continue
        print(
            f"Port {pid}:"
            f"  egress  min={min(eg)} max={max(eg)} avg={sum(eg) // len(eg)}"
            f"  ingress min={min(ig)} max={max(ig)} avg={sum(ig) // len(ig)}"
        )


if __name__ == "__main__":
    main()
