"""Workflow Builder page — create, save, load, and run multi-recipe workflows."""

from __future__ import annotations

import queue
import threading

from nicegui import ui

from serialcables_switchtec.core.workflows import RECIPE_REGISTRY
from serialcables_switchtec.core.workflows.export import DeviceContext
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeResult,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_executor import WorkflowExecutor
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowSummary,
)
from serialcables_switchtec.core.workflows.workflow_storage import WorkflowStorage
from serialcables_switchtec.ui.components.param_inputs import extract_value
from serialcables_switchtec.ui.components.workflow_monitor import WorkflowMonitor
from serialcables_switchtec.ui.components.workflow_step_editor import workflow_step_editor
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.pages.workflow_builder_helpers import (
    collect_advanced_data,
    model_to_step_data,
    step_data_to_model,
)
from serialcables_switchtec.ui.theme import COLORS

# Category labels for grouping recipes in the "Add Step" dropdown
_CATEGORY_LABELS: dict[RecipeCategory, str] = {
    RecipeCategory.LINK_HEALTH: "Link Health",
    RecipeCategory.SIGNAL_INTEGRITY: "Signal Integrity",
    RecipeCategory.ERROR_TESTING: "Error Testing",
    RecipeCategory.PERFORMANCE: "Performance",
    RecipeCategory.CONFIGURATION: "Configuration",
    RecipeCategory.DEBUG: "Debug",
}


def _build_recipe_options() -> dict[str, str]:
    """Build a {recipe_key: display_label} dict grouped by category."""
    options: dict[str, str] = {}
    by_category: dict[RecipeCategory, list[tuple[str, str]]] = {}

    for key, cls in sorted(RECIPE_REGISTRY.items()):
        instance = cls()
        cat = instance.category
        by_category.setdefault(cat, []).append((key, instance.name))

    for cat in RecipeCategory:
        items = by_category.get(cat, [])
        if not items:
            continue
        cat_label = _CATEGORY_LABELS.get(cat, cat.value)
        for recipe_key, recipe_name in items:
            options[recipe_key] = f"[{cat_label}] {recipe_name}"

    return options


