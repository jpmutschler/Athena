"""Eye diagram capture and display page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def eye_diagram_page() -> None:
    """Eye diagram capture controls and heatmap display."""
    with page_layout("Eye Diagram", current_path="/eye"):
        ui.label("Eye Diagram Capture").classes("text-h5 q-mb-md")

        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Capture Settings").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm"):
                ui.number(label="Port ID", value=0, min=0, max=59)
                ui.number(label="Lane ID", value=0, min=0, max=143)
                ui.number(label="Step Interval (ms)", value=10, min=1)

            with ui.row().classes("q-mt-sm"):
                ui.button("Start Capture", icon="play_arrow").props("color=positive")
                ui.button("Cancel", icon="stop").props("color=negative")

        with ui.card().classes("w-full q-pa-md"):
            ui.label("Eye Diagram").classes("text-h6 q-mb-sm")
            ui.label("Start a capture to view the eye diagram.").classes("text-subtitle2")
