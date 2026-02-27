"""Port status page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def ports_page() -> None:
    """Port grid with link status."""
    with page_layout("Port Status"):
        ui.label("Port Status").classes("text-h5 q-mb-md")
        ui.label("Connect to a device to view port status.").classes("text-subtitle1")
