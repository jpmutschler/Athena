#!/usr/bin/env python3
"""Run BER measurement at multiple PCIe generations via loopback.

Configures loopback mode on a specified port, then runs PRBS31 pattern
generation and monitoring at each requested PCIe generation (Gen3-Gen6).
Computes approximate BER from error counts and produces a cross-generation
comparison table.

Usage:
    python multi_gen_ber_comparison.py --device /dev/switchtec0 --port 0 --output ./results
    python multi_gen_ber_comparison.py -d /dev/switchtec0 --port 4 --gens gen3,gen4,gen5,gen6 --duration 30
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

from serialcables_switchtec.bindings.constants import (
    DiagLtssmSpeed,
    DiagPatternLinkRate,
)
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


# ── Generation configuration maps ─────────────────────────────────────

# Pattern value for PRBS31 varies by generation family.
# Gen3/Gen4 use DiagPattern enum (PRBS_31 = 3).
# Gen5 uses DiagPatternGen5 enum (PRBS_31 = 3).
# Gen6 uses DiagPatternGen6 enum (PRBS_31 = 6).
GEN_PATTERN_PRBS31: dict[str, int] = {
    "gen3": 3,
    "gen4": 3,
    "gen5": 3,
    "gen6": 6,
}

# Pattern value to disable the generator.
GEN_PATTERN_DISABLED: dict[str, int] = {
    "gen3": 6,
    "gen4": 6,
    "gen5": 10,
    "gen6": 0x1A,
}

GEN_TO_LINK_RATE: dict[str, DiagPatternLinkRate] = {
    "gen3": DiagPatternLinkRate.GEN3,
    "gen4": DiagPatternLinkRate.GEN4,
    "gen5": DiagPatternLinkRate.GEN5,
    "gen6": DiagPatternLinkRate.GEN6,
}

GEN_TO_LTSSM_SPEED: dict[str, DiagLtssmSpeed] = {
    "gen3": DiagLtssmSpeed.GEN3,
    "gen4": DiagLtssmSpeed.GEN4,
    "gen5": DiagLtssmSpeed.GEN5,
    "gen6": DiagLtssmSpeed.GEN6,
}

# Raw data rate in giga-transfers per second.
LINK_RATE_GTS: dict[str, float] = {
    "gen3": 8.0,
    "gen4": 16.0,
    "gen5": 32.0,
    "gen6": 64.0,
}

VALID_GENS = ("gen3", "gen4", "gen5", "gen6")


# ── CLI ────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross-generation BER comparison via loopback."
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
        help="Physical port ID to test",
    )
    parser.add_argument(
        "--gens",
        default="gen3,gen4,gen5",
        help="Comma-separated generations to test (default: gen3,gen4,gen5)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Soak duration per generation in seconds (default: 10)",
    )
    parser.add_argument(
        "--lanes",
        type=int,
        default=4,
        help="Number of lanes to monitor (default: 4)",
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


def _parse_gens(gens_arg: str) -> list[str]:
    """Parse and validate generation list from CLI argument."""
    result: list[str] = []
    for token in gens_arg.split(","):
        gen = token.strip().lower()
        if gen not in VALID_GENS:
            _log(f"WARNING: Unknown generation '{gen}', skipping.")
            continue
        result.append(gen)
    return result


def _format_ber(ber: float, total_bits: float = 0.0) -> str:
    """Format BER as a readable string.

    When zero errors are observed, the 90% confidence upper bound is
    2.3 / total_bits (Poisson one-sided). The bound depends on actual
    test duration and link rate, so we compute it rather than claiming
    a fixed floor like 1e-15.
    """
    if ber == 0.0:
        if total_bits > 0:
            upper_bound = 2.3 / total_bits
            return f"< {upper_bound:.1e}"
        return "0 (unknown confidence)"
    return f"{ber:.2e}"


def _ber_verdict(ber: float) -> str:
    """Determine verdict based on BER value."""
    if ber == 0.0:
        return "PASS"
    if ber < 1e-12:
        return "WARN"
    return "FAIL"


# ── Cancellable sleep ──────────────────────────────────────────────────


def _cancellable_sleep(seconds: float) -> bool:
    """Sleep in small increments. Return True if completed, False if interrupted."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        remaining = end - time.monotonic()
        time.sleep(min(remaining, 0.5))
    return True


# ── BER measurement for one generation ─────────────────────────────────


