"""Margin Testing page -- dedicated cross-hair lane margining dashboard."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def margin_testing_page() -> None:
    """Render the Margin Testing page."""
    with page_layout(title="Margin Testing", current_path="/margin"):
        ui.label("Margin Testing").classes("text-h5 q-mb-md").style(
            f"color: {COLORS.text_primary};"
        )
        with ui.card().classes("q-pa-lg"):
            ui.icon("straighten").classes("text-h3 q-mb-md").style(
                f"color: {COLORS.accent};"
            )
            ui.label("Cross-Hair Lane Margin Analysis").classes(
                "text-h6 q-mb-sm"
            ).style(f"color: {COLORS.text_primary};")
            ui.label(
                "This page will provide dedicated cross-hair margin testing "
                "with multi-port sweep, per-lane diamond plots, historical "
                "comparison, and generation-aware thresholds (NRZ vs PAM4)."
            ).style(f"color: {COLORS.text_secondary};")
            ui.separator().classes("q-my-md")
            ui.label("Planned features:").style(
                f"color: {COLORS.text_primary}; font-weight: 600;"
            )
            features = [
                "Multi-port margin sweep (all active ports sequentially)",
                "Per-lane diamond plot visualization with PASS/FAIL overlay",
                "Configurable thresholds per generation (Gen5 NRZ vs Gen6 PAM4)",
                "All-ports margin heatmap (port x lane grid, color by margin)",
                "CSV/JSON export of margin data",
                "Receiver calibration readout (CTLE, DFE taps, target amplitude)",
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
                "In the meantime, cross-hair margin testing is available "
                "on the Equalization page (section 4)."
            ).style(f"color: {COLORS.text_muted}; font-style: italic;")
