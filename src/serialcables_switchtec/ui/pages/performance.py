"""Performance monitoring page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def performance_page() -> None:
    """Live bandwidth and latency charts."""
    with page_layout("Performance", current_path="/performance"):
        ui.label("Performance Monitoring").classes("text-h5 q-mb-md")

        with ui.row().classes("w-full q-gutter-md"):
            with ui.card().classes("col q-pa-md"):
                ui.label("Bandwidth Counters").classes("text-h6 q-mb-sm")
                ui.label("Connect to a device and select ports to monitor.").classes(
                    "text-subtitle2"
                )

            with ui.card().classes("col q-pa-md"):
                ui.label("Latency Counters").classes("text-h6 q-mb-sm")
                ui.label("Configure egress/ingress port pair for measurement.").classes(
                    "text-subtitle2"
                )
