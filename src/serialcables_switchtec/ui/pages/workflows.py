"""Workflow recipes page with functional recipe runner."""

from __future__ import annotations

import queue
import threading

from nicegui import run, ui

from serialcables_switchtec.core.workflows import RECIPE_REGISTRY, get_recipes_by_category
from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeResult,
    RecipeSummary,
    StepStatus,
)
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.recipe_card import recipe_card
from serialcables_switchtec.ui.components.recipe_stepper import RecipeStepper
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

# ---------------------------------------------------------------------------
# Scaffold recipes that don't have a core implementation yet
# ---------------------------------------------------------------------------

_SCAFFOLD_RECIPES: list[dict[str, str]] = [
    {"category": "link_health", "name": "Link Health Check", "description": "Quick sanity check on a single port.", "duration": "~2s"},
    {"category": "link_health", "name": "Link Training Debug", "description": "Debug link training failures.", "duration": "~5s"},
    {"category": "link_health", "name": "LTSSM State Monitor", "description": "Continuously poll LTSSM state.", "duration": "30s"},
    {"category": "signal_integrity", "name": "Eye Diagram Quick Scan", "description": "Capture an eye diagram with defaults.", "duration": "~30s"},
    {"category": "signal_integrity", "name": "Cross-Hair Margin Analysis", "description": "Quantitative margin measurement.", "duration": "~10s/lane"},
    {"category": "signal_integrity", "name": "Port Equalization Report", "description": "Full equalization snapshot.", "duration": "~3s"},
    {"category": "error_testing", "name": "Error Injection + Recovery", "description": "Inject error and verify recovery.", "duration": "~5s"},
    {"category": "performance", "name": "Bandwidth Baseline", "description": "Sample bandwidth counters.", "duration": "10s"},
    {"category": "performance", "name": "Latency Measurement Profile", "description": "Measure switch traversal latency.", "duration": "~5s"},
    {"category": "performance", "name": "Event Counter Stress Baseline", "description": "Baseline event counter rates.", "duration": "30s"},
    {"category": "configuration", "name": "Config Space Dump", "description": "Read and decode PCI config space.", "duration": "~2s"},
    {"category": "configuration", "name": "Firmware Validation", "description": "Check firmware version and partitions.", "duration": "~2s"},
    {"category": "configuration", "name": "Fabric Bind/Unbind Validation", "description": "Bind/unbind round-trip test.", "duration": "~5s"},
    {"category": "debug", "name": "OSA Link Training Capture", "description": "Capture ordered sets via OSA.", "duration": "~10s"},
    {"category": "debug", "name": "Switch Thermal Profile", "description": "Sample temperatures over time.", "duration": "60s"},
]

_CATEGORIES: list[tuple[str, str, str]] = [
    ("link_health", "Link Health", "monitor_heart"),
    ("signal_integrity", "Signal Integrity", "ssid_chart"),
    ("error_testing", "Error Testing", "bug_report"),
    ("performance", "Performance", "speed"),
    ("configuration", "Configuration", "settings"),
    ("debug", "Debug", "pest_control"),
]

# Map category strings to the enum
_CAT_MAP: dict[str, RecipeCategory] = {c.value: c for c in RecipeCategory}


