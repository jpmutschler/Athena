#!/usr/bin/env python3
"""Generate a comprehensive first-power-on HTML acceptance report.

Reads device summary, firmware partitions, port status, and equalization
data from a Switchtec Gen6 switch and produces a self-contained HTML
report with inline CSS (dark theme) suitable for lab review.

Usage:
    python board_bringup_report.py --device /dev/switchtec0 --output ./results
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate board bring-up acceptance report (HTML)."
    )
    parser.add_argument("--device", "-d", default="/dev/switchtec0", help="Device path")
    parser.add_argument("--output", "-o", default=".", help="Output directory")
    return parser.parse_args()


# ── Data collection ────────────────────────────────────────────────────


def _collect_summary(dev: SwitchtecDevice) -> dict:
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


def _collect_firmware(dev: SwitchtecDevice) -> dict:
    _log("Reading firmware info...")
    fw_version = dev.firmware.get_fw_version()
    part_summary = dev.firmware.get_part_summary()
    boot_ro = dev.firmware.is_boot_ro()

    partitions: dict[str, dict] = {}
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

    return {
        "version": fw_version,
        "boot_ro": boot_ro,
        "partitions": partitions,
    }


def _collect_ports(dev: SwitchtecDevice) -> list[dict]:
    _log("Reading port status...")
    ports = dev.get_status()
    results: list[dict] = []
    for p in ports:
        results.append(
            {
                "phys_id": p.port.phys_id,
                "link_up": p.link_up,
                "link_rate": p.link_rate,
                "cfg_lnk_width": p.cfg_lnk_width,
                "neg_lnk_width": p.neg_lnk_width,
                "ltssm_str": p.ltssm_str,
                "pci_bdf": p.pci_bdf or "",
                "width_degraded": p.link_up and p.neg_lnk_width < p.cfg_lnk_width,
            }
        )
    return results


def _collect_equalization(dev: SwitchtecDevice, ports: list[dict]) -> dict[int, dict]:
    eq_data: dict[int, dict] = {}
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
            _log(f"  WARNING: EQ coeff read failed on port {port_id}: {exc}")
            entry["cursors"] = []

        try:
            fslf = dev.diagnostics.port_eq_tx_fslf(port_id, lane_id=0)
            entry["fslf"] = {"fs": fslf.fs, "lf": fslf.lf}
        except SwitchtecError as exc:
            _log(f"  WARNING: FS/LF read failed on port {port_id}: {exc}")
            entry["fslf"] = None

        eq_data[port_id] = entry
    return eq_data


# ── HTML generation ────────────────────────────────────────────────────

_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: 'Consolas', 'Courier New', monospace; padding: 24px; }
h1 { color: #00d4ff; margin-bottom: 8px; }
h2 { color: #00d4ff; margin: 24px 0 12px 0; border-bottom: 1px solid #333; padding-bottom: 4px; }
h3 { color: #7ec8e3; margin: 16px 0 8px 0; }
.meta { color: #888; font-size: 0.9em; margin-bottom: 16px; }
table { border-collapse: collapse; margin: 8px 0 16px 0; width: 100%; }
th, td { border: 1px solid #333; padding: 6px 10px; text-align: left; font-size: 0.85em; }
th { background: #16213e; color: #00d4ff; }
td { background: #0f3460; }
.ok { color: #00ff88; font-weight: bold; }
.warn { color: #ffaa00; font-weight: bold; }
.fail { color: #ff4444; font-weight: bold; }
.up { color: #00ff88; }
.down { color: #ff4444; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 12px 0; }
.summary-card { background: #16213e; border: 1px solid #333; border-radius: 6px; padding: 12px; text-align: center; }
.summary-card .value { font-size: 1.6em; color: #00d4ff; }
.summary-card .label { font-size: 0.8em; color: #888; }
"""


def _esc(text: object) -> str:
    return html.escape(str(text))


