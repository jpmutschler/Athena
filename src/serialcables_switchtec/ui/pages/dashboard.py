"""Main dashboard page with device overview."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.models.device import PortStatus
from serialcables_switchtec.ui.components.device_card import device_card
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import (
    COLORS,
    LINK_DOWN_COLOR,
    LINK_TRAINING_COLOR,
    LINK_UP_COLOR,
    gen_color,
)


def _temp_color(temp: float) -> str:
    """Return a color based on temperature threshold."""
    if temp >= 85.0:
        return COLORS.error
    if temp >= 70.0:
        return COLORS.warning
    return COLORS.success


def dashboard_page() -> None:
    """Main dashboard showing switch overview."""
    from serialcables_switchtec.ui import state

    with page_layout("Dashboard", current_path="/dashboard"):
        if not state.is_connected():
            show_disconnected()
            return

        summary = state.get_summary()
        if summary is None:
            show_disconnected()
            return

        color = gen_color(summary.generation)
        temp_color = _temp_color(summary.die_temperature)

        ui.label("Switch Overview").classes("text-h5 q-mb-md")

        # --- Summary cards row ---
        with ui.row().classes("w-full q-gutter-md q-mb-lg"):
            # Temperature card
            with ui.card().classes("col q-pa-md"):
                ui.label("Temperature").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                ui.label(f"{summary.die_temperature:.1f}\u00b0C").classes(
                    "text-h4"
                ).style(f"color: {temp_color};")

            # Generation card
            with ui.card().classes("col q-pa-md"):
                ui.label("Generation").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                ui.label(summary.generation).classes("text-h4").style(
                    f"color: {color};"
                )

            # Active Ports card
            with ui.card().classes("col q-pa-md"):
                ui.label("Active Ports").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                ports_count_label = ui.label("--").classes(
                    "text-h4"
                ).style(f"color: {COLORS.text_muted};")

            # FW Version card
            with ui.card().classes("col q-pa-md"):
                ui.label("FW Version").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                ui.label(summary.fw_version).classes("text-h4").style(
                    f"color: {COLORS.text_primary};"
                )

        # --- Device detail card ---
        ui.label("Device Details").classes("text-h6 q-mb-sm")
        device_card(summary)

        # --- Port summary (loaded asynchronously to avoid blocking) ---
        port_section_container = ui.column().classes("w-full")

        async def _load_ports() -> None:
            ports = await run.io_bound(state.get_port_status)
            ports_up = sum(1 for p in ports if p.link_up)
            ports_total = len(ports)
            ports_color = COLORS.success if ports_up > 0 else COLORS.error
            ports_count_label.set_text(f"{ports_up} / {ports_total}")
            ports_count_label.style(f"color: {ports_color};")

            port_section_container.clear()
            if ports:
                with port_section_container:
                    ui.label("Port Summary").classes("text-h6 q-mt-lg q-mb-sm")
                    with ui.row().classes("w-full q-gutter-sm flex-wrap"):
                        for p in ports:
                            _port_badge(p)

        ui.timer(0.1, _load_ports, once=True)


def _port_badge(port_status: PortStatus) -> None:
    """Render a compact port status badge."""
    is_up = port_status.link_up
    if is_up:
        color = LINK_UP_COLOR
        status_text = f"x{port_status.neg_lnk_width} Gen{port_status.link_rate}"
    elif port_status.ltssm_str and "L0" not in port_status.ltssm_str:
        color = LINK_TRAINING_COLOR
        status_text = port_status.ltssm_str
    else:
        color = LINK_DOWN_COLOR
        status_text = port_status.ltssm_str or "Down"

    with ui.card().classes("q-pa-xs").style(
        f"border: 1px solid {color}; min-width: 90px; text-align: center;"
        f" background: {COLORS.bg_secondary};"
    ):
        ui.label(f"P{port_status.port.phys_id}").classes(
            "text-caption text-bold"
        ).style(f"color: {color};")
        ui.label(status_text).style(
            f"color: {COLORS.text_secondary}; font-size: 0.7em;"
        )
