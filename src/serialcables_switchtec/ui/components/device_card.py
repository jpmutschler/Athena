"""Device information card component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.models.device import DeviceSummary
from serialcables_switchtec.ui.theme import GEN_COLORS, SC_SUCCESS


def device_card(summary: DeviceSummary) -> None:
    """Render a device summary card."""
    gen_color = GEN_COLORS.get(int(summary.generation[-1]) if summary.generation[-1].isdigit() else 0, "#9e9e9e")

    with ui.card().classes("w-full q-pa-md"):
        with ui.row().classes("items-center q-mb-sm"):
            ui.icon("memory").classes("text-h5").style(f"color: {gen_color}")
            ui.label(summary.name).classes("text-h6 q-ml-sm")
            ui.badge(summary.generation).props(f'color="{gen_color}"')

        with ui.grid(columns=2).classes("w-full"):
            ui.label("Device ID:").classes("text-bold")
            ui.label(f"0x{summary.device_id:04x}")

            ui.label("Variant:").classes("text-bold")
            ui.label(summary.variant)

            ui.label("Boot Phase:").classes("text-bold")
            ui.label(summary.boot_phase)

            ui.label("FW Version:").classes("text-bold")
            ui.label(summary.fw_version)

            ui.label("Temperature:").classes("text-bold")
            ui.label(f"{summary.die_temperature:.1f} C")

            ui.label("Ports:").classes("text-bold")
            ui.label(str(summary.port_count))
