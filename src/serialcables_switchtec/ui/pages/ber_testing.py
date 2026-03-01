"""BER testing page — loopback, pattern generator, pattern monitor, live error chart."""

from __future__ import annotations

import time

from nicegui import run, ui

from serialcables_switchtec.bindings.constants import (
    DiagLtssmSpeed,
    DiagPatternLinkRate,
)
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.confirm_dialog import confirm_action
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults

# Gen-specific pattern maps (mirrored from CLI diag.py)
_GEN_PATTERN_MAPS: dict[str, dict[str, int]] = {
    "gen3": {
        "PRBS7": 0, "PRBS11": 1, "PRBS23": 2, "PRBS31": 3,
        "PRBS9": 4, "PRBS15": 5, "Disabled": 6,
    },
    "gen4": {
        "PRBS7": 0, "PRBS11": 1, "PRBS23": 2, "PRBS31": 3,
        "PRBS9": 4, "PRBS15": 5, "Disabled": 6,
    },
    "gen5": {
        "PRBS7": 0, "PRBS11": 1, "PRBS23": 2, "PRBS31": 3,
        "PRBS9": 4, "PRBS15": 5, "PRBS5": 6, "PRBS20": 7,
        "Disabled": 10,
    },
    "gen6": {
        "PRBS7": 0, "PRBS9": 1, "PRBS11": 2, "PRBS13": 3,
        "PRBS15": 4, "PRBS23": 5, "PRBS31": 6,
        "52UI Jitter": 0x19, "Disabled": 0x1A,
    },
}

_LTSSM_SPEED_OPTIONS = {s.value: s.name for s in DiagLtssmSpeed}
_LINK_RATE_OPTIONS = {
    r.value: r.name for r in DiagPatternLinkRate if r != DiagPatternLinkRate.DISABLED
}
_GEN_SELECT_OPTIONS = {"gen3": "Gen 3", "gen4": "Gen 4", "gen5": "Gen 5", "gen6": "Gen 6"}

_LANE_COLORS = [
    "#4fc3f7", "#66bb6a", "#ffa726", "#ef5350",
    "#ab47bc", "#26c6da", "#ffee58", "#ec407a",
    "#8d6e63", "#78909c", "#d4e157", "#29b6f6",
    "#ff7043", "#5c6bc0", "#9ccc65", "#42a5f5",
]


def _make_ber_figure(
    samples: dict[int, dict[str, list]],
) -> dict:
    """Build a Plotly figure from per-lane error count history."""
    traces = []
    for lane_id in sorted(samples.keys()):
        data = samples[lane_id]
        color = _LANE_COLORS[lane_id % len(_LANE_COLORS)]
        traces.append({
            "type": "scatter",
            "x": list(data["timestamps"]),
            "y": list(data["errors"]),
            "mode": "lines+markers",
            "name": f"Lane {lane_id}",
            "line": {"color": color, "width": 2},
            "marker": {"size": 4},
        })

    return {
        "data": traces,
        "layout": {
            **plotly_layout_defaults(),
            "title": "Live BER Error Count",
            "xaxis": {
                **plotly_layout_defaults()["xaxis"],
                "title": "Elapsed (s)",
            },
            "yaxis": {
                **plotly_layout_defaults()["yaxis"],
                "title": "Error Count",
            },
            "legend": {
                "font": {"color": COLORS.text_secondary},
                "bgcolor": "rgba(0,0,0,0)",
            },
        },
    }