def workflow_builder_page() -> None:
    """Render the Workflow Builder page."""
    from serialcables_switchtec.ui import state

    storage = WorkflowStorage()
    recipe_options = _build_recipe_options()

    with page_layout("Workflow Builder", current_path="/workflow-builder"):
        if not state.is_connected():
            from serialcables_switchtec.ui.components.disconnected import show_disconnected

            show_disconnected()
            return

        ui.label("Workflow Builder").classes("text-h5 q-mb-sm")
        ui.label(
            "Create multi-recipe validation workflows. "
            "Add steps, configure parameters, save, and run."
        ).classes("text-subtitle2 q-mb-md").style(
            f"color: {COLORS.text_secondary};"
        )

        # --- Mutable builder state ---
        builder_state: dict = {
            "steps": [],        # list of {recipe_key, label, params, advanced}
            "widgets": [],      # list of widget dicts from step_editor
            "running": False,
            "cancel_event": None,
            "timer": None,
            "queue": None,
            "results": [],
            "monitor": None,
            "definition": None,
            "device_context": None,
            "wf_summary": None,
        }

        # =================================================================
        # Section 1: Workflow Metadata
        # =================================================================
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Workflow Settings").classes("text-subtitle1 text-bold q-mb-sm")
            name_input = ui.input(
                label="Workflow Name",
                value="",
                validation={"Required": lambda v: bool(v.strip())},
            ).classes("w-full").props("dense")

            desc_input = ui.textarea(
                label="Description (optional)",
                value="",
            ).classes("w-full").props("dense rows=2")

            abort_switch = ui.switch(
                "Abort on critical failure",
                value=True,
            )

        # =================================================================
        # Section 2: Step List
        # =================================================================
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Steps").classes("text-subtitle1 text-bold q-mb-sm")

            with ui.row().classes("w-full items-end q-gutter-sm q-mb-sm"):
                add_select = ui.select(
                    options=recipe_options,
                    label="Select a recipe to add",
                    value=None,
                ).classes("flex-grow")

                ui.button(
                    "Add Step", icon="add",
                    on_click=lambda: _add_step(
                        add_select.value,
                        builder_state,
                        steps_container,
                        recipe_options,
                    ),
                ).props("unelevated dense")

            steps_container = ui.column().classes("w-full")

        # =================================================================
        # Section 3: Actions
        # =================================================================
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Actions").classes("text-subtitle1 text-bold q-mb-sm")
            with ui.row().classes("q-gutter-sm"):
                ui.button(
                    "Save",
                    icon="save",
                    on_click=lambda: _on_save(
                        name_input,
                        desc_input,
                        abort_switch,
                        builder_state,
                        storage,
                        load_select,
                    ),
                ).props("unelevated dense")

                load_select = ui.select(
                    options=storage.list_workflows(),
                    label="Load workflow",
                    value=None,
                    on_change=lambda e: _on_load(
                        e.value,
                        storage,
                        name_input,
                        desc_input,
                        abort_switch,
                        builder_state,
                        steps_container,
                        recipe_options,
                    ),
                ).props("dense").classes("min-w-[200px]")

                ui.button(
                    "Delete",
                    icon="delete",
                    on_click=lambda: _on_delete(
                        name_input,
                        storage,
                        load_select,
                    ),
                ).props("unelevated dense color=negative")

                ui.button(
                    "Run Workflow",
                    icon="play_arrow",
                    on_click=lambda: _on_run(
                        name_input,
                        desc_input,
                        abort_switch,
                        builder_state,
                        runner_container,
                        runner_status,
                        cancel_btn,
                    ),
                ).props("unelevated dense color=positive")

        # =================================================================
        # Section 4: Runner Output
        # =================================================================
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Runner Output").classes("text-subtitle1 text-bold q-mb-sm")
            runner_status = ui.label("Configure and run a workflow above.").classes(
                "text-subtitle2"
            ).style(f"color: {COLORS.text_secondary};")

            cancel_btn = ui.button(
                "Cancel", icon="cancel",
            ).props("color=negative flat")
            cancel_btn.set_visibility(False)

            def _on_cancel() -> None:
                evt = builder_state.get("cancel_event")
                if evt is not None:
                    evt.set()
                runner_status.set_text("Cancelling...")
                cancel_btn.set_enabled(False)

            cancel_btn.on_click(_on_cancel)

            runner_container = ui.column().classes("w-full q-mt-sm")


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _collect_step_data(builder_state: dict) -> list[dict]:
    """Read current values from step editor widgets into step dicts.

    Mutates step dicts in place — this is intentional for UI state
    synchronization before save/run/re-render operations.
    """
    steps = builder_state["steps"]
    widgets_list = builder_state["widgets"]

    for step, widgets in zip(steps, widgets_list):
        label_widget = widgets.get("__label__")
        if label_widget is not None:
            step["label"] = getattr(label_widget, "value", "") or ""

        recipe_cls = RECIPE_REGISTRY[step["recipe_key"]]
        recipe = recipe_cls()
        for p in recipe.parameters():
            w = widgets.get(p.name)
            if w is not None:
                step["params"][p.name] = extract_value(p, w)

        adv_widgets = widgets.get("__advanced__", {})
        if adv_widgets:
            step["advanced"] = collect_advanced_data(adv_widgets, recipe)

    return steps


def _build_definition(
    name_input: object,
    desc_input: object,
    abort_switch: object,
    builder_state: dict,
) -> WorkflowDefinition | None:
    """Build a WorkflowDefinition from the current UI state."""
    name = getattr(name_input, "value", "").strip()
    if not name:
        ui.notify("Workflow name is required", type="warning", position="top")
        return None

    steps_data = _collect_step_data(builder_state)
    if not steps_data:
        ui.notify("Add at least one step", type="warning", position="top")
        return None

    workflow_steps = [step_data_to_model(s) for s in steps_data]

    return WorkflowDefinition(
        name=name,
        description=getattr(desc_input, "value", ""),
        steps=workflow_steps,
        abort_on_critical_fail=getattr(abort_switch, "value", True),
    )


