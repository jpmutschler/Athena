"""Performance monitoring page."""

from __future__ import annotations

import time

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

# Per-port trace colors for the Plotly bandwidth chart
_PORT_COLORS = [
    "#4fc3f7", "#66bb6a", "#ffa726", "#ef5350",
    "#ab47bc", "#26c6da", "#ffee58", "#ec407a",
    "#8d6e63", "#78909c", "#d4e157", "#29b6f6",
]


def _make_bw_figure(
    bw_history: dict[int, dict[str, list]],
) -> dict:
    """Build a Plotly figure dict from bandwidth history data."""
    traces = []
    color_idx = 0

    for port_id in sorted(bw_history.keys()):
        data = bw_history[port_id]
        color = _PORT_COLORS[color_idx % len(_PORT_COLORS)]
        color_idx += 1

        # Egress trace (solid line)
        traces.append({
            "type": "scatter",
            "x": list(data["timestamps"]),
            "y": list(data["egress"]),
            "mode": "lines+markers",
            "name": f"P{port_id} Egress",
            "line": {"color": color, "width": 2},
            "marker": {"size": 4},
        })
        # Ingress trace (dashed line, same color)
        traces.append({
            "type": "scatter",
            "x": list(data["timestamps"]),
            "y": list(data["ingress"]),
            "mode": "lines+markers",
            "name": f"P{port_id} Ingress",
            "line": {"color": color, "width": 2, "dash": "dash"},
            "marker": {"size": 4},
        })

    return {
        "data": traces,
        "layout": {
            "title": "Bandwidth Over Time",
            "xaxis": {
                "title": "Elapsed (s)",
                "color": COLORS.text_secondary,
                "gridcolor": COLORS.text_muted,
            },
            "yaxis": {
                "title": "Bytes",
                "color": COLORS.text_secondary,
                "gridcolor": COLORS.text_muted,
            },
            "paper_bgcolor": COLORS.bg_primary,
            "plot_bgcolor": COLORS.bg_card,
            "font": {"color": COLORS.text_primary},
            "legend": {
                "font": {"color": COLORS.text_secondary},
                "bgcolor": "rgba(0,0,0,0)",
            },
            "margin": {"l": 60, "r": 20, "t": 40, "b": 40},
        },
    }