def _measure_gen(
    dev: SwitchtecDevice,
    port_id: int,
    gen: str,
    duration: int,
    lane_count: int,
) -> dict:
    """Measure BER for one generation. Returns result dict."""
    gen_upper = gen.upper()
    pattern_val = GEN_PATTERN_PRBS31[gen]
    disabled_val = GEN_PATTERN_DISABLED[gen]
    link_rate = GEN_TO_LINK_RATE[gen]
    ltssm_speed = GEN_TO_LTSSM_SPEED[gen]
    gts = LINK_RATE_GTS[gen]

    result: dict = {
        "gen": gen_upper,
        "pattern": "PRBS31",
        "lanes": lane_count,
        "duration_s": duration,
        "total_errors": 0,
        "approx_ber": 0.0,
        "gts": gts,
        "verdict": "PASS",
        "error_msg": "",
    }

    # Step 1: Enable loopback
    _log(f"  [{gen_upper}] Enabling loopback at {gen_upper} speed...")
    try:
        dev.diagnostics.loopback_set(
            port_id, enable=True, ltssm_speed=ltssm_speed
        )
    except SwitchtecError as exc:
        _log(f"  [{gen_upper}] ERROR: loopback_set failed: {exc}")
        result["verdict"] = "SKIP"
        result["error_msg"] = str(exc)
        return result

    try:
        # Step 2: Wait for link training
        _log(f"  [{gen_upper}] Waiting for link training...")
        time.sleep(1.0)

        # Step 3: Start pattern generator
        _log(f"  [{gen_upper}] Starting PRBS31 pattern generator...")
        dev.diagnostics.pattern_gen_set(port_id, pattern_val, link_rate)

        # Step 4: Start pattern monitor
        _log(f"  [{gen_upper}] Starting pattern monitor...")
        dev.diagnostics.pattern_mon_set(port_id, pattern_val)

        # Step 5: Read baseline error counts
        time.sleep(0.2)
        baseline_errors: list[int] = []
        for lane in range(lane_count):
            try:
                mon = dev.diagnostics.pattern_mon_get(port_id, lane)
                baseline_errors.append(mon.error_count)
            except SwitchtecError:
                baseline_errors.append(0)

        # Step 6: Soak
        _log(
            f"  [{gen_upper}] Soaking for {duration}s "
            f"({lane_count} lanes)..."
        )
        _cancellable_sleep(duration)

        # Step 7: Read final error counts
        total_errors = 0
        per_lane_errors: list[int] = []
        for lane in range(lane_count):
            try:
                mon = dev.diagnostics.pattern_mon_get(port_id, lane)
                delta = mon.error_count - baseline_errors[lane]
                if delta < 0:
                    delta = mon.error_count
                per_lane_errors.append(delta)
                total_errors += delta
            except SwitchtecError:
                per_lane_errors.append(0)

        # Step 8: Disable pattern generator
        _log(f"  [{gen_upper}] Disabling pattern generator...")
        try:
            dev.diagnostics.pattern_gen_set(
                port_id, disabled_val, DiagPatternLinkRate.DISABLED
            )
        except SwitchtecError:
            pass

        # Step 9: Compute BER
        # BER = total_errors / (rate_gts * 1e9 * duration * lanes)
        # NOTE: For Gen6 PAM4, LINK_RATE_GTS uses 64 GT/s (the data rate).
        # If the pattern monitor counts symbol errors rather than bit errors,
        # the denominator should use 32 GBaud (symbol rate) instead.
        # This approximation uses the data rate for all generations.
        total_bits = gts * 1e9 * duration * lane_count
        approx_ber = total_errors / total_bits if total_bits > 0 else 0.0

        result["total_errors"] = total_errors
        result["approx_ber"] = approx_ber
        result["total_bits"] = total_bits
        result["verdict"] = _ber_verdict(approx_ber)

        # Per-lane detail
        lane_detail = ", ".join(
            f"L{i}={e}" for i, e in enumerate(per_lane_errors)
        )
        _log(
            f"  [{gen_upper}] PRBS31: {total_errors} errors, "
            f"BER {_format_ber(approx_ber, total_bits)} [{lane_detail}]"
        )

    except SwitchtecError as exc:
        _log(f"  [{gen_upper}] ERROR during measurement: {exc}")
        result["verdict"] = "SKIP"
        result["error_msg"] = str(exc)
    finally:
        # Always disable loopback
        _log(f"  [{gen_upper}] Disabling loopback...")
        try:
            dev.diagnostics.loopback_set(port_id, enable=False)
        except SwitchtecError as exc:
            _log(f"  [{gen_upper}] WARNING: loopback disable failed: {exc}")

    return result


