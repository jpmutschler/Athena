"""Shared page scaffold with header and sidebar navigation."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from nicegui import ui

from serialcables_switchtec.ui.theme import SC_BLUE, apply_dark_theme


@contextmanager
def page_layout(title: str = "Switchtec Dashboard") -> Generator[None, None, None]:
    """Shared page layout with header, sidebar, and content area."""
    ui.add_css(apply_dark_theme())

    with ui.header().classes("items-center justify-between"):
        ui.label("Serial Cables Switchtec").classes("text-h6 text-white")
        ui.label(title).classes("text-subtitle1 text-white q-ml-md")

    with ui.left_drawer(value=True).classes("q-pa-md"):
        ui.label("Navigation").classes("text-h6 q-mb-md")
        ui.link("Discovery", "/").classes("text-white q-mb-sm block")
        ui.link("Dashboard", "/dashboard").classes("text-white q-mb-sm block")
        ui.link("Ports", "/ports").classes("text-white q-mb-sm block")
        ui.link("Eye Diagram", "/eye").classes("text-white q-mb-sm block")
        ui.link("LTSSM Trace", "/ltssm").classes("text-white q-mb-sm block")
        ui.link("Performance", "/performance").classes("text-white q-mb-sm block")

    with ui.column().classes("w-full q-pa-md"):
        yield