def performance_page() -> None:
    """Live bandwidth and latency charts."""
    from serialcables_switchtec.ui import state

    with page_layout("Performance", current_path="/performance"):
        if not state.is_connected():
            show_disconnected()
            return

        ports = state.get_port_status()

        ui.label("Performance Monitoring").classes("text-h5 q-mb-md")

        # ================================================================
        #  Bandwidth Monitoring Section
        # ================================================================
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Bandwidth Counters").classes("text-h6 q-mb-sm")

            # Port selection
            port_options = {
                p.port.phys_id: f"P{p.port.phys_id} ({'UP' if p.link_up else 'DOWN'})"
                for p in ports
            }
            if not port_options:
                ui.label("No ports available.").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )

            with ui.row().classes("q-gutter-sm items-end w-full"):
                port_select = ui.select(
                    options=port_options,
                    label="Ports to Monitor",
                    multiple=True,
                    value=[],
                ).classes("w-64").props("use-chips")

                interval_select = ui.select(
                    options={1.0: "1s", 2.0: "2s", 5.0: "5s"},
                    label="Interval",
                    value=1.0,
                ).classes("w-24")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                start_bw_btn = ui.button(
                    "Start Monitoring", icon="play_arrow",
                ).props("color=positive")
                stop_bw_btn = ui.button(
                    "Stop Monitoring", icon="stop",
                ).props("color=negative")
                stop_bw_btn.set_enabled(False)

        # --- Live bandwidth chart ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            bw_chart = ui.plotly(
                _make_bw_figure({})
            ).classes("w-full").style("height: 400px")

        # --- Per-port bandwidth totals card ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Current Bandwidth Totals").classes("text-h6 q-mb-sm")
            bw_totals_container = ui.column().classes("w-full")
            with bw_totals_container:
                ui.label("Start monitoring to see totals.").classes(
                    "text-subtitle2"
                ).style(f"color: {COLORS.text_secondary};")

        # --- Bandwidth monitoring state ---
        bw_state: dict = {
            "timer": None,
            "history": {},
            "start_time": 0.0,
        }

        def _clear_bw_history(selected_ports: list[int]) -> dict[int, dict[str, list]]:
            """Create a fresh history dict for the selected ports."""
            return {
                pid: {"timestamps": [], "egress": [], "ingress": []}
                for pid in selected_ports
            }

        async def _poll_bw() -> None:
            """Called on each timer tick to fetch and display bandwidth data."""
            dev = state.get_active_device()
            if dev is None:
                return

            selected_ports = list(port_select.value or [])
            if not selected_ports:
                return

            try:
                results = await run.io_bound(
                    dev.performance.bw_get, selected_ports, True,
                )
            except SwitchtecError:
                return

            elapsed = time.monotonic() - bw_state["start_time"]
            history = bw_state["history"]

            # Keep only the last 120 data points per port to limit memory
            max_points = 120

            for pid, result in zip(selected_ports, results):
                if pid not in history:
                    history[pid] = {"timestamps": [], "egress": [], "ingress": []}
                port_data = history[pid]
                port_data["timestamps"].append(round(elapsed, 1))
                port_data["egress"].append(result.egress.total)
                port_data["ingress"].append(result.ingress.total)
                # Trim old data
                if len(port_data["timestamps"]) > max_points:
                    port_data["timestamps"] = port_data["timestamps"][-max_points:]
                    port_data["egress"] = port_data["egress"][-max_points:]
                    port_data["ingress"] = port_data["ingress"][-max_points:]

            # Update chart
            bw_chart.update_figure(_make_bw_figure(history))

            # Update totals display
            bw_totals_container.clear()
            with bw_totals_container:
                with ui.row().classes("w-full q-gutter-md flex-wrap"):
                    for pid, result in zip(selected_ports, results):
                        with ui.card().classes("q-pa-sm").style(
                            f"border: 1px solid {COLORS.text_muted};"
                            f" background: {COLORS.bg_secondary};"
                            " min-width: 160px;"
                        ):
                            ui.label(f"Port {pid}").classes(
                                "text-subtitle2 text-bold"
                            ).style(f"color: {COLORS.accent};")
                            ui.label(
                                f"Egress: {result.egress.total:,} B"
                            ).style(
                                f"color: {COLORS.text_primary}; font-size: 0.85em;"
                            )
                            ui.label(
                                f"Ingress: {result.ingress.total:,} B"
                            ).style(
                                f"color: {COLORS.text_primary}; font-size: 0.85em;"
                            )
                            if result.time_us > 0:
                                egress_mbps = (
                                    result.egress.total * 8.0 / result.time_us
                                )
                                ingress_mbps = (
                                    result.ingress.total * 8.0 / result.time_us
                                )
                                ui.label(
                                    f"Egress: {egress_mbps:.1f} Mbps"
                                ).style(
                                    f"color: {COLORS.text_secondary};"
                                    " font-size: 0.8em;"
                                )
                                ui.label(
                                    f"Ingress: {ingress_mbps:.1f} Mbps"
                                ).style(
                                    f"color: {COLORS.text_secondary};"
                                    " font-size: 0.8em;"
                                )

        async def _on_start_bw() -> None:
            selected_ports = list(port_select.value or [])
            if not selected_ports:
                ui.notify(
                    "Select at least one port to monitor",
                    type="warning", position="top",
                )
                return

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            # Initial clear read to establish baseline
            try:
                await run.io_bound(
                    dev.performance.bw_get, selected_ports, True,
                )
            except SwitchtecError as exc:
                ui.notify(
                    f"Failed to initialize counters: {exc}",
                    type="negative", position="top",
                )
                return

            interval = float(interval_select.value or 1.0)
            bw_state["history"] = _clear_bw_history(selected_ports)
            bw_state["start_time"] = time.monotonic()

            # Create a ui.timer for periodic polling
            bw_state["timer"] = ui.timer(interval, _poll_bw)

            start_bw_btn.set_enabled(False)
            stop_bw_btn.set_enabled(True)
            port_select.set_enabled(False)
            interval_select.set_enabled(False)

            ui.notify("Bandwidth monitoring started", type="positive", position="top")

        def _on_stop_bw() -> None:
            timer = bw_state.get("timer")
            if timer is not None:
                timer.cancel()
                bw_state["timer"] = None

            start_bw_btn.set_enabled(True)
            stop_bw_btn.set_enabled(False)
            port_select.set_enabled(True)
            interval_select.set_enabled(True)

            ui.notify("Bandwidth monitoring stopped", type="info", position="top")

        start_bw_btn.on_click(_on_start_bw)
        stop_bw_btn.on_click(_on_stop_bw)

        # ================================================================
        #  Latency Measurement Section
        # ================================================================
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Latency Measurement").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end"):
                egress_port_input = ui.number(
                    label="Egress Port ID", value=0, min=0, max=59,
                ).classes("w-32")
                ingress_port_input = ui.number(
                    label="Ingress Port ID", value=0, min=0, max=59,
                ).classes("w-32")
                sample_count_input = ui.number(
                    label="Samples", value=10, min=1, max=100,
                ).classes("w-24")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                lat_btn = ui.button(
                    "Measure Latency", icon="timer",
                ).props("color=primary")

        # --- Latency results card ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Latency Results").classes("text-h6 q-mb-sm")
            lat_container = ui.column().classes("w-full")
            with lat_container:
                ui.label(
                    "Configure egress/ingress port pair and click Measure."
                ).classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )

        async def _on_measure_latency() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            egress_port = int(egress_port_input.value or 0)
            ingress_port = int(ingress_port_input.value or 0)
            sample_count = int(sample_count_input.value or 10)

            lat_btn.props("loading")
            try:
                # Setup the latency counter pair
                await run.io_bound(
                    dev.performance.lat_setup,
                    egress_port, ingress_port, True,
                )

                # Collect samples
                samples = []
                for _ in range(sample_count):
                    result = await run.io_bound(
                        dev.performance.lat_get, egress_port, True,
                    )
                    samples.append(result)

                # Display results
                lat_container.clear()
                with lat_container:
                    if not samples:
                        ui.label("No samples collected.").classes(
                            "text-subtitle2"
                        ).style(f"color: {COLORS.text_secondary};")
                        return

                    current_values = [s.current_ns for s in samples]
                    max_values = [s.max_ns for s in samples]
                    avg_ns = sum(current_values) / len(current_values)
                    peak_ns = max(max_values)
                    min_ns = min(current_values)

                    # Summary cards
                    with ui.row().classes("q-gutter-md q-mb-md"):
                        with ui.card().classes("q-pa-sm").style(
                            f"border: 1px solid {COLORS.text_muted};"
                            f" background: {COLORS.bg_secondary};"
                        ):
                            ui.label("Average").classes(
                                "text-subtitle2"
                            ).style(f"color: {COLORS.text_secondary};")
                            ui.label(f"{avg_ns:.0f} ns").classes(
                                "text-h5"
                            ).style(f"color: {COLORS.accent};")

                        with ui.card().classes("q-pa-sm").style(
                            f"border: 1px solid {COLORS.text_muted};"
                            f" background: {COLORS.bg_secondary};"
                        ):
                            ui.label("Min").classes(
                                "text-subtitle2"
                            ).style(f"color: {COLORS.text_secondary};")
                            ui.label(f"{min_ns} ns").classes(
                                "text-h5"
                            ).style(f"color: {COLORS.success};")

                        with ui.card().classes("q-pa-sm").style(
                            f"border: 1px solid {COLORS.text_muted};"
                            f" background: {COLORS.bg_secondary};"
                        ):
                            ui.label("Peak").classes(
                                "text-subtitle2"
                            ).style(f"color: {COLORS.text_secondary};")
                            ui.label(f"{peak_ns} ns").classes(
                                "text-h5"
                            ).style(f"color: {COLORS.warning};")

                    # Latency samples table
                    columns = [
                        {
                            "name": "sample",
                            "label": "#",
                            "field": "sample",
                            "align": "right",
                        },
                        {
                            "name": "current_ns",
                            "label": "Current (ns)",
                            "field": "current_ns",
                            "align": "right",
                            "sortable": True,
                        },
                        {
                            "name": "max_ns",
                            "label": "Max (ns)",
                            "field": "max_ns",
                            "align": "right",
                            "sortable": True,
                        },
                    ]

                    rows = [
                        {
                            "sample": i + 1,
                            "current_ns": s.current_ns,
                            "max_ns": s.max_ns,
                        }
                        for i, s in enumerate(samples)
                    ]

                    ui.table(
                        columns=columns,
                        rows=rows,
                        row_key="sample",
                        pagination={"rowsPerPage": 20},
                    ).classes("w-full")

                ui.notify(
                    f"Latency: avg {avg_ns:.0f} ns, peak {peak_ns} ns"
                    f" ({sample_count} samples)",
                    type="positive", position="top",
                )

            except SwitchtecError as exc:
                ui.notify(
                    f"Latency measurement failed: {exc}",
                    type="negative", position="top",
                )
            finally:
                lat_btn.props(remove="loading")

        lat_btn.on_click(_on_measure_latency)
