"""LTSSM state trace page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def ltssm_trace_page() -> None:
    """LTSSM state machine timeline display."""
    with page_layout("LTSSM Trace", current_path="/ltssm"):
        ui.label("LTSSM State Trace").classes("text-h5 q-mb-md")

        with ui.card().classes("w-full q-pa-md q-mb-md"):
            with ui.row().classes("q-gutter-sm items-end"):
                ui.number(label="Port ID", value=0, min=0, max=59)
                ui.number(label="Max Entries", value=64, min=1, max=256)
                ui.button("Capture Log", icon="history").props("color=primary")
                ui.button("Clear Log", icon="delete").props("color=negative")

        with ui.card().classes("w-full q-pa-md"):
            ui.label("LTSSM Timeline").classes("text-h6 q-mb-sm")
            ui.label("Capture a log to view the LTSSM timeline.").classes("text-subtitle2")
