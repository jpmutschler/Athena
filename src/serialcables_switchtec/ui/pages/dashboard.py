"""Main dashboard page with device overview."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def dashboard_page() -> None:
    """Main dashboard showing switch overview."""
    with page_layout("Dashboard"):
        ui.label("Switch Overview").classes("text-h5 q-mb-md")

        with ui.row().classes("w-full q-gutter-md"):
            with ui.card().classes("col q-pa-md"):
                ui.label("Temperature").classes("text-h6")
                ui.label("-- C").classes("text-h4 text-positive")

            with ui.card().classes("col q-pa-md"):
                ui.label("Generation").classes("text-h6")
                ui.label("--").classes("text-h4 text-accent")

            with ui.card().classes("col q-pa-md"):
                ui.label("Active Ports").classes("text-h6")
                ui.label("--").classes("text-h4 text-info")

            with ui.card().classes("col q-pa-md"):
                ui.label("FW Version").classes("text-h6")
                ui.label("--").classes("text-h4")

        ui.label("No device connected. Go to Discovery to connect.").classes(
            "text-subtitle1 q-mt-lg"
        )
