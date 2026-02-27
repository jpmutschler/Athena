"""Shared page scaffold with header and sidebar navigation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS, apply_dark_theme


@contextmanager
def page_layout(title: str = "Dashboard") -> Generator[None, None, None]:
    """Shared page layout with header, sidebar, and content area."""
    ui.add_css(apply_dark_theme())

    with ui.header(elevated=True).classes("q-pa-sm"):
        with ui.row().classes("w-full items-center no-wrap q-gutter-md"):
            ui.image("/static/logo.png").style(
                "width: 32px; height: 32px;"
            )
            ui.label("ATHENA").classes("text-h6 text-bold").style(
                f"color: {COLORS.cyan}; letter-spacing: 0.15em;"
            )
            ui.label("|").style(f"color: {COLORS.text_muted};")
            ui.label("Serial Cables Switchtec Switch Manager").classes(
                "text-subtitle2"
            ).style(f"color: {COLORS.text_secondary};")
            ui.space()
            ui.label(title).classes("text-subtitle1").style(
                f"color: {COLORS.text_primary};"
            )

    with ui.left_drawer(value=True).classes("q-pa-md"):
        ui.label("Navigation").classes("text-h6 q-mb-md").style(
            f"color: {COLORS.text_primary};"
        )
        ui.link("Discovery", "/").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )
        ui.link("Dashboard", "/dashboard").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )
        ui.link("Ports", "/ports").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )
        ui.link("Eye Diagram", "/eye").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )
        ui.link("LTSSM Trace", "/ltssm").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )
        ui.link("Performance", "/performance").classes("q-mb-sm block").style(
            f"color: {COLORS.cyan}; text-decoration: none;"
        )

    with ui.column().classes("w-full q-pa-md"):
        yield
