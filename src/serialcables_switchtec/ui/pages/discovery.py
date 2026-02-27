"""Device discovery page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout


def discovery_page() -> None:
    """Device discovery and connection page."""
    with page_layout("Device Discovery"):
        ui.label("Switchtec Device Discovery").classes("text-h5 q-mb-md")

        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Connect to Device").classes("text-h6 q-mb-sm")

            device_path = ui.input(
                label="Device Path",
                placeholder="/dev/switchtec0",
            ).classes("w-full q-mb-sm")

            with ui.row():
                ui.button("Scan", icon="search").props("color=primary")
                ui.button("Connect", icon="link").props("color=positive")

        with ui.card().classes("w-full q-pa-md"):
            ui.label("Discovered Devices").classes("text-h6 q-mb-sm")
            ui.label("Click 'Scan' to discover devices").classes("text-subtitle2")