def ber_testing_page() -> None:
    """BER testing page with loopback, pattern gen/mon, and live error chart."""
    from serialcables_switchtec.ui import state

    with page_layout("BER Testing", current_path="/ber"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("BER Testing").classes("text-h5 q-mb-md")

        # ── Section 1: Loopback Configuration ────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Loopback Configuration").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                lb_port_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                lb_speed_select = ui.select(
                    options=_LTSSM_SPEED_OPTIONS,
                    label="LTSSM Speed",
                    value=DiagLtssmSpeed.GEN4.value,
                ).classes("w-32")

            with ui.row().classes("q-gutter-md q-mt-sm flex-wrap"):
                lb_parallel = ui.switch("Parallel")
                lb_external = ui.switch("External")
                lb_ltssm = ui.switch("LTSSM")
                lb_pipe = ui.switch("PIPE")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                lb_enable_btn = ui.button(
                    "Enable Loopback", icon="loop",
                ).props("color=positive")
                lb_disable_btn = ui.button(
                    "Disable Loopback", icon="close",
                ).props("color=negative")
                lb_refresh_btn = ui.button(
                    "Read Status", icon="refresh",
                ).props("flat")

            lb_status_label = ui.label("Loopback status: unknown").classes(
                "text-subtitle2 q-mt-sm"
            ).style(f"color: {COLORS.text_secondary};")

            async def _on_lb_enable() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(lb_port_input.value or 0)
                speed = DiagLtssmSpeed(int(lb_speed_select.value or 3))
                lb_enable_btn.props("loading")
                try:
                    await run.io_bound(
                        dev.diagnostics.loopback_set,
                        port, True,
                        bool(lb_parallel.value),
                        bool(lb_external.value),
                        bool(lb_ltssm.value),
                        bool(lb_pipe.value),
                        speed,
                    )
                    lb_status_label.set_text(
                        f"Loopback ENABLED on port {port} at {speed.name}"
                    )
                    lb_status_label.style(f"color: {COLORS.success};")
                    ui.notify("Loopback enabled", type="positive", position="top")
                except SwitchtecError as exc:
                    ui.notify(f"Loopback enable failed: {exc}", type="negative", position="top")
                finally:
                    lb_enable_btn.props(remove="loading")

            async def _on_lb_disable() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(lb_port_input.value or 0)
                lb_disable_btn.props("loading")
                try:
                    await run.io_bound(
                        dev.diagnostics.loopback_set, port, False,
                    )
                    lb_status_label.set_text(f"Loopback DISABLED on port {port}")
                    lb_status_label.style(f"color: {COLORS.text_secondary};")
                    ui.notify("Loopback disabled", type="info", position="top")
                except SwitchtecError as exc:
                    ui.notify(f"Loopback disable failed: {exc}", type="negative", position="top")
                finally:
                    lb_disable_btn.props(remove="loading")

            async def _on_lb_refresh() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(lb_port_input.value or 0)
                lb_refresh_btn.props("loading")
                try:
                    result = await run.io_bound(dev.diagnostics.loopback_get, port)
                    enabled_str = "ENABLED" if result.enabled else "DISABLED"
                    speed_name = DiagLtssmSpeed(result.ltssm_speed).name
                    lb_status_label.set_text(
                        f"Loopback {enabled_str} on port {port} (speed: {speed_name})"
                    )
                    color = COLORS.success if result.enabled else COLORS.text_secondary
                    lb_status_label.style(f"color: {color};")
                except SwitchtecError as exc:
                    ui.notify(f"Loopback read failed: {exc}", type="negative", position="top")
                finally:
                    lb_refresh_btn.props(remove="loading")

            lb_enable_btn.on_click(_on_lb_enable)
            lb_disable_btn.on_click(_on_lb_disable)
            lb_refresh_btn.on_click(_on_lb_refresh)

        # ── Section 2: Pattern Generator ─────────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Pattern Generator").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                pg_port_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                pg_gen_select = ui.select(
                    options=_GEN_SELECT_OPTIONS,
                    label="PCIe Generation",
                    value="gen4",
                ).classes("w-32")

            pattern_options: dict[int, str] = {
                v: k for k, v in _GEN_PATTERN_MAPS["gen4"].items()
            }
            pg_pattern_select = ui.select(
                options=pattern_options,
                label="Pattern",
                value=3,
            ).classes("w-40")

            def _on_gen_change() -> None:
                gen = pg_gen_select.value or "gen4"
                new_options = {v: k for k, v in _GEN_PATTERN_MAPS[gen].items()}
                pg_pattern_select.options = new_options
                pg_pattern_select.update()
                if pg_pattern_select.value not in new_options:
                    pg_pattern_select.set_value(next(iter(new_options)))

            pg_gen_select.on_value_change(lambda _: _on_gen_change())

            pg_speed_select = ui.select(
                options=_LINK_RATE_OPTIONS,
                label="Link Speed",
                value=DiagPatternLinkRate.GEN4.value,
            ).classes("w-32")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                pg_start_btn = ui.button(
                    "Start Generator", icon="play_arrow",
                ).props("color=positive")
                pg_stop_btn = ui.button(
                    "Stop Generator", icon="stop",
                ).props("color=negative")

            async def _on_pg_start() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(pg_port_input.value or 0)
                pattern = int(pg_pattern_select.value)
                speed = DiagPatternLinkRate(int(pg_speed_select.value or 4))
                pg_start_btn.props("loading")
                try:
                    await run.io_bound(
                        dev.diagnostics.pattern_gen_set, port, pattern, speed,
                    )
                    ui.notify(
                        f"Pattern generator started on port {port}",
                        type="positive", position="top",
                    )
                except SwitchtecError as exc:
                    ui.notify(f"Pattern gen failed: {exc}", type="negative", position="top")
                finally:
                    pg_start_btn.props(remove="loading")

            async def _on_pg_stop() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(pg_port_input.value or 0)
                gen = pg_gen_select.value or "gen4"
                disabled_val = _GEN_PATTERN_MAPS[gen].get("Disabled", 6)
                pg_stop_btn.props("loading")
                try:
                    await run.io_bound(
                        dev.diagnostics.pattern_gen_set, port, disabled_val,
                        DiagPatternLinkRate.DISABLED,
                    )
                    ui.notify("Pattern generator stopped", type="info", position="top")
                except SwitchtecError as exc:
                    ui.notify(f"Pattern gen stop failed: {exc}", type="negative", position="top")
                finally:
                    pg_stop_btn.props(remove="loading")

            pg_start_btn.on_click(_on_pg_start)
            pg_stop_btn.on_click(_on_pg_stop)

        # ── Section 3: Pattern Monitor ───────────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Pattern Monitor").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                pm_port_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                pm_lane_count = ui.number(
                    label="Lane Count", value=4, min=1, max=16,
                ).classes("w-28")
                pm_interval = ui.select(
                    options={0.5: "0.5s", 1.0: "1s", 2.0: "2s", 5.0: "5s", 10.0: "10s"},
                    label="Poll Interval",
                    value=1.0,
                ).classes("w-28")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                pm_start_btn = ui.button(
                    "Start Monitoring", icon="play_arrow",
                ).props("color=positive")
                pm_stop_btn = ui.button(
                    "Stop Monitoring", icon="stop",
                ).props("color=negative")
                pm_stop_btn.set_enabled(False)

            ui.separator().classes("q-my-sm")

            ui.label("Error Injection").classes("text-subtitle1 q-mb-xs").style(
                f"color: {COLORS.text_primary};"
            )
            with ui.row().classes("q-gutter-sm items-end"):
                inj_port_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                inj_count_input = ui.number(
                    label="Error Count", value=1, min=1, max=1000,
                ).classes("w-28")
                inj_btn = ui.button(
                    "Inject Errors", icon="bolt",
                ).props("color=negative")

        # ── Section 4: Per-Lane Error Count Table ────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Per-Lane Error Counts").classes("text-h6 q-mb-sm")
            lane_table_container = ui.column().classes("w-full")
            with lane_table_container:
                ui.label("Start monitoring to see error counts.").classes(
                    "text-subtitle2"
                ).style(f"color: {COLORS.text_secondary};")

        # ── Section 5: Live BER Chart ────────────────────────────────
        with ui.card().classes("w-full q-pa-md"):
            ber_chart = ui.plotly(
                _make_ber_figure({})
            ).classes("w-full").style("height: 400px")

        # ── Monitor State ────────────────────────────────────────────
        ber_state: dict = {"timer": None, "samples": {}, "start_time": 0.0, "prev_counts": {}}

        async def _poll_monitor() -> None:
            dev = state.get_active_device()
            if dev is None:
                return

            port = int(pm_port_input.value or 0)
            lanes = int(pm_lane_count.value or 4)
            elapsed = time.monotonic() - ber_state["start_time"]
            max_points = 120

            rows = []
            for lane in range(lanes):
                try:
                    result = await run.io_bound(
                        dev.diagnostics.pattern_mon_get, port, lane,
                    )
                except SwitchtecError:
                    continue

                prev = ber_state["prev_counts"].get(lane, 0)
                delta = result.error_count - prev
                ber_state["prev_counts"][lane] = result.error_count

                rows.append({
                    "lane": lane,
                    "pattern": result.pattern_type,
                    "errors": result.error_count,
                    "delta": delta,
                })

                if lane not in ber_state["samples"]:
                    ber_state["samples"][lane] = {"timestamps": [], "errors": []}
                lane_data = ber_state["samples"][lane]
                lane_data["timestamps"].append(round(elapsed, 1))
                lane_data["errors"].append(result.error_count)
                if len(lane_data["timestamps"]) > max_points:
                    lane_data["timestamps"] = lane_data["timestamps"][-max_points:]
                    lane_data["errors"] = lane_data["errors"][-max_points:]

            # Update table
            lane_table_container.clear()
            with lane_table_container:
                if rows:
                    columns = [
                        {"name": "lane", "label": "Lane", "field": "lane", "align": "center"},
                        {"name": "pattern", "label": "Pattern Type", "field": "pattern", "align": "center"},
                        {"name": "errors", "label": "Error Count", "field": "errors", "align": "right", "sortable": True},
                        {"name": "delta", "label": "Delta", "field": "delta", "align": "right"},
                    ]
                    ui.table(columns=columns, rows=rows, row_key="lane").classes("w-full")

            # Update chart
            ber_chart.update_figure(_make_ber_figure(ber_state["samples"]))

        async def _on_pm_start() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(pm_port_input.value or 0)
            pattern_val = int(pg_pattern_select.value)

            try:
                await run.io_bound(
                    dev.diagnostics.pattern_mon_set, port, pattern_val,
                )
            except SwitchtecError as exc:
                ui.notify(f"Pattern monitor setup failed: {exc}", type="negative", position="top")
                return

            interval = float(pm_interval.value or 1.0)
            ber_state["samples"] = {}
            ber_state["prev_counts"] = {}
            ber_state["start_time"] = time.monotonic()
            ber_state["timer"] = ui.timer(interval, _poll_monitor)

            pm_start_btn.set_enabled(False)
            pm_stop_btn.set_enabled(True)
            pm_port_input.set_enabled(False)
            pm_lane_count.set_enabled(False)
            pm_interval.set_enabled(False)

            ui.notify("Pattern monitoring started", type="positive", position="top")

        def _on_pm_stop() -> None:
            timer = ber_state.get("timer")
            if timer is not None:
                timer.cancel()
                ber_state["timer"] = None

            pm_start_btn.set_enabled(True)
            pm_stop_btn.set_enabled(False)
            pm_port_input.set_enabled(True)
            pm_lane_count.set_enabled(True)
            pm_interval.set_enabled(True)

            ui.notify("Pattern monitoring stopped", type="info", position="top")

        pm_start_btn.on_click(_on_pm_start)
        pm_stop_btn.on_click(_on_pm_stop)

        async def _on_inject() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(inj_port_input.value or 0)
            count = int(inj_count_input.value or 1)

            confirmed = await confirm_action(
                title="Confirm Error Injection",
                message=f"Inject {count} error(s) into pattern stream on port {port}?",
                confirm_text="Inject",
                dangerous=True,
            )
            if not confirmed:
                return

            inj_btn.props("loading")
            try:
                await run.io_bound(dev.diagnostics.pattern_inject, port, count)
                ui.notify(
                    f"Injected {count} error(s) on port {port}",
                    type="warning", position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Injection failed: {exc}", type="negative", position="top")
            finally:
                inj_btn.props(remove="loading")

        inj_btn.on_click(_on_inject)