def workflows_page() -> None:
    """Workflow recipes page with functional recipe runner."""
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

        # --- Runner state ---
        runner_state: dict = {
            "cancel_event": None,
            "timer": None,
            "queue": None,
            "results": [],
            "stepper": None,
            "running": False,
        }

        # --- Recipe Runner Panel ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Recipe Runner").classes("text-h6 q-mb-sm")
            runner_status = ui.label("Select a recipe and click Run.").classes(
                "text-subtitle2"
            ).style(f"color: {COLORS.text_secondary};")

            cancel_btn = ui.button(
                "Cancel", icon="cancel",
            ).props("color=negative flat")
            cancel_btn.set_visibility(False)

            runner_container = ui.column().classes("w-full q-mt-sm")

        def _on_cancel() -> None:
            evt = runner_state.get("cancel_event")
            if evt is not None:
                evt.set()
            runner_status.set_text("Cancelling...")
            cancel_btn.set_enabled(False)

        cancel_btn.on_click(_on_cancel)

        def _on_run_recipe(recipe: Recipe, params: dict) -> None:
            if runner_state["running"]:
                ui.notify("A recipe is already running", type="warning", position="top")
                return

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            # Setup
            cancel_event = threading.Event()
            result_queue: queue.Queue[RecipeResult | RecipeSummary | None] = queue.Queue()
            runner_state["cancel_event"] = cancel_event
            runner_state["queue"] = result_queue
            runner_state["results"] = []
            runner_state["running"] = True

            runner_container.clear()
            stepper = RecipeStepper(runner_container)
            runner_state["stepper"] = stepper

            runner_status.set_text(f"Running: {recipe.name}...")
            cancel_btn.set_visibility(True)
            cancel_btn.set_enabled(True)

            def _run_in_thread() -> None:
                try:
                    gen = recipe.run(dev, cancel_event, **params)
                    summary = None
                    try:
                        while True:
                            result = next(gen)
                            result_queue.put(result)
                    except StopIteration as stop:
                        summary = stop.value
                    if summary is not None:
                        result_queue.put(summary)
                except Exception as exc:
                    # Put a fail result for unexpected errors
                    fail = RecipeResult(
                        recipe_name=recipe.name,
                        step="Unexpected error",
                        step_index=0,
                        total_steps=1,
                        status=StepStatus.FAIL,
                        detail=str(exc),
                    )
                    result_queue.put(fail)
                    result_queue.put(None)
                finally:
                    result_queue.put(None)  # Sentinel

            threading.Thread(target=_run_in_thread, daemon=True).start()

            def _drain_queue() -> None:
                stepper_ref = runner_state["stepper"]
                results_list = runner_state["results"]
                q = runner_state["queue"]
                if q is None:
                    return

                drained = False
                while not q.empty():
                    item = q.get_nowait()
                    if item is None:
                        # Done
                        drained = True
                        break
                    if isinstance(item, RecipeSummary):
                        stepper_ref.render_summary(item)
                        runner_status.set_text(f"Completed: {recipe.name}")
                        drained = True
                        break
                    # It's a RecipeResult
                    if item.status != StepStatus.RUNNING:
                        results_list.append(item)
                    stepper_ref.render_results(
                        [*results_list] if item.status != StepStatus.RUNNING
                        else [*results_list, item]
                    )

                if drained:
                    timer = runner_state.get("timer")
                    if timer is not None:
                        timer.cancel()
                        runner_state["timer"] = None
                    runner_state["running"] = False
                    cancel_btn.set_visibility(False)

            runner_state["timer"] = ui.timer(0.2, _drain_queue)

        # --- Category Tabs ---
        with ui.tabs().classes("w-full") as tabs:
            tab_map: dict[str, ui.tab] = {}
            for cat_id, cat_label, cat_icon in _CATEGORIES:
                tab_map[cat_id] = ui.tab(cat_label, icon=cat_icon)

        with ui.tab_panels(tabs, value=tab_map["link_health"]).classes(
            "w-full"
        ).style(f"background-color: {COLORS.bg_primary};"):
            for cat_id, _cat_label, _cat_icon in _CATEGORIES:
                with ui.tab_panel(tab_map[cat_id]):
                    _render_category(cat_id, _on_run_recipe)


def _render_category(
    cat_id: str,
    on_run: object,
) -> None:
    """Render recipe cards for a category, mixing implemented and scaffold recipes."""
    cat_enum = _CAT_MAP.get(cat_id)
    implemented: list[Recipe] = []
    if cat_enum is not None:
        implemented = get_recipes_by_category(cat_enum)

    implemented_names = {r.name for r in implemented}

    with ui.row().classes("w-full q-gutter-md flex-wrap"):
        # Implemented recipes with full parameter cards
        for r in implemented:
            recipe_card(r, on_run)

        # Scaffold recipes (not yet implemented)
        for scaffold in _SCAFFOLD_RECIPES:
            if scaffold["category"] == cat_id and scaffold["name"] not in implemented_names:
                _scaffold_card(scaffold)


def _scaffold_card(recipe: dict[str, str]) -> None:
    """Render a disabled scaffold recipe card."""
    with ui.card().classes("q-pa-md").style(
        f"min-width: 300px; max-width: 420px; flex: 1 1 300px;"
        f" border: 1px solid {COLORS.text_muted}; opacity: 0.7;"
    ):
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            ui.label(recipe["name"]).classes("text-subtitle1 text-bold").style(
                f"color: {COLORS.text_primary};"
            )
            ui.badge(recipe["duration"]).style(
                f"background-color: {COLORS.bg_secondary};"
                f" color: {COLORS.text_secondary};"
            )

        ui.label(recipe["description"]).classes("text-body2").style(
            f"color: {COLORS.text_secondary};"
        )

        ui.separator().classes("q-my-sm")
        ui.button(
            "Run", icon="play_arrow",
        ).props("disable unelevated dense").style(
            f"background-color: {COLORS.bg_secondary};"
            f" color: {COLORS.text_muted};"
        ).tooltip("Coming soon")
