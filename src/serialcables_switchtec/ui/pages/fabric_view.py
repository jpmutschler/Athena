"""Fabric View page -- multi-device topology dashboard."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def fabric_view_page() -> None:
    """Render the Fabric View page."""
    with page_layout(title="Fabric View", current_path="/fabric-view"):
        ui.label("Fabric View").classes("text-h5 q-mb-md").style(
            f"color: {COLORS.text_primary};"
        )
        with ui.card().classes("q-pa-lg"):
            ui.icon("account_tree").classes("text-h3 q-mb-md").style(
                f"color: {COLORS.accent};"
            )
            ui.label("Multi-Device Fabric Topology").classes(
                "text-h6 q-mb-sm"
            ).style(f"color: {COLORS.text_primary};")
            ui.label(
                "This page will provide an aggregate view of all connected "
                "Switchtec devices in a PAX fabric, with topology "
                "visualization, cross-device health monitoring, and "
                "coordinated fabric management."
            ).style(f"color: {COLORS.text_secondary};")
            ui.separator().classes("q-my-md")
            ui.label("Planned features:").style(
                f"color: {COLORS.text_primary}; font-weight: 600;"
            )
            features = [
                "Multi-device connection (connect N switches simultaneously)",
                "Topology graph visualization (switches, ports, links)",
                "Aggregate port status across all connected devices",
                "Per-device health cards (temperature, firmware, link summary)",
                "Device selector for navigating to per-device detail pages",
                "Fabric-level GFMS bind/unbind operations",
            ]
            for feat in features:
                with ui.row().classes("items-center q-mb-xs"):
                    ui.icon("check_circle_outline").style(
                        f"color: {COLORS.text_muted}; font-size: 1em;"
                    )
                    ui.label(feat).style(
                        f"color: {COLORS.text_secondary}; font-size: 0.9em;"
                    )
            ui.separator().classes("q-my-md")
            ui.label(
                "In the meantime, single-device fabric operations are "
                "available on the Fabric page."
            ).style(f"color: {COLORS.text_muted}; font-style: italic;")