def _build_header(summary: dict, timestamp: str) -> str:
    return (
        f"<h1>Board Bring-Up Report</h1>\n"
        f'<p class="meta">{_esc(summary["name"])} &mdash; '
        f"{_esc(summary['generation'])} {_esc(summary['variant'])} &mdash; "
        f"FW {_esc(summary['fw_version'])} &mdash; {_esc(timestamp)}</p>\n"
    )


def _build_summary_cards(summary: dict, ports: list[dict]) -> str:
    up_count = sum(1 for p in ports if p["link_up"])
    down_count = len(ports) - up_count
    degraded = sum(1 for p in ports if p["width_degraded"])
    cards = [
        ("Total Ports", str(summary["port_count"])),
        ("Ports UP", str(up_count)),
        ("Ports DOWN", str(down_count)),
        ("Width Degraded", str(degraded)),
        ("Temperature", f"{summary['die_temperature']:.1f} C"),
        ("Boot Phase", summary["boot_phase"]),
    ]
    lines = ['<div class="summary-grid">']
    for label, value in cards:
        lines.append(
            f'<div class="summary-card">'
            f'<div class="value">{_esc(value)}</div>'
            f'<div class="label">{_esc(label)}</div></div>'
        )
    lines.append("</div>")
    return "\n".join(lines)


def _build_firmware_section(fw: dict) -> str:
    lines = ["<h2>Firmware</h2>"]
    lines.append(
        f"<p>Version: <strong>{_esc(fw['version'])}</strong> &mdash; "
        f"Boot RO: <strong>{_esc(fw['boot_ro'])}</strong></p>"
    )
    if fw["partitions"]:
        lines.append(
            "<table><tr><th>Partition</th><th>Slot</th>"
            "<th>Version</th><th>Valid</th><th>Active</th>"
            "<th>Running</th><th>Read-Only</th></tr>"
        )
        for part_name, slots in fw["partitions"].items():
            for slot_name, img in slots.items():
                valid_cls = "ok" if img["valid"] else "fail"
                lines.append(
                    f"<tr><td>{_esc(part_name)}</td>"
                    f"<td>{_esc(slot_name)}</td>"
                    f"<td>{_esc(img['version'])}</td>"
                    f'<td class="{valid_cls}">{_esc(img["valid"])}</td>'
                    f"<td>{_esc(img['active'])}</td>"
                    f"<td>{_esc(img['running'])}</td>"
                    f"<td>{_esc(img['read_only'])}</td></tr>"
                )
        lines.append("</table>")
    return "\n".join(lines)


def _link_rate_str(rate: int) -> str:
    rate_map = {1: "2.5 GT/s", 2: "5 GT/s", 3: "8 GT/s", 4: "16 GT/s", 5: "32 GT/s", 6: "64 GT/s"}
    return rate_map.get(rate, f"{rate}")