def _render_steps(
    builder_state: dict,
    container: ui.column,
    recipe_options: dict[str, str],
) -> None:
    """Clear and re-render all step editor rows."""
    container.clear()
    builder_state["widgets"] = []
    steps = builder_state["steps"]
    total = len(steps)

    with container:
        for idx, step_data in enumerate(steps):
            recipe_cls = RECIPE_REGISTRY[step_data["recipe_key"]]
            recipe = recipe_cls()

            captured_idx = idx

            def make_move_up(i: int = captured_idx):
                def _move():
                    if i > 0:
                        _collect_step_data(builder_state)
                        steps[i], steps[i - 1] = steps[i - 1], steps[i]
                        _render_steps(builder_state, container, recipe_options)
                return _move

            def make_move_down(i: int = captured_idx):
                def _move():
                    if i < len(steps) - 1:
                        _collect_step_data(builder_state)
                        steps[i], steps[i + 1] = steps[i + 1], steps[i]
                        _render_steps(builder_state, container, recipe_options)
                return _move

            def make_remove(i: int = captured_idx):
                def _remove():
                    _collect_step_data(builder_state)
                    steps.pop(i)
                    _render_steps(builder_state, container, recipe_options)
                return _remove

            widgets = workflow_step_editor(
                index=idx,
                total=total,
                recipe=recipe,
                current_params=step_data.get("params", {}),
                current_label=step_data.get("label", ""),
                on_move_up=make_move_up(idx),
                on_move_down=make_move_down(idx),
                on_remove=make_remove(idx),
                current_advanced=step_data.get("advanced"),
            )
            builder_state["widgets"].append(widgets)

    if not steps:
        with container:
            ui.label("No steps added yet.").style(
                f"color: {COLORS.text_muted};"
            )


def _add_step(
    recipe_key: str | None,
    builder_state: dict,
    steps_container: ui.column,
    recipe_options: dict[str, str],
) -> None:
    """Add a recipe step to the builder."""
    if recipe_key is None:
        ui.notify("Select a recipe first", type="warning", position="top")
        return

    _collect_step_data(builder_state)

    builder_state["steps"].append({
        "recipe_key": recipe_key,
        "label": "",
        "params": {},
        "advanced": {},
    })
    _render_steps(builder_state, steps_container, recipe_options)


def _on_save(
    name_input: object,
    desc_input: object,
    abort_switch: object,
    builder_state: dict,
    storage: WorkflowStorage,
    load_select: object,
) -> None:
    """Save the current workflow definition."""
    definition = _build_definition(name_input, desc_input, abort_switch, builder_state)
    if definition is None:
        return

    try:
        path = storage.save(definition)
        ui.notify(f"Saved: {path.name}", type="positive", position="top")
        load_select.options = storage.list_workflows()
        load_select.update()
    except Exception as exc:
        ui.notify(f"Save failed: {exc}", type="negative", position="top")


def _on_load(
    workflow_slug: str | None,
    storage: WorkflowStorage,
    name_input: object,
    desc_input: object,
    abort_switch: object,
    builder_state: dict,
    steps_container: ui.column,
    recipe_options: dict[str, str],
) -> None:
    """Load a saved workflow into the builder."""
    if workflow_slug is None:
        return

    try:
        definition = storage.load(workflow_slug)
    except FileNotFoundError:
        ui.notify(f"Workflow not found: {workflow_slug}", type="negative", position="top")
        return
    except Exception as exc:
        ui.notify(f"Load failed: {exc}", type="negative", position="top")
        return

    name_input.value = definition.name
    desc_input.value = definition.description
    abort_switch.value = definition.abort_on_critical_fail

    builder_state["steps"] = [
        model_to_step_data(step) for step in definition.steps
    ]
    _render_steps(builder_state, steps_container, recipe_options)
    ui.notify(f"Loaded: {definition.name}", type="info", position="top")


def _on_delete(
    name_input: object,
    storage: WorkflowStorage,
    load_select: object,
) -> None:
    """Delete the current workflow from storage."""
    name = getattr(name_input, "value", "").strip()
    if not name:
        ui.notify("Enter a workflow name to delete", type="warning", position="top")
        return

    try:
        storage.delete(name)
        ui.notify(f"Deleted: {name}", type="info", position="top")
        load_select.options = storage.list_workflows()
        load_select.update()
    except Exception as exc:
        ui.notify(f"Delete failed: {exc}", type="negative", position="top")


