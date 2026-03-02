"""LTSSM state trace page."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.core.ltssm_graph import build_state_graph
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.ltssm_state_graph import ltssm_state_graph
from serialcables_switchtec.ui.components.ltssm_timeline import ltssm_timeline
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def ltssm_trace_page() -> None:
    """LTSSM state machine timeline display."""
    from serialcables_switchtec.ui import state

    with page_layout("LTSSM Trace", current_path="/ltssm"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("LTSSM State Trace").classes("text-h5 q-mb-md")

        # --- Controls card ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            with ui.row().classes("q-gutter-sm items-end"):
                port_id_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                max_entries_input = ui.number(
                    label="Max Entries", value=64, min=1, max=256,
                ).classes("w-32")
                capture_btn = ui.button(
                    "Capture Log", icon="history",
                ).props("color=primary")
                clear_btn = ui.button(
                    "Clear Log", icon="delete",
                ).props("color=negative")

        # --- Tabbed chart view ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            with ui.tabs().classes("w-full") as tabs:
                timeline_tab = ui.tab("Timeline", icon="timeline")
                graph_tab = ui.tab("State Graph", icon="hub")

            with ui.tab_panels(tabs, value=timeline_tab).classes("w-full"):
                with ui.tab_panel(timeline_tab):
                    timeline_container = ui.column().classes("w-full")
                    with timeline_container:
                        ui.label(
                            "Capture a log to view the LTSSM timeline."
                        ).classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )

                with ui.tab_panel(graph_tab):
                    graph_container = ui.column().classes("w-full")
                    with graph_container:
                        ui.label(
                            "Capture a log to view the state graph."
                        ).classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )

        # --- Log entries table card ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Log Entries").classes("text-h6 q-mb-sm")
            table_container = ui.column().classes("w-full")
            with table_container:
                ui.label(
                    "No log entries yet."
                ).classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )

        async def _on_capture() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port_id = int(port_id_input.value or 0)
            max_entries = int(max_entries_input.value or 64)

            capture_btn.props("loading")
            try:
                entries = await run.io_bound(
                    dev.diagnostics.ltssm_log, port_id, max_entries,
                )

                # Render the timeline chart
                timeline_container.clear()
                with timeline_container:
                    if entries:
                        ltssm_timeline(entries)
                    else:
                        ui.label(
                            "No LTSSM transitions captured."
                        ).classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )

                # Render the state graph
                graph_container.clear()
                with graph_container:
                    if entries:
                        graph = build_state_graph(entries)
                        ltssm_state_graph(graph)
                    else:
                        ui.label(
                            "No LTSSM transitions for graph."
                        ).classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )

                # Render the log entries table
                table_container.clear()
                with table_container:
                    if entries:
                        columns = [
                            {
                                "name": "timestamp",
                                "label": "Timestamp",
                                "field": "timestamp",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "link_state_str",
                                "label": "LTSSM State",
                                "field": "link_state_str",
                                "sortable": True,
                                "align": "left",
                            },
                            {
                                "name": "link_state",
                                "label": "State ID",
                                "field": "link_state",
                                "sortable": True,
                                "align": "right",
                            },
                            {
                                "name": "link_rate",
                                "label": "Link Rate",
                                "field": "link_rate",
                                "sortable": True,
                                "align": "right",
                            },
                            {
                                "name": "link_width",
                                "label": "Width",
                                "field": "link_width",
                                "sortable": True,
                                "align": "right",
                            },
                            {
                                "name": "tx_minor",
                                "label": "TX Minor",
                                "field": "tx_minor",
                                "sortable": True,
                                "align": "right",
                            },
                            {
                                "name": "rx_minor",
                                "label": "RX Minor",
                                "field": "rx_minor",
                                "sortable": True,
                                "align": "right",
                            },
                        ]

                        rows = [
                            {
                                "timestamp": entry.timestamp,
                                "link_state_str": entry.link_state_str,
                                "link_state": entry.link_state,
                                "link_rate": entry.link_rate,
                                "link_width": entry.link_width,
                                "tx_minor": entry.tx_minor_state,
                                "rx_minor": entry.rx_minor_state,
                            }
                            for entry in entries
                        ]

                        ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="timestamp",
                            pagination={"rowsPerPage": 20},
                        ).classes("w-full")
                    else:
                        ui.label(
                            "No log entries."
                        ).classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )

                entry_count = len(entries)
                ui.notify(
                    f"Captured {entry_count} LTSSM log entries",
                    type="positive" if entry_count > 0 else "info",
                    position="top",
                )

            except SwitchtecError as exc:
                ui.notify(
                    f"LTSSM capture failed: {exc}",
                    type="negative", position="top",
                )
            finally:
                capture_btn.props(remove="loading")

        async def _on_clear() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port_id = int(port_id_input.value or 0)

            clear_btn.props("loading")
            try:
                await run.io_bound(
                    dev.diagnostics.ltssm_clear, port_id,
                )

                # Reset displays
                timeline_container.clear()
                with timeline_container:
                    ui.label(
                        "Log cleared. Capture a new log to view the timeline."
                    ).classes("text-subtitle2").style(
                        f"color: {COLORS.text_secondary};"
                    )

                graph_container.clear()
                with graph_container:
                    ui.label(
                        "Log cleared. Capture a new log to view the state graph."
                    ).classes("text-subtitle2").style(
                        f"color: {COLORS.text_secondary};"
                    )

                table_container.clear()
                with table_container:
                    ui.label(
                        "No log entries yet."
                    ).classes("text-subtitle2").style(
                        f"color: {COLORS.text_secondary};"
                    )

                ui.notify(
                    f"LTSSM log cleared for port {port_id}",
                    type="info", position="top",
                )
            except SwitchtecError as exc:
                ui.notify(
                    f"Clear failed: {exc}",
                    type="negative", position="top",
                )
            finally:
                clear_btn.props(remove="loading")

        capture_btn.on_click(_on_capture)
        clear_btn.on_click(_on_clear)