def _build_port_table(ports: list[dict]) -> str:
    lines = ["<h2>Port Status</h2>"]
    lines.append(
        "<table><tr><th>Port</th><th>Link</th><th>Rate</th>"
        "<th>Cfg Width</th><th>Neg Width</th><th>Width Match</th>"
        "<th>LTSSM</th><th>BDF</th></tr>"
    )
    for p in ports:
        link_cls = "up" if p["link_up"] else "down"
        link_txt = "UP" if p["link_up"] else "DOWN"
        rate_txt = _link_rate_str(p["link_rate"]) if p["link_up"] else "-"
        neg_txt = str(p["neg_lnk_width"]) if p["link_up"] else "-"
        if not p["link_up"]:
            match_cls, match_txt = "", "-"
        elif p["width_degraded"]:
            match_cls, match_txt = "fail", "DEGRADED"
        else:
            match_cls, match_txt = "ok", "OK"
        lines.append(
            f"<tr><td>{p['phys_id']}</td>"
            f'<td class="{link_cls}">{link_txt}</td>'
            f"<td>{_esc(rate_txt)}</td>"
            f"<td>x{p['cfg_lnk_width']}</td>"
            f"<td>x{_esc(neg_txt)}</td>"
            f'<td class="{match_cls}">{match_txt}</td>'
            f"<td>{_esc(p['ltssm_str'])}</td>"
            f"<td>{_esc(p['pci_bdf'])}</td></tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)


def _build_eq_section(eq_data: dict[int, dict]) -> str:
    if not eq_data:
        return "<h2>Equalization</h2><p>No active ports to report.</p>"
    lines = ["<h2>Equalization</h2>"]
    for port_id in sorted(eq_data):
        entry = eq_data[port_id]
        fslf = entry.get("fslf")
        fslf_str = f"FS={fslf['fs']}, LF={fslf['lf']}" if fslf else "N/A"
        lines.append(f"<h3>Port {port_id} (FS/LF: {_esc(fslf_str)})</h3>")
        cursors = entry.get("cursors", [])
        if cursors:
            lines.append("<table><tr><th>Lane</th><th>Pre</th><th>Post</th></tr>")
            for c in cursors:
                lines.append(
                    f"<tr><td>{c['lane']}</td><td>{c['pre']}</td><td>{c['post']}</td></tr>"
                )
            lines.append("</table>")
        else:
            lines.append("<p>No cursor data available.</p>")
    return "\n".join(lines)


def _generate_html(
    summary: dict,
    fw: dict,
    ports: list[dict],
    eq_data: dict[int, dict],
    timestamp: str,
) -> str:
    parts = [
        "<!DOCTYPE html><html lang='en'><head>",
        "<meta charset='UTF-8'>",
        f"<title>Bring-Up Report - {_esc(summary['name'])}</title>",
        f"<style>{_CSS}</style>",
        "</head><body>",
        _build_header(summary, timestamp),
        _build_summary_cards(summary, ports),
        _build_firmware_section(fw),
        _build_port_table(ports),
        _build_eq_section(eq_data),
        "<hr style='margin-top:32px;border-color:#333'>",
        '<p class="meta">Generated by board_bringup_report.py</p>',
        "</body></html>",
    ]
    return "\n".join(parts)


# ── Terminal summary ───────────────────────────────────────────────────


def _print_terminal_summary(summary: dict, ports: list[dict], eq_data: dict[int, dict]) -> None:
    up = sum(1 for p in ports if p["link_up"])
    degraded = sum(1 for p in ports if p["width_degraded"])
    print(f"\n{'=' * 60}")
    print(f"  BRING-UP SUMMARY: {summary['name']}")
    print(
        f"  {summary['generation']} {summary['variant']}  "
        f"FW {summary['fw_version']}  "
        f"Temp {summary['die_temperature']:.1f} C"
    )
    print(f"{'=' * 60}")
    print(
        f"  Ports: {len(ports)} total, {up} UP, {len(ports) - up} DOWN, {degraded} width-degraded"
    )
    print(f"  EQ data collected for {len(eq_data)} active ports")
    if degraded:
        print(f"\n  WARNING: {degraded} port(s) have width degradation!")
        for p in ports:
            if p["width_degraded"]:
                print(
                    f"    Port {p['phys_id']}: "
                    f"cfg x{p['cfg_lnk_width']} / "
                    f"neg x{p['neg_lnk_width']}"
                )
    print(f"{'=' * 60}\n")


# ── Utility ────────────────────────────────────────────────────────────


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ── Main ───────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _log(f"Opening device {args.device}...")
    dev = SwitchtecDevice.open(args.device)
    try:
        summary = _collect_summary(dev)
        fw = _collect_firmware(dev)
        ports = _collect_ports(dev)
        eq_data = _collect_equalization(dev, ports)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        html_content = _generate_html(summary, fw, ports, eq_data, timestamp)

        filename = datetime.now().strftime("bringup_report_%Y%m%d_%H%M%S.html")
        filepath = output_dir / filename
        filepath.write_text(html_content, encoding="utf-8")

        _print_terminal_summary(summary, ports, eq_data)
        _log(f"Report written to {filepath}")
    except KeyboardInterrupt:
        _log("\nInterrupted by user.")
        sys.exit(130)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
