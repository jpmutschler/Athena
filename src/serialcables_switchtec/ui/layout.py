"""Shared page scaffold with header and sidebar navigation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS, apply_dark_theme, gen_color

_NAV_ITEMS = [
    ("Discovery", "/", "search"),
    ("Dashboard", "/dashboard", "dashboard"),
    ("Ports", "/ports", "device_hub"),
    ("Eye Diagram", "/eye", "visibility"),
    ("LTSSM Trace", "/ltssm", "timeline"),
    ("Performance", "/performance", "speed"),
]


@contextmanager
def page_layout(
    title: str = "Dashboard",
    current_path: str = "/",
) -> Generator[None, None, None]:
    """Shared page layout with header, sidebar, and content area.

    Args:
        title: Page title displayed in the header.
        current_path: URL path of the current page for nav highlighting.
    """
    from serialcables_switchtec.ui import state

    ui.add_css(apply_dark_theme())

    # --- Header ---
    with ui.header(elevated=True).classes("q-pa-sm"):
        with ui.row().classes("w-full items-center no-wrap q-gutter-md"):
            ui.image("/static/logo.png").style(
                "width: 32px; height: 32px;"
            )
            ui.label("ATHENA").classes("text-h6 text-bold").style(
                f"color: {COLORS.accent}; letter-spacing: 0.15em;"
            )
            ui.label("|").style(f"color: {COLORS.text_muted};")
            ui.label("Serial Cables Switchtec Switch Manager").classes(
                "text-subtitle2"
            ).style(f"color: {COLORS.text_secondary};")

            ui.space()

            # Device context in header (uses cached summary, no I/O)
            if state.is_connected():
                summary = state.get_summary()
                if summary:
                    color = gen_color(summary.generation)
                    ui.icon("memory").style(f"color: {color};")
                    ui.label(summary.name).classes("text-subtitle2").style(
                        f"color: {COLORS.text_primary};"
                    )
                    ui.badge(summary.generation).style(
                        f"background-color: {color};"
                    )
                    ui.label(f"{summary.die_temperature:.0f}\u00b0C").classes(
                        "text-caption"
                    ).style(f"color: {COLORS.text_secondary};")
                    ui.button(
                        icon="link_off",
                        on_click=_on_disconnect,
                    ).props("flat dense round size=sm").tooltip("Disconnect")
            else:
                ui.label("No device").classes("text-caption").style(
                    f"color: {COLORS.text_muted};"
                )

            ui.label(title).classes("text-subtitle1").style(
                f"color: {COLORS.text_primary};"
            )

    # --- Sidebar navigation ---
    with ui.left_drawer(value=True).classes("q-pa-md"):
        ui.label("Navigation").classes("text-h6 q-mb-md").style(
            f"color: {COLORS.text_primary};"
        )
        for label, path, icon in _NAV_ITEMS:
            is_active = path == current_path
            bg = f"background-color: {COLORS.bg_card};" if is_active else ""
            border = (
                f"border-left: 3px solid {COLORS.accent}; padding-left: 8px;"
                if is_active
                else "border-left: 3px solid transparent; padding-left: 8px;"
            )
            font_weight = "font-weight: 600;" if is_active else ""
            color = COLORS.accent if is_active else COLORS.text_secondary

            with ui.row().classes("items-center q-mb-xs q-pa-xs").style(
                f"{bg}{border} border-radius: 4px; cursor: pointer; {font_weight}"
            ).on("click", lambda _, p=path: ui.navigate.to(p)):
                ui.icon(icon).style(f"color: {color}; font-size: 1.2em;")
                ui.label(label).style(
                    f"color: {color}; text-decoration: none;"
                )

    with ui.column().classes("w-full q-pa-md"):
        yield


def _on_disconnect() -> None:
    """Disconnect from the active device and navigate to discovery."""
    from serialcables_switchtec.ui import state

    state.disconnect_device()
    ui.notify("Disconnected", type="info", position="top")
    ui.navigate.to("/")
