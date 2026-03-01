#!/usr/bin/env python3
"""Audit all ports against expected topology for speed/width regression.

Compares current link state against an optional expected-topology JSON
file. Produces a CSV report and a terminal table with per-port verdicts:
MATCH, DEGRADED, DOWN, or EXTRA.

Usage:
    python link_width_rate_audit.py --device /dev/switchtec0 --output ./results
    python link_width_rate_audit.py -d /dev/switchtec0 --topology expected.json --strict
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice

# Map numeric link_rate to human-readable string
_RATE_MAP: dict[int, str] = {
    1: "2.5 GT/s",
    2: "5 GT/s",
    3: "8 GT/s",
    4: "16 GT/s",
    5: "32 GT/s",
    6: "64 GT/s",
}

# Reverse: human-readable string back to numeric
_RATE_REVERSE: dict[str, int] = {v: k for k, v in _RATE_MAP.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit port link width and rate against expected topology."
    )
    parser.add_argument("--device", "-d", default="/dev/switchtec0", help="Device path")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    parser.add_argument(
        "--topology",
        "-t",
        default=None,
        help="Path to expected topology JSON file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 on any DEGRADED or DOWN verdict",
    )
    return parser.parse_args()


def _rate_str(rate: int) -> str:
    return _RATE_MAP.get(rate, str(rate))


def _rate_from_str(rate_str: str) -> int:
    return _RATE_REVERSE.get(rate_str, -1)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ── Topology loading ───────────────────────────────────────────────────


def _load_topology(path: Path) -> dict[int, dict]:
    """Load expected topology JSON and index by port_id."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected_list = raw.get("expected", [])
    indexed: dict[int, dict] = {}
    for entry in expected_list:
        port_id = entry["port_id"]
        indexed[port_id] = {
            "gen": entry.get("gen", ""),
            "width": entry.get("width", 0),
        }
    return indexed


# ── Audit logic ────────────────────────────────────────────────────────


def _audit_ports(ports: list[dict], topology: dict[int, dict] | None) -> list[dict]:
    """Compare actual port state against expected topology.

    Returns list of audit rows with verdict.
    """
    results: list[dict] = []
    seen_ids: set[int] = set()

    for p in ports:
        port_id = p["phys_id"]
        seen_ids.add(port_id)
        actual_gen = _rate_str(p["link_rate"]) if p["link_up"] else "DOWN"
        actual_width = p["neg_lnk_width"] if p["link_up"] else 0

        if topology is None or port_id not in topology:
            verdict = "EXTRA" if (topology is not None and p["link_up"]) else "INFO"
            results.append(
                {
                    "port_id": port_id,
                    "expected_gen": "-",
                    "actual_gen": actual_gen,
                    "expected_width": "-",
                    "actual_width": actual_width if p["link_up"] else "-",
                    "link_up": p["link_up"],
                    "verdict": verdict,
                }
            )
            continue

        exp = topology[port_id]
        exp_gen = exp["gen"]
        exp_width = exp["width"]

        if not p["link_up"]:
            verdict = "DOWN"
        elif actual_gen == exp_gen and actual_width == exp_width:
            verdict = "MATCH"
        else:
            gen_ok = actual_gen == exp_gen
            width_ok = actual_width == exp_width
            if not gen_ok or not width_ok:
                verdict = "DEGRADED"
            else:
                verdict = "MATCH"

        results.append(
            {
                "port_id": port_id,
                "expected_gen": exp_gen,
                "actual_gen": actual_gen,
                "expected_width": exp_width,
                "actual_width": actual_width if p["link_up"] else 0,
                "link_up": p["link_up"],
                "verdict": verdict,
            }
        )

    # Ports expected but not seen in device status
    if topology is not None:
        for port_id in sorted(topology):
            if port_id not in seen_ids:
                exp = topology[port_id]
                results.append(
                    {
                        "port_id": port_id,
                        "expected_gen": exp["gen"],
                        "actual_gen": "MISSING",
                        "expected_width": exp["width"],
                        "actual_width": 0,
                        "link_up": False,
                        "verdict": "DOWN",
                    }
                )

    results.sort(key=lambda r: r["port_id"])
    return results


# ── Output ─────────────────────────────────────────────────────────────

_VERDICT_SYMBOLS: dict[str, str] = {
    "MATCH": "  OK ",
    "DEGRADED": " WARN",
    "DOWN": " FAIL",
    "EXTRA": " NOTE",
    "INFO": " INFO",
}


def _print_terminal_table(results: list[dict]) -> None:
    header = (
        f"{'Port':>6}  {'ExpGen':>10}  {'ActGen':>10}  "
        f"{'ExpW':>5}  {'ActW':>5}  {'Link':>5}  {'Verdict':>8}"
    )
    sep = "-" * len(header)
    print(f"\n{sep}")
    print(header)
    print(sep)
    for r in results:
        exp_w = str(r["expected_width"])
        act_w = str(r["actual_width"])
        link = "UP" if r["link_up"] else "DOWN"
        symbol = _VERDICT_SYMBOLS.get(r["verdict"], "     ")
        print(
            f"{r['port_id']:>6}  {str(r['expected_gen']):>10}  "
            f"{str(r['actual_gen']):>10}  "
            f"{exp_w:>5}  {act_w:>5}  {link:>5}  "
            f"{symbol} {r['verdict']}"
        )
    print(sep)

    # Tally
    counts: dict[str, int] = {}
    for r in results:
        v = r["verdict"]
        counts[v] = counts.get(v, 0) + 1
    parts = [f"{v}: {c}" for v, c in sorted(counts.items())]
    print(f"  Totals: {', '.join(parts)}")
    print()


def _write_csv(results: list[dict], filepath: Path) -> None:
    fieldnames = [
        "port_id",
        "expected_gen",
        "actual_gen",
        "expected_width",
        "actual_width",
        "link_up",
        "verdict",
    ]
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


# ── Collect port data ──────────────────────────────────────────────────


def _collect_ports(dev: SwitchtecDevice) -> list[dict]:
    statuses = dev.get_status()
    return [
        {
            "phys_id": s.port.phys_id,
            "link_up": s.link_up,
            "link_rate": s.link_rate,
            "cfg_lnk_width": s.cfg_lnk_width,
            "neg_lnk_width": s.neg_lnk_width,
            "ltssm_str": s.ltssm_str,
        }
        for s in statuses
    ]


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    topology: dict[int, dict] | None = None
    if args.topology:
        topo_path = Path(args.topology)
        if not topo_path.exists():
            _log(f"ERROR: Topology file not found: {topo_path}")
            sys.exit(2)
        _log(f"Loading topology from {topo_path}...")
        topology = _load_topology(topo_path)
        _log(f"  {len(topology)} expected port entries loaded.")

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        ports = _collect_ports(dev)
        _log(f"  {len(ports)} ports discovered.")
    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()

    results = _audit_ports(ports, topology)
    _print_terminal_table(results)

    filename = datetime.now().strftime("audit_%Y%m%d_%H%M%S.csv")
    filepath = output_dir / filename
    _write_csv(results, filepath)
    _log(f"CSV written to {filepath}")

    # Exit code logic
    if args.strict and topology is not None:
        failures = sum(1 for r in results if r["verdict"] in ("DEGRADED", "DOWN"))
        if failures > 0:
            _log(f"STRICT MODE: {failures} port(s) with DEGRADED or DOWN verdict.")
            sys.exit(1)


if __name__ == "__main__":
    main()
