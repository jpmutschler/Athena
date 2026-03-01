#!/usr/bin/env python3
"""Unattended overnight link stability monitor for Switchtec Gen6 switches.

Detects link retraining, link-down events, width/rate degradation, and thermal
excursions over extended test runs. Records all events to a JSONL log and
prints a pass/warn/fail verdict on completion.

Usage:
    python overnight_stability_test.py --device /dev/switchtec0 --output ./results
    python overnight_stability_test.py --duration 12 --temp-warn 80 --temp-crit 95
    python overnight_stability_test.py -d /dev/switchtec0 --interval 2
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Overnight link stability monitor with event logging."
    )
    parser.add_argument(
        "--device", "-d", default="/dev/switchtec0", help="Device path"
    )
    parser.add_argument(
        "--output", "-o", default=".", help="Output directory"
    )
    parser.add_argument(
        "--duration", type=int, default=8,
        help="Test duration in hours (default: 8)",
    )
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Seconds between polls (default: 5)",
    )
    parser.add_argument(
        "--temp-warn", type=float, default=85.0,
        help="Temperature warning threshold in C (default: 85.0)",
    )
    parser.add_argument(
        "--temp-crit", type=float, default=100.0,
        help="Temperature critical threshold in C (default: 100.0)",
    )
    return parser.parse_args()


def _fmt_elapsed(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class _EventLog:
    """Thin wrapper around a JSONL file and in-memory event list."""

    def __init__(self, path: Path) -> None:
        self._fh = open(path, "w")
        self.count = 0

    def write(self, event: dict[str, object]) -> None:
        self._fh.write(json.dumps(event, default=str) + "\n")
        self._fh.flush()
        if event.get("type") != "baseline":
            self.count += 1

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()


class _StabilityState:
    """Mutable test state shared across the polling loop and summary."""

    def __init__(self, baseline: dict[int, dict[str, object]]) -> None:
        self.baseline = baseline
        self.active_ports = [
            pid for pid, info in baseline.items() if info["link_up"]
        ]
        self.port_uptime: dict[int, float] = {p: 0.0 for p in baseline}
        self.port_downtime: dict[int, float] = {p: 0.0 for p in baseline}
        self.port_down_start: dict[int, float] = {}
        self.retrain_count: dict[int, int] = {p: 0 for p in baseline}
        self.link_down_count: dict[int, int] = {p: 0 for p in baseline}
        self.ltssm_prev: dict[int, int] = {}
        self.temp_min: float = float("inf")
        self.temp_max: float = float("-inf")
        self.temp_warn_fired: set[int] = set()
        self.has_link_down = False
        self.elapsed_s = 0.0


def _build_baseline(dev: SwitchtecDevice) -> dict[int, dict[str, object]]:
    baseline: dict[int, dict[str, object]] = {}
    for s in dev.get_status():
        baseline[s.port.phys_id] = {
            "link_up": s.link_up,
            "link_rate": s.link_rate,
            "neg_lnk_width": s.neg_lnk_width,
            "ltssm_str": s.ltssm_str,
        }
    return baseline


def _check_ports(
    dev: SwitchtecDevice, st: _StabilityState, elog: _EventLog,
    elapsed: float, actual_delta: float,
) -> None:
    """Compare current port status against baseline; emit change events."""
    try:
        statuses = dev.get_status()
    except SwitchtecError as exc:
        elog.write({"type": "poll_error", "timestamp": _now_iso(), "error": str(exc)})
        return

    for s in statuses:
        pid = s.port.phys_id
        if pid not in st.baseline:
            continue
        prev = st.baseline[pid]

        # Uptime/downtime tracking (uses actual wall-clock delta, not
        # configured interval, to avoid drift over long runs)
        if s.link_up:
            if pid in st.port_down_start:
                # Just recovered — count downtime, don't credit uptime
                st.port_downtime[pid] += elapsed - st.port_down_start.pop(pid)
            else:
                st.port_uptime[pid] += actual_delta
        elif pid not in st.port_down_start and prev["link_up"]:
            st.port_down_start[pid] = elapsed

        # Detect changes and emit events
        for field, etype in [
            ("link_up", "link_change"),
            ("link_rate", "rate_change"),
            ("neg_lnk_width", "width_change"),
        ]:
            cur_val = getattr(s, field)
            if cur_val != prev[field]:
                elog.write({
                    "type": etype, "timestamp": _now_iso(),
                    "port_id": pid, "was": prev[field], "now": cur_val,
                    "elapsed_s": round(elapsed, 1),
                })
                if etype == "link_change" and not cur_val:
                    st.link_down_count[pid] += 1
                    st.has_link_down = True

        st.baseline[pid] = {
            "link_up": s.link_up, "link_rate": s.link_rate,
            "neg_lnk_width": s.neg_lnk_width, "ltssm_str": s.ltssm_str,
        }


def _check_ltssm(
    dev: SwitchtecDevice, st: _StabilityState, elog: _EventLog,
    elapsed: float,
) -> None:
    """Read LTSSM logs on active ports; emit events for new transitions."""
    for pid in st.active_ports:
        try:
            entries = dev.diagnostics.ltssm_log(pid)
            cur = len(entries)
            prev = st.ltssm_prev.get(pid, 0)
            if cur > prev:
                delta = cur - prev
                elog.write({
                    "type": "ltssm_activity", "timestamp": _now_iso(),
                    "port_id": pid, "transitions": delta,
                    "total_entries": cur, "elapsed_s": round(elapsed, 1),
                })
                st.retrain_count[pid] += delta
            st.ltssm_prev[pid] = cur
        except SwitchtecError:
            pass


def _check_temps(
    dev: SwitchtecDevice, st: _StabilityState, elog: _EventLog,
    elapsed: float, warn_thresh: float, crit_thresh: float,
) -> list[float]:
    """Read die temperatures, track min/max, emit threshold events."""
    try:
        temps = dev.get_die_temperatures(nr_sensors=5)
    except SwitchtecError:
        return []

    for i, t in enumerate(temps):
        if t < st.temp_min:
            st.temp_min = t
        if t > st.temp_max:
            st.temp_max = t

        if t >= crit_thresh and i not in st.temp_warn_fired:
            elog.write({
                "type": "temp_critical", "timestamp": _now_iso(),
                "sensor": i, "temp": round(t, 1),
                "threshold": crit_thresh, "elapsed_s": round(elapsed, 1),
            })
            st.temp_warn_fired.add(i)
        elif t >= warn_thresh and i not in st.temp_warn_fired:
            elog.write({
                "type": "temp_warning", "timestamp": _now_iso(),
                "sensor": i, "temp": round(t, 1),
                "threshold": warn_thresh, "elapsed_s": round(elapsed, 1),
            })
            st.temp_warn_fired.add(i)
        elif t < warn_thresh:
            st.temp_warn_fired.discard(i)
    return temps


def _print_summary(st: _StabilityState, event_count: int) -> None:
    """Print terminal summary to stdout."""
    print("\n" + "=" * 60)
    print("OVERNIGHT STABILITY TEST SUMMARY")
    print("=" * 60)
    print(f"Duration:       {_fmt_elapsed(st.elapsed_s)}")
    print(f"Total events:   {event_count}")
    print()

    print("--- Per-Port Results ---")
    for pid in sorted(st.baseline.keys()):
        up = st.port_uptime.get(pid, 0.0)
        down = st.port_downtime.get(pid, 0.0)
        total = up + down if (up + down) > 0 else 1.0
        pct = (up / total) * 100.0
        print(
            f"  Port {pid:2d}: uptime {pct:5.1f}% | "
            f"retrains: {st.retrain_count.get(pid, 0)} | "
            f"link-downs: {st.link_down_count.get(pid, 0)}"
        )

    print("\n--- Temperature ---")
    if st.temp_min != float("inf"):
        print(f"  Min: {st.temp_min:.1f} C  Max: {st.temp_max:.1f} C")
    else:
        print("  No temperature data collected.")

    print()
    if st.has_link_down:
        verdict, reason = "FAIL", "Link-down event(s) detected"
    elif event_count > 0:
        verdict, reason = "WARN", "Non-critical events (retraining, temp)"
    else:
        verdict, reason = "PASS", "No link anomalies detected"
    print(f"Verdict: {verdict} -- {reason}")
    print("=" * 60)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    dev = SwitchtecDevice.open(args.device)
    elog: _EventLog | None = None
    st: _StabilityState | None = None
    start_time = time.monotonic()

    try:
        summary = dev.get_summary()
        baseline = _build_baseline(dev)
        st = _StabilityState(baseline)
        temperatures = dev.get_die_temperatures(nr_sensors=5)

        print(
            f"Device: {summary.name} ({summary.generation} {summary.variant})",
            file=sys.stderr,
        )
        print(
            f"FW: {summary.fw_version} | Ports: {summary.port_count} "
            f"({len(st.active_ports)} active)",
            file=sys.stderr,
        )
        print(
            f"Duration: {args.duration}h | Interval: {args.interval}s | "
            f"Temp warn/crit: {args.temp_warn}/{args.temp_crit} C",
            file=sys.stderr,
        )

        # Clear LTSSM logs
        for pid in st.active_ports:
            try:
                dev.diagnostics.ltssm_clear(pid)
                st.ltssm_prev[pid] = 0
            except SwitchtecError as exc:
                print(f"WARNING: LTSSM clear port {pid}: {exc}", file=sys.stderr)

        # Open event log
        ts_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = output_dir / f"stability_{ts_str}.jsonl"
        elog = _EventLog(log_path)
        print(f"Logging events to: {log_path}", file=sys.stderr)

        elog.write({
            "type": "baseline", "timestamp": _now_iso(),
            "device": summary.name, "generation": summary.generation,
            "variant": summary.variant, "fw_version": summary.fw_version,
            "ports": [
                {"port_id": pid, "link_up": info["link_up"],
                 "link_rate": info["link_rate"],
                 "neg_lnk_width": info["neg_lnk_width"]}
                for pid, info in baseline.items()
            ],
            "temperatures": temperatures,
        })

        # Polling loop
        duration_s = args.duration * 3600
        prev_elapsed = 0.0

        while True:
            elapsed = time.monotonic() - start_time
            if elapsed >= duration_s:
                break
            time.sleep(args.interval)
            elapsed = time.monotonic() - start_time
            actual_delta = elapsed - prev_elapsed
            prev_elapsed = elapsed
            st.elapsed_s = elapsed

            _check_ports(dev, st, elog, elapsed, actual_delta)
            _check_ltssm(dev, st, elog, elapsed)
            temperatures = _check_temps(
                dev, st, elog, elapsed, args.temp_warn, args.temp_crit,
            )

            # Status ticker
            ports_up = sum(1 for info in st.baseline.values() if info["link_up"])
            max_t = max(temperatures) if temperatures else 0.0
            now_str = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
            print(
                f"[{now_str}] Elapsed: {_fmt_elapsed(elapsed)} | "
                f"Ports UP: {ports_up}/{len(st.baseline)} | "
                f"Events: {elog.count} | Temp: {max_t:.1f} C",
                file=sys.stderr,
            )

        # Write final event
        st.elapsed_s = time.monotonic() - start_time
        _write_final(dev, elog, st.active_ports)
        _print_summary(st, elog.count)

    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        if st is not None:
            st.elapsed_s = time.monotonic() - start_time
            _print_summary(st, elog.count if elog else 0)

    finally:
        if elog is not None:
            elog.close()
        dev.close()


def _write_final(
    dev: SwitchtecDevice, elog: _EventLog, active_ports: list[int],
) -> None:
    final_ltssm: dict[int, int] = {}
    for pid in active_ports:
        try:
            final_ltssm[pid] = len(dev.diagnostics.ltssm_log(pid))
        except SwitchtecError:
            final_ltssm[pid] = -1
    try:
        final_temps = dev.get_die_temperatures(nr_sensors=5)
    except SwitchtecError:
        final_temps = []
    elog.write({
        "type": "final", "timestamp": _now_iso(),
        "ltssm_entries": final_ltssm, "temperatures": final_temps,
    })


if __name__ == "__main__":
    main()