def _capture_device_context(dev: object) -> DeviceContext:
    """Capture device metadata before workflow execution."""
    from serialcables_switchtec.core.workflows.export import make_device_context

    try:
        return make_device_context(
            device_path=getattr(dev, "path", ""),
            name=getattr(dev, "name", ""),
            device_id=getattr(dev, "device_id", 0),
            generation=getattr(dev, "generation_str", ""),
            fw_version=dev.get_fw_version() if hasattr(dev, "get_fw_version") else "",
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Device context capture failed: %s", exc)
        return make_device_context()


def _on_run(
    name_input: object,
    desc_input: object,
    abort_switch: object,
    builder_state: dict,
    runner_container: ui.column,
    runner_status: object,
    cancel_btn: object,
) -> None:
    """Build a workflow definition and run it."""
    from serialcables_switchtec.ui import state

    if builder_state["running"]:
        ui.notify("A workflow is already running", type="warning", position="top")
        return

    dev = state.get_active_device()
    if dev is None:
        ui.notify("No device connected", type="negative", position="top")
        return

    definition = _build_definition(name_input, desc_input, abort_switch, builder_state)
    if definition is None:
        return

    # Capture device context before execution (device may disconnect later)
    builder_state["device_context"] = _capture_device_context(dev)
    builder_state["definition"] = definition
    builder_state["wf_summary"] = None

    cancel_event = threading.Event()
    result_queue: queue.Queue[RecipeResult | WorkflowSummary | None] = queue.Queue()
    builder_state["cancel_event"] = cancel_event
    builder_state["queue"] = result_queue
    builder_state["results"] = []
    builder_state["running"] = True

    runner_container.clear()

    # Build step keys for the monitor
    step_keys = [
        (idx, step.recipe_key) for idx, step in enumerate(definition.steps)
    ]
    monitor = WorkflowMonitor(runner_container)
    monitor.start(definition.name, len(definition.steps), step_keys)
    builder_state["monitor"] = monitor

    runner_status.set_text(f"Running: {definition.name}...")
    cancel_btn.set_visibility(True)
    cancel_btn.set_enabled(True)

    executor = WorkflowExecutor()

    def _run_in_thread() -> None:
        try:
            gen = executor.run(definition, dev, cancel_event)
            wf_summary = None
            try:
                while True:
                    result = next(gen)
                    result_queue.put(result)
            except StopIteration as stop:
                wf_summary = stop.value
            if wf_summary is not None:
                result_queue.put(wf_summary)
        except Exception as exc:
            fail = RecipeResult(
                recipe_name=definition.name,
                step="Workflow error",
                step_index=0,
                total_steps=1,
                status=StepStatus.FAIL,
                detail=str(exc),
            )
            result_queue.put(fail)
        finally:
            result_queue.put(None)

    threading.Thread(target=_run_in_thread, daemon=True).start()

    def _drain_queue() -> None:
        monitor_ref = builder_state["monitor"]
        q = builder_state["queue"]
        if q is None:
            return

        drained = False
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            if item is None:
                drained = True
                break
            if isinstance(item, WorkflowSummary):
                builder_state["wf_summary"] = item
                monitor_ref.finish(item)
                runner_status.set_text(f"Completed: {item.workflow_name}")
                _add_download_report_button(runner_container, builder_state)
                drained = True
                break
            monitor_ref.update(item)

        if drained:
            timer = builder_state.get("timer")
            if timer is not None:
                timer.cancel()
                builder_state["timer"] = None
            builder_state["running"] = False
            cancel_btn.set_visibility(False)

    builder_state["timer"] = ui.timer(0.2, _drain_queue)


def _add_download_report_button(container: ui.column, builder_state: dict) -> None:
    """Add a Download Report button after workflow completion."""
    from datetime import datetime, timezone

    from serialcables_switchtec.core.workflows.workflow_report import (
        WorkflowReportGenerator,
        WorkflowReportInput,
    )

    wf_summary = builder_state.get("wf_summary")
    definition = builder_state.get("definition")
    device_ctx = builder_state.get("device_context")

    if wf_summary is None or definition is None or device_ctx is None:
        return

    def _download_report() -> None:
        import re

        report_input = WorkflowReportInput(
            workflow_summary=wf_summary,
            workflow_definition=definition,
            device_context=device_ctx,
            generated_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        generator = WorkflowReportGenerator()
        html_content = generator.generate(report_input)
        slug = re.sub(r"[^a-z0-9]+", "_", wf_summary.workflow_name[:200].lower()).strip("_") or "report"
        filename = f"workflow_report_{slug}.html"
        ui.download(html_content.encode("utf-8"), filename)

    with container:
        ui.button(
            "Download Report",
            icon="download",
            on_click=_download_report,
        ).props("unelevated dense color=primary").classes("q-mt-sm")
