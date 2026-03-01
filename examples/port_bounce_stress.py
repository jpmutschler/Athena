#!/usr/bin/env python3
"""Stress test link recovery by repeatedly disabling/enabling a port.

Cycles a single physical port through disable/enable operations and measures
link recovery time, verifying that the link comes back at baseline speed and
width each time. Records per-cycle results to CSV and prints a final summary
with pass/degraded/fail counts and recovery time statistics.

Usage:
    python port_bounce_stress.py --device /dev/switchtec0 --port 4 --output ./results
    python port_bounce_stress.py -d /dev/switchtec0 --port 0 --cycles 50
    python port_bounce_stress.py --port 8 --down-time 2.0 --recovery-timeout 15
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.bindings.constants import FabPortControlType
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stress test link recovery via port bounce cycles."
    )
    parser.add_argument(
        "--device", "-d", default="/dev/switchtec0", help="Device path"
    )
    parser.add_argument(
        "--output", "-o", default=".", help="Output directory"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Physical port ID to bounce",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="Number of bounce cycles (default: 100)",
    )
    parser.add_argument(
        "--down-time",
        type=float,
        default=1.0,
        help="Seconds port stays disabled (default: 1.0)",
    )
    parser.add_argument(
        "--recovery-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for link up after enable (default: 10.0)",
    )
    return parser.parse_args()


def _find_port_status(
    dev: SwitchtecDevice, port_id: int
) -> object | None:
    """Find the PortStatus for a given physical port ID, or None."""
    statuses = dev.get_status()
    for s in statuses:
        if s.port.phys_id == port_id:
            return s
    return None


def _poll_link_up(
    dev: SwitchtecDevice,
    port_id: int,
    timeout: float,
    poll_interval: float = 0.1,
) -> tuple[bool, float, int, int]:
    """Poll until port is link_up or timeout.

    Returns:
        (link_up, recovery_ms, link_rate, neg_lnk_width)
    """
    start = time.monotonic()
    deadline = start + timeout

    while time.monotonic() < deadline:
        try:
            status = _find_port_status(dev, port_id)
            if status is not None and status.link_up:
                recovery_ms = (time.monotonic() - start) * 1000.0
                return (
                    True,
                    recovery_ms,
                    status.link_rate,
                    status.neg_lnk_width,
                )
        except SwitchtecError:
            pass
        time.sleep(poll_interval)

    # Timeout: try one final read
    try:
        status = _find_port_status(dev, port_id)
        if status is not None and status.link_up:
            recovery_ms = (time.monotonic() - start) * 1000.0
            return (
                True,
                recovery_ms,
                status.link_rate,
                status.neg_lnk_width,
            )
    except SwitchtecError:
        pass

    return (False, timeout * 1000.0, 0, 0)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dev = SwitchtecDevice.open(args.device)
    csv_file = None
    writer = None

    # Results tracking
    verdicts: list[str] = []
    recovery_times: list[float] = []
    completed_cycles = 0
    baseline_rate = 0
    baseline_width = 0

    try:
        # Baseline check
        baseline_status = _find_port_status(dev, args.port)
        if baseline_status is None:
            print(
                f"ERROR: Port {args.port} not found on device.",
                file=sys.stderr,
            )
            sys.exit(1)

        if not baseline_status.link_up:
            print(
                f"ERROR: Port {args.port} is not link-up. "
                f"LTSSM: {baseline_status.ltssm_str}",
                file=sys.stderr,
            )
            sys.exit(1)

        baseline_rate = baseline_status.link_rate
        baseline_width = baseline_status.neg_lnk_width

        print(
            f"Port {args.port} baseline: "
            f"rate={baseline_rate} width=x{baseline_width}",
            file=sys.stderr,
        )
        print(
            f"Cycles: {args.cycles} | Down-time: {args.down_time}s | "
            f"Recovery timeout: {args.recovery_timeout}s",
            file=sys.stderr,
        )

        # Open CSV
        timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        csv_path = output_dir / f"bounce_{timestamp_str}.csv"
        csv_file = open(csv_path, "w", newline="")
        writer = csv.writer(csv_file)
        writer.writerow([
            "cycle",
            "disable_time",
            "enable_time",
            "recovery_ms",
            "link_rate",
            "link_width",
            "verdict",
        ])

        print(f"Logging to: {csv_path}", file=sys.stderr)
        print("", file=sys.stderr)

        # Bounce loop
        for cycle in range(1, args.cycles + 1):
            # (a) Clear LTSSM log
            try:
                dev.diagnostics.ltssm_clear(args.port)
            except SwitchtecError:
                pass

            # (b) Disable port
            disable_time = datetime.now(tz=timezone.utc).isoformat()
            try:
                dev.fabric.port_control(
                    args.port, FabPortControlType.DISABLE
                )
            except SwitchtecError as exc:
                print(
                    f"Cycle {cycle}/{args.cycles}: "
                    f"DISABLE failed: {exc}",
                    file=sys.stderr,
                )
                verdict = "FAIL"
                writer.writerow([
                    cycle, disable_time, "", 0.0, 0, 0, verdict,
                ])
                verdicts.append(verdict)
                completed_cycles += 1
                continue

            # (c) Wait down-time
            time.sleep(args.down_time)

            # (d) Enable port
            enable_time = datetime.now(tz=timezone.utc).isoformat()
            try:
                dev.fabric.port_control(
                    args.port, FabPortControlType.ENABLE
                )
            except SwitchtecError as exc:
                print(
                    f"Cycle {cycle}/{args.cycles}: "
                    f"ENABLE failed: {exc}",
                    file=sys.stderr,
                )
                verdict = "FAIL"
                writer.writerow([
                    cycle, disable_time, enable_time, 0.0, 0, 0, verdict,
                ])
                verdicts.append(verdict)
                completed_cycles += 1
                continue

            # (e) Poll for link-up
            link_up, recovery_ms, rate, width = _poll_link_up(
                dev, args.port, args.recovery_timeout
            )

            # (f) Determine verdict
            if not link_up:
                verdict = "FAIL"
            elif rate == baseline_rate and width == baseline_width:
                verdict = "PASS"
            else:
                verdict = "DEGRADED"

            # (g) Write CSV row
            writer.writerow([
                cycle,
                disable_time,
                enable_time,
                f"{recovery_ms:.1f}",
                rate,
                width,
                verdict,
            ])
            verdicts.append(verdict)
            if link_up:
                recovery_times.append(recovery_ms)
            completed_cycles += 1

            # (h) Print progress
            if verdict == "PASS":
                detail = f"recovery: {recovery_ms:.0f}ms"
            elif verdict == "DEGRADED":
                detail = (
                    f"recovery: {recovery_ms:.0f}ms "
                    f"rate={rate} width=x{width}"
                )
            else:
                detail = "link did not come up"

            print(
                f"Cycle {cycle:>{len(str(args.cycles))}}"
                f"/{args.cycles}: {verdict} ({detail})",
                file=sys.stderr,
            )

            # Flush CSV periodically
            if cycle % 10 == 0:
                csv_file.flush()

        # Completed all cycles
        _print_summary(
            args, verdicts, recovery_times, completed_cycles,
            baseline_rate, baseline_width,
        )

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        _print_summary(
            args, verdicts, recovery_times, completed_cycles,
            baseline_rate, baseline_width,
        )

    finally:
        if csv_file is not None:
            csv_file.flush()
            csv_file.close()
        dev.close()


def _print_summary(
    args: argparse.Namespace,
    verdicts: list[str],
    recovery_times: list[float],
    completed_cycles: int,
    baseline_rate: int,
    baseline_width: int,
) -> None:
    """Print port bounce stress test summary to stdout."""
    pass_count = verdicts.count("PASS")
    degraded_count = verdicts.count("DEGRADED")
    fail_count = verdicts.count("FAIL")

    print("\n" + "=" * 56)
    print("PORT BOUNCE STRESS TEST SUMMARY")
    print("=" * 56)
    print(f"Port:            {args.port}")
    print(f"Baseline:        rate={baseline_rate} width=x{baseline_width}")
    print(f"Cycles:          {completed_cycles}/{args.cycles}")
    print(f"Down-time:       {args.down_time}s")
    print(f"Recovery timeout:{args.recovery_timeout}s")
    print()
    print(f"  PASS:     {pass_count:>5}")
    print(f"  DEGRADED: {degraded_count:>5}")
    print(f"  FAIL:     {fail_count:>5}")
    print()

    if recovery_times:
        min_rt = min(recovery_times)
        max_rt = max(recovery_times)
        avg_rt = sum(recovery_times) / len(recovery_times)
        print("Recovery time (ms):")
        print(f"  Min:  {min_rt:>8.1f}")
        print(f"  Max:  {max_rt:>8.1f}")
        print(f"  Avg:  {avg_rt:>8.1f}")

        # Trend detection: compare first quarter avg to last quarter avg
        quarter = max(1, len(recovery_times) // 4)
        first_q = recovery_times[:quarter]
        last_q = recovery_times[-quarter:]
        avg_first = sum(first_q) / len(first_q)
        avg_last = sum(last_q) / len(last_q)

        if avg_last > avg_first * 1.2:
            print(
                f"\n  TREND: Recovery time increasing "
                f"({avg_first:.0f}ms -> {avg_last:.0f}ms)"
            )
        elif avg_last < avg_first * 0.8:
            print(
                f"\n  TREND: Recovery time decreasing "
                f"({avg_first:.0f}ms -> {avg_last:.0f}ms)"
            )
        else:
            print("\n  TREND: Recovery time stable")
    else:
        print("Recovery time: no successful recoveries recorded")

    print("=" * 56)


if __name__ == "__main__":
    main()