# ── CSV output ─────────────────────────────────────────────────────────


_CSV_FIELDS = [
    "gen",
    "pattern",
    "lanes",
    "duration_s",
    "total_errors",
    "approx_ber",
]


def _write_csv(results: list[dict], filepath: Path) -> None:
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


# ── Terminal comparison table ──────────────────────────────────────────


def _print_comparison(results: list[dict], port_id: int) -> None:
    """Print a formatted comparison table."""
    print(f"\nCross-Generation BER Comparison (Port {port_id}, PRBS31)")
    sep = "-" * 68
    print(sep)
    print(
        f"{'Gen':>6} | {'Rate':>8} | {'Errors':>8} | "
        f"{'BER (approx)':>14} | {'Verdict':>7}"
    )
    print(sep)

    for r in results:
        if r["verdict"] == "SKIP":
            print(
                f"{r['gen']:>6} | {'N/A':>8} | {'N/A':>8} | "
                f"{'SKIPPED':>14} | {'SKIP':>7}"
            )
            continue

        gts = r["gts"]
        rate_str = f"{gts:>4.0f} GT/s"
        errors_str = str(r["total_errors"])
        ber_str = _format_ber(r["approx_ber"], r.get("total_bits", 0.0))

        print(
            f"{r['gen']:>6} | {rate_str:>8} | {errors_str:>8} | "
            f"{ber_str:>14} | {r['verdict']:>7}"
        )

    print(sep)

    # Overall verdict
    active = [r for r in results if r["verdict"] != "SKIP"]
    if active:
        worst = max(active, key=lambda r: r["approx_ber"])
        if worst["approx_ber"] == 0.0:
            print("Overall: All generations error-free.")
        else:
            print(
                f"Overall: Worst BER at {worst['gen']} = "
                f"{_format_ber(worst['approx_ber'], worst.get('total_bits', 0.0))}"
            )
    else:
        print("Overall: All generations skipped.")
    print()


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    gens = _parse_gens(args.gens)
    if not gens:
        _log("ERROR: No valid generations specified.")
        sys.exit(2)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        _log(
            f"Port {args.port}, Generations: {', '.join(g.upper() for g in gens)}, "
            f"Duration: {args.duration}s/gen, Lanes: {args.lanes}"
        )

        # Confirmation prompt — loopback takes port offline
        if not args.yes and sys.stdin.isatty():
            response = input(
                f"\nWARNING: This will enable loopback mode on port {args.port}.\n"
                f"The port will be taken offline and any live traffic will be dropped.\n"
                f"Generations to test: {', '.join(g.upper() for g in gens)}\n"
                f"Continue? [y/N]: "
            )
            if response.lower() != "y":
                _log("Aborted.")
                dev.close()
                sys.exit(0)

        results: list[dict] = []
        for gen_idx, gen in enumerate(gens):
            _log(
                f"\n[{gen_idx + 1}/{len(gens)}] "
                f"Testing {gen.upper()}..."
            )
            result = _measure_gen(
                dev, args.port, gen, args.duration, args.lanes
            )
            results.append(result)

            # Brief pause between generations
            if gen_idx < len(gens) - 1:
                _log("  Waiting 2s before next generation...")
                time.sleep(2.0)

        # Write CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ber_comparison_{timestamp}.csv"
        filepath = output_dir / filename
        _write_csv(results, filepath)
        _log(f"\nCSV written to {filepath}")

        # Print comparison table
        _print_comparison(results, args.port)

    except KeyboardInterrupt:
        _log("\nInterrupted by user. Cleaning up...")
        # Disable pattern gen and loopback on interrupt
        try:
            gen = gens[0] if gens else "gen4"
            disabled_val = GEN_PATTERN_DISABLED.get(gen, 6)
            dev.diagnostics.pattern_gen_set(
                args.port, disabled_val, DiagPatternLinkRate.DISABLED
            )
        except SwitchtecError:
            pass
        try:
            dev.diagnostics.loopback_set(args.port, enable=False)
        except SwitchtecError:
            pass
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
