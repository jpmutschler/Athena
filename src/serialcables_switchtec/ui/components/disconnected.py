"""Shared disconnected/empty state components."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS


def show_disconnected() -> None:
    """Show disconnected state with guidance to Discovery page."""
    with ui.column().classes("w-full items-center q-mt-xl"):
        ui.icon("link_off").classes("text-h1").style(
            f"color: {COLORS.text_muted};"
        )
        ui.label("No Device Connected").classes("text-h5 q-mt-md").style(
            f"color: {COLORS.text_secondary};"
        )
        ui.label(
            "Go to Discovery to scan and connect to a Switchtec device."
        ).style(f"color: {COLORS.text_muted};")
        ui.button(
            "Go to Discovery",
            icon="search",
            on_click=lambda: ui.navigate.to("/"),
        ).props("color=primary outline").classes("q-mt-md")
