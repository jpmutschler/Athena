"""Margin Testing page -- dedicated cross-hair lane margining dashboard.

PAM4-first design: defaults, colorscales, thresholds, and labels are
calibrated for Gen6 (64 GT/s, PAM4) validation.  NRZ generations
(Gen3-5) are fully supported via the generation selector.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from nicegui import run, ui

from serialcables_switchtec.bindings.constants import (
    DiagCrossHairState,
    SwitchtecGen,
)
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.diagnostics import CrossHairResult
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.margin_diamond import margin_diamond
from serialcables_switchtec.ui.components.margin_heatmap import (
    build_margin_csv,
    build_margin_json,
    margin_heatmap_pair,
)
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

# ── Generation-aware thresholds (from core/workflows/cross_hair_margin.py) ──

_MARGIN_THRESHOLDS: dict[str, dict] = {
    "gen6": {"h_warn": 7, "v_warn": 10, "is_pam4": True, "label": "Gen6 (64 GT/s, PAM4)"},
    "gen5": {"h_warn": 20, "v_warn": 30, "is_pam4": False, "label": "Gen5 (32 GT/s, NRZ)"},
    "gen4": {"h_warn": 25, "v_warn": 35, "is_pam4": False, "label": "Gen4 (16 GT/s, NRZ)"},
    "gen3": {"h_warn": 30, "v_warn": 40, "is_pam4": False, "label": "Gen3 (8 GT/s, NRZ)"},
    # Custom: is_pam4 defaults to False; auto-detect overrides if device is Gen6
    "custom": {"h_warn": 20, "v_warn": 30, "is_pam4": False, "label": "Custom"},
}

_GEN_SELECT_OPTIONS: dict[str, str] = {
    "gen6": "Gen6 (64 GT/s, PAM4)",
    "gen5": "Gen5 (32 GT/s, NRZ)",
    "gen4": "Gen4 (16 GT/s, NRZ)",
    "gen3": "Gen3 (8 GT/s, NRZ)",
    "custom": "Custom",
}

_GEN_FROM_SWITCHTEC: dict[SwitchtecGen, str] = {
    SwitchtecGen.GEN3: "gen3",
    SwitchtecGen.GEN4: "gen4",
    SwitchtecGen.GEN5: "gen5",
    SwitchtecGen.GEN6: "gen6",
}


# ── Pure helper functions (testable without UI) ───────────────────────


def _resolve_thresholds(
    gen_key: str,
    custom_h: int | None = None,
    custom_v: int | None = None,
) -> dict:
    """Return ``{h_warn, v_warn, is_pam4}`` for the given generation key."""
    base = _MARGIN_THRESHOLDS.get(gen_key, _MARGIN_THRESHOLDS["gen5"])
    h = custom_h if (gen_key == "custom" and custom_h is not None) else base["h_warn"]
    v = custom_v if (gen_key == "custom" and custom_v is not None) else base["v_warn"]
    return {"h_warn": h, "v_warn": v, "is_pam4": base["is_pam4"]}


def _build_row(
    port_id: int,
    lane_id: int,
    lane_offset: int,
    ch: object,
    h_warn: int,
    v_warn: int,
    is_pam4: bool,
) -> dict:
    """Compute a single lane margin row from a CrossHairResult.

    Verdict logic: both margins must meet threshold for PASS.  Non-zero
    margins below threshold are MARGINAL.  Zero or negative on either
    axis (collapsed eye) is FAIL.
    """
    h_margin = ch.eye_left_lim + ch.eye_right_lim
    v_top = min(ch.eye_top_left_lim, ch.eye_top_right_lim)
    v_bot = min(ch.eye_bot_left_lim, ch.eye_bot_right_lim)
    v_margin = v_top + v_bot

    h_pass = h_margin >= h_warn
    v_pass = v_margin >= v_warn
    if h_pass and v_pass:
        verdict = "PASS"
    elif h_margin > 0 and v_margin > 0:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    return {
        "port_id": port_id,
        "lane_index": lane_offset,
        "lane_id": lane_id,
        "h_margin": h_margin,
        "v_margin": v_margin,
        "verdict": verdict,
        "signaling": "PAM4" if is_pam4 else "NRZ",
        "eye_left_lim": ch.eye_left_lim,
        "eye_right_lim": ch.eye_right_lim,
        "eye_top_left_lim": ch.eye_top_left_lim,
        "eye_top_right_lim": ch.eye_top_right_lim,
        "eye_bot_left_lim": ch.eye_bot_left_lim,
        "eye_bot_right_lim": ch.eye_bot_right_lim,
    }


def _error_row(
    port_id: int,
    lane_id: int,
    lane_offset: int,
    is_pam4: bool,
) -> dict:
    """Return a FAIL row with zero margins for a lane that errored/timed out."""
    return {
        "port_id": port_id,
        "lane_index": lane_offset,
        "lane_id": lane_id,
        "h_margin": 0,
        "v_margin": 0,
        "verdict": "FAIL",
        "signaling": "PAM4" if is_pam4 else "NRZ",
        "eye_left_lim": 0,
        "eye_right_lim": 0,
        "eye_top_left_lim": 0,
        "eye_top_right_lim": 0,
        "eye_bot_left_lim": 0,
        "eye_bot_right_lim": 0,
    }


def _build_heatmap_grids(
    rows: list[dict],
) -> tuple[list[int], int, list[list[float | None]], list[list[float | None]]]:
    """Group rows by port and build H/V margin grids for heatmap rendering.

    Returns:
        (port_ids, max_lanes, h_grid, v_grid)
    """
    port_rows: dict[int, list[dict]] = {}
    for row in rows:
        port_rows.setdefault(row["port_id"], []).append(row)

    port_ids = sorted(port_rows.keys())
    max_lanes = max(len(pr) for pr in port_rows.values())

    h_grid: list[list[float | None]] = []
    v_grid: list[list[float | None]] = []
    for pid in port_ids:
        h_row: list[float | None] = [None] * max_lanes
        v_row: list[float | None] = [None] * max_lanes
        for row in port_rows[pid]:
            idx = row["lane_index"]
            if idx < max_lanes:
                h_row[idx] = row["h_margin"]
                v_row[idx] = row["v_margin"]
        h_grid.append(h_row)
        v_grid.append(v_row)

    return port_ids, max_lanes, h_grid, v_grid


# ── Sweep state ───────────────────────────────────────────────────────


@dataclass
class _SweepState:
    running: bool = False
    cancelled: bool = False
    rows: list[dict] = field(default_factory=list)
    thresholds: dict = field(default_factory=dict)


# ── Page ──────────────────────────────────────────────────────────────


def margin_testing_page() -> None:
    """Render the Margin Testing page."""
    from serialcables_switchtec.ui import state

    with page_layout(title="Margin Testing", current_path="/margin"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Margin Testing").classes("text-h5 q-mb-md")

        # ── Warning banner ────────────────────────────────────────
        with ui.card().classes("w-full q-pa-sm q-mb-md").style(
            f"border-left: 4px solid {COLORS.warning};"
        ):
            with ui.row().classes("items-center q-gutter-sm"):
                ui.icon("warning").style(f"color: {COLORS.warning};")
                ui.label(
                    "Cross-hair measurement temporarily affects lanes under test. "
                    "Do not run on production traffic."
                ).style(f"color: {COLORS.text_secondary};")

        # ── PAM4 info banner (toggled by generation) ──────────────
        pam4_banner = ui.card().classes("w-full q-pa-sm q-mb-md").style(
            f"border-left: 4px solid {COLORS.blue};"
        )
        with pam4_banner:
            with ui.row().classes("items-center q-gutter-sm"):
                ui.icon("info").style(f"color: {COLORS.blue};")
                ui.label(
                    "PAM4 signaling (Gen6): Margins are measured across 3 sub-eyes. "
                    "Expected values are ~1/3 of NRZ \u2014 passing thresholds: "
                    "H\u22657, V\u226510."
                ).style(f"color: {COLORS.text_secondary};")

        # ── Section 1: Configuration card ─────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Sweep Configuration").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                port_mode = ui.toggle(
                    {"all": "All Active Ports", "single": "Single Port"},
                    value="all",
                ).props("dense")
                single_port_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                single_port_input.set_visibility(False)

            def _on_port_mode_change() -> None:
                single_port_input.set_visibility(port_mode.value == "single")

            port_mode.on_value_change(lambda _: _on_port_mode_change())

            ui.separator().classes("q-my-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                gen_select = ui.select(
                    options=_GEN_SELECT_OPTIONS,
                    label="Generation",
                    value="gen6",
                ).classes("w-48")

                custom_h_input = ui.number(
                    label="H Threshold", value=20, min=0, max=200,
                ).classes("w-28")
                custom_v_input = ui.number(
                    label="V Threshold", value=30, min=0, max=200,
                ).classes("w-28")
                custom_h_input.set_visibility(False)
                custom_v_input.set_visibility(False)

                timeout_input = ui.number(
                    label="Timeout/lane (s)", value=15, min=1, max=120,
                ).classes("w-32")

            def _on_gen_change() -> None:
                is_custom = gen_select.value == "custom"
                custom_h_input.set_visibility(is_custom)
                custom_v_input.set_visibility(is_custom)
                pam4_banner.set_visibility(gen_select.value == "gen6")

            gen_select.on_value_change(lambda _: _on_gen_change())

            # Auto-detect generation from device
            async def _auto_detect_gen() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                try:
                    gen = await run.io_bound(lambda: dev.generation)
                    key = _GEN_FROM_SWITCHTEC.get(gen)
                    if key is not None:
                        gen_select.set_value(key)
                except (SwitchtecError, OSError):
                    pass

            ui.timer(0.1, _auto_detect_gen, once=True)

            ui.separator().classes("q-my-sm")

            with ui.row().classes("q-gutter-sm"):
                start_btn = ui.button(
                    "Start Sweep", icon="play_arrow",
                ).props("color=positive")
                cancel_btn = ui.button(
                    "Cancel", icon="stop",
                ).props("color=negative")
                cancel_btn.set_enabled(False)

        # ── Section 2: Progress card (hidden until sweep) ─────────
        progress_card = ui.card().classes("w-full q-pa-md q-mb-md")
        progress_card.set_visibility(False)
        with progress_card:
            progress_label = ui.label("Preparing sweep...").classes(
                "text-subtitle2 q-mb-sm"
            )
            progress_bar = ui.linear_progress(value=0, show_value=False).props(
                "color=positive"
            )

        # ── Section 3-5: Result containers ────────────────────────
        heatmap_container = ui.column().classes("w-full q-mb-md")
        diamond_container = ui.column().classes("w-full q-mb-md")
        table_container = ui.column().classes("w-full q-mb-md")

        # ── Section 6: Export ─────────────────────────────────────
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Export").classes("text-h6 q-mb-sm")
            with ui.row().classes("q-gutter-sm"):
                export_csv_btn = ui.button(
                    "Export CSV", icon="download",
                ).props("flat")
                export_json_btn = ui.button(
                    "Export JSON", icon="download",
                ).props("flat")

        # ── Sweep state ───────────────────────────────────────────

        sweep = _SweepState()

        # ── Export handlers ───────────────────────────────────────

        def _on_export_csv() -> None:
            if not sweep.rows:
                ui.notify("No margin data to export", type="warning", position="top")
                return
            ui.download(build_margin_csv(sweep.rows), "margin_sweep.csv")

        def _on_export_json() -> None:
            if not sweep.rows:
                ui.notify("No margin data to export", type="warning", position="top")
                return
            ui.download(
                build_margin_json(sweep.rows, sweep.thresholds),
                "margin_sweep.json",
            )

        export_csv_btn.on_click(_on_export_csv)
        export_json_btn.on_click(_on_export_json)

        # ── Result rendering (split into focused sub-functions) ───

        def _render_heatmap_section(
            rows: list[dict], h_warn: int, v_warn: int, is_pam4: bool,
        ) -> None:
            port_ids, max_lanes, h_grid, v_grid = _build_heatmap_grids(rows)
            heatmap_container.clear()
            with heatmap_container:
                with ui.card().classes("w-full q-pa-md"):
                    ui.label("Margin Heatmap").classes("text-h6 q-mb-sm")
                    margin_heatmap_pair(
                        port_ids=port_ids,
                        max_lane_count=max_lanes,
                        h_grid=h_grid,
                        v_grid=v_grid,
                        h_thresh=h_warn,
                        v_thresh=v_warn,
                        is_pam4=is_pam4,
                    )

        def _render_diamond_section(rows: list[dict]) -> None:
            port_rows: dict[int, list[dict]] = {}
            for row in rows:
                port_rows.setdefault(row["port_id"], []).append(row)

            diamond_container.clear()
            with diamond_container:
                with ui.card().classes("w-full q-pa-md"):
                    ui.label("Margin Diamond Plots").classes("text-h6 q-mb-sm")
                    for pid in sorted(port_rows.keys()):
                        ui.label(f"Port {pid}").classes(
                            "text-subtitle1 q-mt-sm"
                        ).style(f"color: {COLORS.text_primary};")
                        ch_results = [
                            CrossHairResult(
                                lane_id=r["lane_id"],
                                state=DiagCrossHairState.DONE,
                                state_name="DONE",
                                eye_left_lim=r["eye_left_lim"],
                                eye_right_lim=r["eye_right_lim"],
                                eye_top_left_lim=r["eye_top_left_lim"],
                                eye_top_right_lim=r["eye_top_right_lim"],
                                eye_bot_left_lim=r["eye_bot_left_lim"],
                                eye_bot_right_lim=r["eye_bot_right_lim"],
                            )
                            for r in port_rows[pid]
                            if r["h_margin"] > 0 or r["v_margin"] > 0
                        ]
                        if ch_results:
                            margin_diamond(ch_results)
                        else:
                            ui.label("No valid margin data").style(
                                f"color: {COLORS.text_muted};"
                            )

        def _render_table_section(rows: list[dict]) -> None:
            table_container.clear()
            with table_container:
                with ui.card().classes("w-full q-pa-md"):
                    ui.label("Margin Results").classes("text-h6 q-mb-sm")
                    columns = [
                        {"name": "port_id", "label": "Port", "field": "port_id", "align": "center"},
                        {"name": "lane_id", "label": "Lane", "field": "lane_id", "align": "center"},
                        {"name": "h_margin", "label": "H Margin", "field": "h_margin", "align": "right"},
                        {"name": "v_margin", "label": "V Margin", "field": "v_margin", "align": "right"},
                        {"name": "verdict", "label": "Verdict", "field": "verdict", "align": "center"},
                        {"name": "signaling", "label": "Signaling", "field": "signaling", "align": "center"},
                        {"name": "eye_left_lim", "label": "Left", "field": "eye_left_lim", "align": "right"},
                        {"name": "eye_right_lim", "label": "Right", "field": "eye_right_lim", "align": "right"},
                        {"name": "eye_top_left_lim", "label": "TL", "field": "eye_top_left_lim", "align": "right"},
                        {"name": "eye_top_right_lim", "label": "TR", "field": "eye_top_right_lim", "align": "right"},
                        {"name": "eye_bot_left_lim", "label": "BL", "field": "eye_bot_left_lim", "align": "right"},
                        {"name": "eye_bot_right_lim", "label": "BR", "field": "eye_bot_right_lim", "align": "right"},
                    ]
                    keyed_rows = [
                        {**r, "_key": f"{r['port_id']}_{r['lane_id']}"} for r in rows
                    ]
                    table = ui.table(
                        columns=columns, rows=keyed_rows, row_key="_key",
                    ).classes("w-full")
                    table.add_slot(
                        "body-cell-verdict",
                        """
                        <q-td :props="props">
                            <q-badge
                                :color="props.value === 'PASS' ? 'positive' :
                                        props.value === 'MARGINAL' ? 'warning' : 'negative'"
                                :label="props.value"
                            />
                        </q-td>
                        """,
                    )
                    pass_count = sum(1 for r in rows if r["verdict"] == "PASS")
                    marginal_count = sum(1 for r in rows if r["verdict"] == "MARGINAL")
                    fail_count = sum(1 for r in rows if r["verdict"] == "FAIL")
                    parts = []
                    if pass_count:
                        parts.append(f"{pass_count} PASS")
                    if marginal_count:
                        parts.append(f"{marginal_count} MARGINAL")
                    if fail_count:
                        parts.append(f"{fail_count} FAIL")
                    color = (
                        COLORS.success if fail_count == 0 and marginal_count == 0
                        else COLORS.warning if fail_count == 0
                        else COLORS.error
                    )
                    ui.label(
                        f"{len(rows)} lanes: {', '.join(parts)}"
                    ).classes("text-subtitle2 q-mt-sm").style(f"color: {color};")

        def _render_results() -> None:
            if not sweep.rows:
                return
            h_warn = sweep.thresholds["h_warn"]
            v_warn = sweep.thresholds["v_warn"]
            is_pam4 = sweep.thresholds["is_pam4"]
            _render_heatmap_section(sweep.rows, h_warn, v_warn, is_pam4)
            _render_diamond_section(sweep.rows)
            _render_table_section(sweep.rows)

        # ── Sweep lane helper ─────────────────────────────────────

        async def _sweep_lane(
            dev: object,
            pid: int,
            lane_id: int,
            lane_offset: int,
            timeout_s: float,
            h_warn: int,
            v_warn: int,
            is_pam4: bool,
            base_label: str,
        ) -> dict:
            """Measure a single lane: enable, poll, disable, return row."""
            try:
                await run.io_bound(dev.diagnostics.cross_hair_enable, lane_id)
            except SwitchtecError:
                return _error_row(pid, lane_id, lane_offset, is_pam4)

            ch = await _poll_lane(dev, lane_id, timeout_s, base_label)

            try:
                await run.io_bound(dev.diagnostics.cross_hair_disable)
            except SwitchtecError:
                pass

            if ch is not None:
                return _build_row(pid, lane_id, lane_offset, ch, h_warn, v_warn, is_pam4)
            return _error_row(pid, lane_id, lane_offset, is_pam4)

        # ── Poll loop ─────────────────────────────────────────────

        async def _poll_lane(
            dev: object,
            lane_id: int,
            timeout_s: float,
            base_label: str,
        ) -> object | None:
            """Poll cross_hair_get until DONE/ERROR or timeout."""
            start_t = time.monotonic()
            while time.monotonic() - start_t < timeout_s:
                try:
                    results = await run.io_bound(
                        dev.diagnostics.cross_hair_get, lane_id, 1,
                    )
                    if results:
                        ch = results[0]
                        if ch.state == DiagCrossHairState.DONE:
                            return ch
                        if ch.state == DiagCrossHairState.ERROR:
                            return None
                        progress_label.set_text(
                            f"{base_label} \u2014 {ch.state_name}"
                        )
                except SwitchtecError:
                    pass
                await asyncio.sleep(0.5)
            return None

        # ── Sweep orchestrator ────────────────────────────────────

        async def _on_start_sweep() -> None:
            if sweep.running:
                return

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            # Resolve thresholds
            gen_key = gen_select.value or "gen6"
            custom_h = int(custom_h_input.value or 20) if gen_key == "custom" else None
            custom_v = int(custom_v_input.value or 30) if gen_key == "custom" else None
            thresholds = _resolve_thresholds(gen_key, custom_h, custom_v)

            # Get target ports
            ports = await run.io_bound(state.get_port_status)
            active_ports = [p for p in ports if p.link_up]

            if port_mode.value == "single":
                target_pid = int(single_port_input.value or 0)
                active_ports = [p for p in active_ports if p.port.phys_id == target_pid]

            if not active_ports:
                ui.notify("No active ports found", type="warning", position="top")
                return

            # Initialize sweep state & UI
            sweep.running = True
            sweep.cancelled = False
            sweep.rows = []
            sweep.thresholds = thresholds
            start_btn.props("loading")
            start_btn.set_enabled(False)
            cancel_btn.set_enabled(True)
            progress_card.set_visibility(True)
            progress_bar.set_value(0)

            timeout_s = float(timeout_input.value or 15)
            total_lanes = sum(p.neg_lnk_width for p in active_ports)
            lanes_done = 0
            sweep_start = time.monotonic()
            h_warn = thresholds["h_warn"]
            v_warn = thresholds["v_warn"]
            is_pam4 = thresholds["is_pam4"]

            try:
                for port_idx, port in enumerate(active_ports):
                    if sweep.cancelled:
                        break
                    pid = port.port.phys_id
                    first_lane = port.first_act_lane
                    width = port.neg_lnk_width

                    for lane_offset in range(width):
                        if sweep.cancelled:
                            break
                        lane_id = first_lane + lane_offset
                        lanes_done += 1

                        frac = lanes_done / max(total_lanes, 1)
                        elapsed = time.monotonic() - sweep_start
                        eta = (elapsed / max(lanes_done, 1)) * (total_lanes - lanes_done)
                        eta_str = f"ETA: {int(eta)}s" if lanes_done > 1 else ""
                        base_label = (
                            f"Port {port_idx + 1}/{len(active_ports)} \u2014 "
                            f"Lane {lane_offset + 1}/{width} \u2014 "
                            f"{int(frac * 100)}% {eta_str}"
                        )
                        progress_bar.set_value(frac)
                        progress_label.set_text(base_label)

                        row = await _sweep_lane(
                            dev, pid, lane_id, lane_offset, timeout_s,
                            h_warn, v_warn, is_pam4, base_label,
                        )
                        sweep.rows.append(row)

                        if state.get_active_device() is None:
                            sweep.cancelled = True
                            ui.notify("Device disconnected", type="negative", position="top")
                            break

                progress_bar.set_value(1.0)
                if sweep.cancelled:
                    progress_label.set_text("Sweep cancelled \u2014 showing partial results")
                else:
                    progress_label.set_text("Sweep complete")
                _render_results()

            except SwitchtecError as exc:
                ui.notify(f"Sweep failed: {exc}", type="negative", position="top")
                progress_label.set_text(f"Sweep failed: {exc}")
                try:
                    await run.io_bound(dev.diagnostics.cross_hair_disable)
                except SwitchtecError:
                    pass
            finally:
                sweep.running = False
                start_btn.props(remove="loading")
                start_btn.set_enabled(True)
                cancel_btn.set_enabled(False)

        async def _on_cancel_sweep() -> None:
            sweep.cancelled = True
            cancel_btn.props("loading")

            dev = state.get_active_device()
            if dev is not None:
                try:
                    await run.io_bound(dev.diagnostics.cross_hair_disable)
                except SwitchtecError:
                    pass

            cancel_btn.props(remove="loading")
            cancel_btn.set_enabled(False)

        start_btn.on_click(_on_start_sweep)
        cancel_btn.on_click(_on_cancel_sweep)
