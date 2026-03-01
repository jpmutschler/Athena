#!/usr/bin/env python3
"""Inject each error type on active ports and build a resilience scorecard.

Tests the link resilience of a Switchtec Gen6 switch by injecting DLLP CRC,
TLP LCRC, TLP sequence number, and completion timeout errors on each active
port.  After each injection, monitors whether the link stays up, tracks
LTSSM transitions, and measures recovery time.  Produces a CSV matrix and
a terminal scorecard.

Usage:
    python error_resilience_matrix.py --device /dev/switchtec0 --output ./results
    python error_resilience_matrix.py -d /dev/switchtec0 --ports 0,4 --recovery-window 8
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


# ── Injection type definitions ─────────────────────────────────────────

INJECTION_TYPES: list[tuple[str, str]] = [
    ("dllp_crc", "DLLP CRC"),
    ("tlp_lcrc", "TLP LCRC"),
    ("tlp_seq_num", "TLP Seq Num"),
    ("cto", "Completion Timeout"),
]


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Error injection resilience matrix."
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
        "--recovery-window",
        type=float,
        default=5.0,
        help="Seconds to wait for link recovery after injection (default: 5.0)",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt (for automated/CI use)",
    )
    return parser.parse_args()


# ── Helpers ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _is_port_up(dev: SwitchtecDevice, port_id: int) -> bool:
    """Check if a specific port is link-up."""
    try:
        statuses = dev.get_status()
        for s in statuses:
            if s.port.phys_id == port_id:
                return s.link_up
    except SwitchtecError:
        pass
    return False


# ── Port discovery ─────────────────────────────────────────────────────


def _discover_ports(
    dev: SwitchtecDevice, ports_arg: str
) -> list[int]:
    """Return list of active port IDs to test."""
    statuses = dev.get_status()
    active_ids = [s.port.phys_id for s in statuses if s.link_up]

    if ports_arg == "auto":
        return sorted(active_ids)

    requested: list[int] = []
    for token in ports_arg.split(","):
        token = token.strip()
        if token:
            pid = int(token)
            if pid in active_ids:
                requested.append(pid)
            else:
                _log(f"WARNING: Port {pid} is not active, skipping.")
    return sorted(requested)


# ── Injection routines ─────────────────────────────────────────────────


def _inject_dllp_crc(dev: SwitchtecDevice, port_id: int) -> None:
    """Inject a burst of DLLP CRC errors and then disable."""
    dev.injector.inject_dllp_crc(port_id, True, 1)
    time.sleep(0.05)
    dev.injector.inject_dllp_crc(port_id, False, 0)


def _inject_tlp_lcrc(dev: SwitchtecDevice, port_id: int) -> None:
    """Inject a burst of TLP LCRC errors and then disable."""
    dev.injector.inject_tlp_lcrc(port_id, True, 1)
    time.sleep(0.05)
    dev.injector.inject_tlp_lcrc(port_id, False, 0)


def _inject_tlp_seq_num(dev: SwitchtecDevice, port_id: int) -> None:
    """Inject a TLP sequence number error."""
    dev.injector.inject_tlp_seq_num(port_id)


def _inject_cto(dev: SwitchtecDevice, port_id: int) -> None:
    """Inject a completion timeout error."""
    dev.injector.inject_cto(port_id)


_INJECTORS: dict[str, object] = {
    "dllp_crc": _inject_dllp_crc,
    "tlp_lcrc": _inject_tlp_lcrc,
    "tlp_seq_num": _inject_tlp_seq_num,
    "cto": _inject_cto,
}


# ── Test one injection ─────────────────────────────────────────────────


def _test_injection(
    dev: SwitchtecDevice,
    port_id: int,
    inj_key: str,
    inj_name: str,
    recovery_window: float,
) -> dict:
    """Perform one injection test and return a result row dict."""
    row: dict = {
        "port_id": port_id,
        "injection_type": inj_name,
        "link_went_down": False,
        "recovery_time_ms": 0,
        "ltssm_transitions": 0,
        "final_link_up": True,
        "verdict": "PASS",
    }

    # Verify link is up before testing
    if not _is_port_up(dev, port_id):
        row["link_went_down"] = True
        row["final_link_up"] = False
        row["verdict"] = "FAIL"
        return row

    # Clear LTSSM log
    try:
        dev.diagnostics.ltssm_clear(port_id)
    except SwitchtecError as exc:
        _log(f"  WARNING: ltssm_clear failed on port {port_id}: {exc}")

    # Perform injection
    inject_fn = _INJECTORS[inj_key]
    try:
        inject_fn(dev, port_id)
    except SwitchtecError as exc:
        _log(
            f"  WARNING: injection {inj_name} failed on port {port_id}: "
            f"{exc}"
        )
        row["verdict"] = "SKIP"
        return row

    # Monitor link during recovery window
    link_went_down = False
    recovery_time_ms = 0
    poll_start = time.monotonic()
    down_time: float | None = None

    while time.monotonic() - poll_start < recovery_window:
        time.sleep(0.1)
        up = _is_port_up(dev, port_id)
        if not up and not link_went_down:
            link_went_down = True
            down_time = time.monotonic()
        if up and link_went_down and down_time is not None:
            recovery_time_ms = int(
                (time.monotonic() - down_time) * 1000
            )
            break

    # Final state check
    final_up = _is_port_up(dev, port_id)

    # Read LTSSM log
    ltssm_count = 0
    try:
        log_entries = dev.diagnostics.ltssm_log(port_id)
        ltssm_count = len(log_entries)
    except SwitchtecError:
        pass

    row["link_went_down"] = link_went_down
    row["recovery_time_ms"] = recovery_time_ms
    row["ltssm_transitions"] = ltssm_count
    row["final_link_up"] = final_up

    # Determine verdict
    if not final_up:
        row["verdict"] = "FAIL"
    elif link_went_down:
        row["verdict"] = "WARN"
    elif ltssm_count > 0:
        row["verdict"] = "WARN"
    else:
        row["verdict"] = "PASS"

    return row


# ── CSV output ─────────────────────────────────────────────────────────


_CSV_FIELDS = [
    "port_id",
    "injection_type",
    "link_went_down",
    "recovery_time_ms",
    "ltssm_transitions",
    "final_link_up",
    "verdict",
]


def _write_csv(rows: list[dict], filepath: Path) -> None:
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ── Terminal matrix ────────────────────────────────────────────────────


def _print_matrix(all_rows: list[dict], port_ids: list[int]) -> None:
    """Print a compact matrix: ports vs injection types."""
    # Build lookup: (port_id, inj_name) -> verdict
    lookup: dict[tuple[int, str], str] = {}
    for row in all_rows:
        lookup[(row["port_id"], row["injection_type"])] = row["verdict"]

    inj_names = [name for _, name in INJECTION_TYPES]
    col_width = 12

    # Header
    header_parts = [f"{'Port':>6}"]
    for name in inj_names:
        header_parts.append(f"{name:^{col_width}}")
    header = " | ".join(header_parts)
    sep = "-" * len(header)

    print("\nError Resilience Matrix")
    print(sep)
    print(header)
    print(sep)

    # Data rows
    for pid in port_ids:
        parts = [f"{pid:>6}"]
        for _, inj_name in INJECTION_TYPES:
            verdict = lookup.get((pid, inj_name), "N/A")
            parts.append(f"{verdict:^{col_width}}")
        print(" | ".join(parts))

    print(sep)

    # Summary counts
    total = len(all_rows)
    pass_count = sum(1 for r in all_rows if r["verdict"] == "PASS")
    warn_count = sum(1 for r in all_rows if r["verdict"] == "WARN")
    fail_count = sum(1 for r in all_rows if r["verdict"] == "FAIL")
    skip_count = sum(1 for r in all_rows if r["verdict"] == "SKIP")

    print(
        f"\nSummary: {total} tests, "
        f"{pass_count} PASS, {warn_count} WARN, "
        f"{fail_count} FAIL, {skip_count} SKIP"
    )

    if fail_count > 0:
        print("\nFailed tests:")
        for row in all_rows:
            if row["verdict"] == "FAIL":
                print(
                    f"  Port {row['port_id']} x {row['injection_type']}: "
                    f"link_up={row['final_link_up']}, "
                    f"transitions={row['ltssm_transitions']}"
                )

    if warn_count > 0:
        print("\nWarning tests:")
        for row in all_rows:
            if row["verdict"] == "WARN":
                detail = ""
                if row["link_went_down"]:
                    detail = (
                        f"link recovered in {row['recovery_time_ms']}ms"
                    )
                elif row["ltssm_transitions"] > 0:
                    detail = (
                        f"{row['ltssm_transitions']} LTSSM transition(s)"
                    )
                print(
                    f"  Port {row['port_id']} x {row['injection_type']}: "
                    f"{detail}"
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
        _log("Discovering active ports...")
        port_ids = _discover_ports(dev, args.ports)
        if not port_ids:
            _log("No active ports to test.")
            return

        _log(
            f"  {len(port_ids)} port(s): "
            f"{', '.join(str(p) for p in port_ids)}"
        )
        _log(
            f"  {len(INJECTION_TYPES)} injection types, "
            f"{args.recovery_window}s recovery window"
        )

        # Confirmation prompt — destructive operation
        if not args.yes and sys.stdin.isatty():
            inj_names = ", ".join(name for _, name in INJECTION_TYPES)
            port_list = ", ".join(str(p) for p in port_ids)
            response = input(
                f"\nWARNING: This will inject errors ({inj_names})\n"
                f"on ports: {port_list}\n"
                f"This may cause link retraining, AER errors, or OS-visible faults.\n"
                f"Continue? [y/N]: "
            )
            if response.lower() != "y":
                _log("Aborted.")
                return

        all_rows: list[dict] = []
        total_tests = len(port_ids) * len(INJECTION_TYPES)
        test_num = 0

        for pid in port_ids:
            for inj_key, inj_name in INJECTION_TYPES:
                test_num += 1
                _log(
                    f"[{test_num}/{total_tests}] "
                    f"Port {pid} x {inj_name}..."
                )

                row = _test_injection(
                    dev, pid, inj_key, inj_name, args.recovery_window
                )
                all_rows.append(row)

                detail = f"{row['verdict']}"
                if row["verdict"] == "PASS":
                    detail += (
                        f" (link stable, "
                        f"{row['ltssm_transitions']} transitions)"
                    )
                elif row["verdict"] == "WARN":
                    if row["link_went_down"]:
                        detail += (
                            f" (recovered in "
                            f"{row['recovery_time_ms']}ms)"
                        )
                    else:
                        detail += (
                            f" ({row['ltssm_transitions']} LTSSM "
                            f"transitions)"
                        )
                elif row["verdict"] == "FAIL":
                    detail += " (link down, not recovered)"

                _log(f"  Port {pid} x {inj_name}: {detail}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resilience_{timestamp}.csv"
        filepath = output_dir / filename
        _write_csv(all_rows, filepath)
        _log(f"CSV written to {filepath}")

        _print_matrix(all_rows, port_ids)

    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        # Ensure rate-based injections are disabled on all known ports
        for pid in port_ids:
            try:
                dev.injector.inject_dllp_crc(pid, False, 0)
            except SwitchtecError:
                pass
            try:
                dev.injector.inject_tlp_lcrc(pid, False, 0)
            except SwitchtecError:
                pass
        dev.close()


if __name__ == "__main__":
    main()
