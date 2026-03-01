"""Workflow recipes scaffold page.

Displays planned workflow recipes organized by category as a stakeholder
preview.  The core recipe system is not yet implemented -- Run buttons
are disabled with a "Coming soon" tooltip.
"""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

# ---------------------------------------------------------------------------
# Recipe data (hardcoded scaffold -- mirrors docs/architecture/workflow-recipes.md)
# ---------------------------------------------------------------------------

_CATEGORIES: list[tuple[str, str, str]] = [
    ("link_health", "Link Health", "monitor_heart"),
    ("signal_integrity", "Signal Integrity", "ssid_chart"),
    ("error_testing", "Error Testing", "bug_report"),
    ("performance", "Performance", "speed"),
    ("configuration", "Configuration", "settings"),
    ("debug", "Debug", "pest_control"),
]

_RECIPES: list[dict[str, str | int]] = [
    # --- Link Health ---
    {
        "category": "link_health",
        "name": "All-Port Status Sweep",
        "description": (
            "Scan every port on the switch for link status, width, rate, "
            "LTSSM state, and die temperature.  One-click overview of the "
            "entire switch."
        ),
        "duration": "~3s",
    },
    {
        "category": "link_health",
        "name": "Link Health Check",
        "description": (
            "Quick sanity check on a single port: link state, width "
            "degradation, temperature, event counters, bandwidth, and "
            "recent LTSSM transitions."
        ),
        "duration": "~2s",
    },
    {
        "category": "link_health",
        "name": "Link Training Debug",
        "description": (
            "Debug link training failures.  Clears the LTSSM log, reads "
            "EQ status and TX coefficients, then captures the full "
            "transition history."
        ),
        "duration": "~5s",
    },
    {
        "category": "link_health",
        "name": "LTSSM State Monitor",
        "description": (
            "Continuously poll LTSSM state to detect intermittent "
            "retraining events.  Reports transition counts and "
            "time-in-state breakdown."
        ),
        "duration": "30s (configurable)",
    },
    # --- Signal Integrity ---
    {
        "category": "signal_integrity",
        "name": "Eye Diagram Quick Scan",
        "description": (
            "Capture an eye diagram with sensible defaults and compute "
            "eye opening metrics (height, width)."
        ),
        "duration": "~30s",
    },
    {
        "category": "signal_integrity",
        "name": "Cross-Hair Margin Analysis",
        "description": (
            "Quantitative margin measurement via cross-hair sweep.  "
            "Reports horizontal (mUI) and vertical (mV) margins with "
            "pass/fail thresholds."
        ),
        "duration": "~10s/lane",
    },
    {
        "category": "signal_integrity",
        "name": "Port Equalization Report",
        "description": (
            "Full equalization snapshot: TX coefficients (local and far "
            "end), EQ table with FOM, FS/LF values, and receiver "
            "calibration per lane."
        ),
        "duration": "~3s",
    },
    # --- Error Testing ---
    {
        "category": "error_testing",
        "name": "BER Soak Test",
        "description": (
            "Run a pattern generator for a configurable duration and "
            "measure bit error rate.  Checks for link retraining during "
            "the soak."
        ),
        "duration": "60s (configurable)",
    },
    {
        "category": "error_testing",
        "name": "Loopback BER Sweep",
        "description": (
            "Enable loopback and sweep all PRBS patterns for the "
            "selected generation.  Identifies the weakest pattern and "
            "worst-case BER."
        ),
        "duration": "varies",
    },
    {
        "category": "error_testing",
        "name": "Error Injection + Recovery",
        "description": (
            "Inject a selected error type (DLLP CRC, TLP LCRC, etc.) "
            "and verify the link detects, counts, and recovers from the "
            "error."
        ),
        "duration": "~5s",
    },
    # --- Performance ---
    {
        "category": "performance",
        "name": "Bandwidth Baseline",
        "description": (
            "Sample bandwidth counters across selected ports and report "
            "average, peak, and minimum throughput with traffic breakdown."
        ),
        "duration": "10s (configurable)",
    },
    {
        "category": "performance",
        "name": "Latency Measurement Profile",
        "description": (
            "Measure switch traversal latency between ingress and egress "
            "ports.  Reports min, avg, p50, p95, p99, and max in "
            "nanoseconds."
        ),
        "duration": "~5s",
    },
    {
        "category": "performance",
        "name": "Event Counter Stress Baseline",
        "description": (
            "Configure and sample event counters over a duration to "
            "establish baseline rates under idle or load conditions."
        ),
        "duration": "30s (configurable)",
    },
    # --- Configuration ---
    {
        "category": "configuration",
        "name": "Config Space Dump",
        "description": (
            "Read and decode PCI config space: header, capability list, "
            "PCIe/AER registers with bit-field decode."
        ),
        "duration": "~2s",
    },
    {
        "category": "configuration",
        "name": "Firmware Validation",
        "description": (
            "Check firmware version, partition summary, boot phase, and "
            "compare active vs inactive partitions."
        ),
        "duration": "~2s",
    },
    {
        "category": "configuration",
        "name": "Fabric Bind/Unbind Validation",
        "description": (
            "Perform a bind/unbind round-trip on a port and verify the "
            "operation succeeds via port config and GFMS events."
        ),
        "duration": "~5s",
    },
    # --- Debug ---
    {
        "category": "debug",
        "name": "OSA Link Training Capture",
        "description": (
            "Configure the on-chip signal analyzer to capture ordered "
            "sets or LTSSM transitions during link training or retrain "
            "events."
        ),
        "duration": "~10s",
    },
    {
        "category": "debug",
        "name": "Switch Thermal Profile",
        "description": (
            "Sample per-die temperatures over time and report min/avg/max "
            "with trend analysis and thermal throttle risk assessment."
        ),
        "duration": "60s (configurable)",
    },
]


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def workflows_page() -> None:
    """Workflow recipes page -- scaffold with category tabs and recipe cards."""
    from serialcables_switchtec.ui import state

    with page_layout("Workflows", current_path="/workflows"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Workflow Recipes").classes("text-h5 q-mb-sm")
        ui.label(
            "Pre-composed validation workflows. Select a category "
            "to browse available recipes."
        ).classes("text-subtitle2 q-mb-md").style(
            f"color: {COLORS.text_secondary};"
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_map: dict[str, ui.tab] = {}
            for cat_id, cat_label, cat_icon in _CATEGORIES:
                tab_map[cat_id] = ui.tab(cat_label, icon=cat_icon)

        with ui.tab_panels(tabs, value=tab_map["link_health"]).classes(
            "w-full"
        ).style(f"background-color: {COLORS.bg_primary};"):
            for cat_id, _cat_label, _cat_icon in _CATEGORIES:
                with ui.tab_panel(tab_map[cat_id]):
                    cat_recipes = [
                        r for r in _RECIPES if r["category"] == cat_id
                    ]
                    _render_recipe_grid(cat_recipes)


def _render_recipe_grid(recipes: list[dict[str, str | int]]) -> None:
    """Render a grid of recipe cards for one category."""
    with ui.row().classes("w-full q-gutter-md flex-wrap"):
        for recipe in recipes:
            _recipe_card(recipe)


def _recipe_card(recipe: dict[str, str | int]) -> None:
    """Render a single recipe card with name, description, duration, and disabled Run button."""
    with ui.card().classes("q-pa-md").style(
        f"min-width: 300px; max-width: 420px; flex: 1 1 300px;"
        f" border: 1px solid {COLORS.text_muted};"
    ):
        # Header row: name + duration badge
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            ui.label(str(recipe["name"])).classes("text-subtitle1 text-bold").style(
                f"color: {COLORS.text_primary};"
            )
            ui.badge(str(recipe["duration"])).style(
                f"background-color: {COLORS.bg_secondary};"
                f" color: {COLORS.text_secondary};"
            )

        # Description
        ui.label(str(recipe["description"])).classes("text-body2").style(
            f"color: {COLORS.text_secondary};"
        )

        # Disabled Run button
        ui.separator().classes("q-my-sm")
        ui.button(
            "Run", icon="play_arrow",
        ).props("disable unelevated dense").style(
            f"background-color: {COLORS.bg_secondary};"
            f" color: {COLORS.text_muted};"
        ).tooltip("Coming soon -- recipe system in development")
