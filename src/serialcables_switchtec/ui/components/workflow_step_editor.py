"""Single workflow step editor row for the builder page."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.workflow_models import OnFailAction
from serialcables_switchtec.ui.components.param_inputs import binding_input, param_input
from serialcables_switchtec.ui.theme import COLORS

_ON_FAIL_OPTIONS = {
    OnFailAction.ABORT: "Abort workflow",
    OnFailAction.CONTINUE: "Continue to next step",
    OnFailAction.SKIP_NEXT: "Skip next step",
    OnFailAction.GOTO: "Jump to label",
}

_LOOP_MODE_OPTIONS = {
    "none": "Run once",
    "count": "Repeat N times",
    "over_values": "Iterate over values",
    "until": "Repeat until condition",
}

_OPERATOR_OPTIONS = {
    "eq": "equals",
    "ne": "not equals",
    "gt": "greater than",
    "lt": "less than",
    "gte": "greater or equal",
    "lte": "less or equal",
    "is_true": "is true",
    "is_false": "is false",
}


def workflow_step_editor(
    index: int,
    total: int,
    recipe: Recipe,
    current_params: dict,
    current_label: str,
    on_move_up: Callable[[], None],
    on_move_down: Callable[[], None],
    on_remove: Callable[[], None],
    current_advanced: dict | None = None,
) -> dict[str, object]:
    """Render one step row in the workflow builder.

    Returns a dict mapping ``{param_name: widget_ref, "__label__": label_widget,
    "__advanced__": {on_fail, on_fail_goto, bindings, loop_mode, ...}}``
    for value extraction at save/run time.
    """
    widgets: dict[str, object] = {}
    params = recipe.parameters()
    adv = current_advanced or {}

    with ui.card().classes("w-full q-pa-sm q-mb-sm").style(
        f"border: 1px solid {COLORS.text_muted};"
    ):
        # Header row: step number, recipe name, move/delete buttons
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"Step {index + 1}: {recipe.name}").classes(
                "text-subtitle2 text-bold"
            ).style(f"color: {COLORS.text_primary};")

            with ui.row().classes("q-gutter-xs"):
                ui.button(
                    icon="arrow_upward",
                    on_click=lambda: on_move_up(),
                ).props("flat dense round size=sm").set_enabled(index > 0)

                ui.button(
                    icon="arrow_downward",
                    on_click=lambda: on_move_down(),
                ).props("flat dense round size=sm").set_enabled(index < total - 1)

                ui.button(
                    icon="delete",
                    on_click=lambda: on_remove(),
                ).props("flat dense round size=sm color=negative")

        # Label input
        label_widget = ui.input(
            label="Step label (optional)",
            value=current_label,
        ).classes("w-full").props("dense")
        widgets["__label__"] = label_widget

        # Parameter inputs
        if params:
            ui.separator().classes("q-my-xs")
            with ui.column().classes("w-full q-gutter-xs"):
                for p in params:
                    if p.name in current_params:
                        override = p.model_copy(update={"default": current_params[p.name]})
                        widget = param_input(override)
                    else:
                        widget = param_input(p)
                    widgets[p.name] = widget

        # --- Advanced section (collapsed by default) ---
        advanced_widgets: dict[str, object] = {}

        with ui.expansion("Advanced", icon="tune").classes("w-full").props("dense"):
            # On-fail handling
            ui.label("On Failure").classes("text-caption text-bold").style(
                f"color: {COLORS.text_secondary};"
            )
            with ui.row().classes("w-full items-end q-gutter-sm"):
                on_fail_select = ui.select(
                    options=_ON_FAIL_OPTIONS,
                    label="Action",
                    value=adv.get("on_fail", OnFailAction.ABORT),
                ).classes("flex-grow").props("dense")
                advanced_widgets["on_fail"] = on_fail_select

                goto_input = ui.input(
                    label="Goto label",
                    value=adv.get("on_fail_goto", ""),
                ).classes("w-40").props("dense")
                advanced_widgets["on_fail_goto"] = goto_input

            ui.separator().classes("q-my-xs")

            # Parameter bindings
            if params:
                ui.label("Parameter Bindings").classes("text-caption text-bold").style(
                    f"color: {COLORS.text_secondary};"
                )
                current_bindings = adv.get("param_bindings", {})
                with ui.column().classes("w-full q-gutter-xs"):
                    for p in params:
                        bw = binding_input(p.name, current_bindings.get(p.name, ""))
                        advanced_widgets[f"bind_{p.name}"] = bw

                ui.separator().classes("q-my-xs")

            # Loop configuration
            ui.label("Loop").classes("text-caption text-bold").style(
                f"color: {COLORS.text_secondary};"
            )
            loop_mode = ui.select(
                options=_LOOP_MODE_OPTIONS,
                label="Loop mode",
                value=adv.get("loop_mode", "none"),
            ).classes("w-full").props("dense")
            advanced_widgets["loop_mode"] = loop_mode

            with ui.row().classes("w-full q-gutter-sm"):
                loop_count = ui.number(
                    label="Count",
                    value=adv.get("loop_count", 3),
                    min=1,
                    max=1000,
                ).classes("w-24").props("dense")
                advanced_widgets["loop_count"] = loop_count

                loop_values = ui.input(
                    label="Values (comma-separated)",
                    value=adv.get("loop_values", ""),
                    placeholder="0,1,2,3",
                ).classes("flex-grow").props("dense")
                advanced_widgets["loop_values"] = loop_values

                loop_param = ui.select(
                    options={p.name: p.display_name for p in params} if params else {},
                    label="Bind to param",
                    value=adv.get("loop_param", None),
                ).classes("w-40").props("dense")
                advanced_widgets["loop_param"] = loop_param

            with ui.row().classes("w-full q-gutter-sm"):
                loop_until_ref = ui.input(
                    label="Until ref",
                    value=adv.get("loop_until_ref", ""),
                    placeholder="steps[0].data.link_up",
                ).classes("flex-grow").props("dense")
                advanced_widgets["loop_until_ref"] = loop_until_ref

                loop_until_value = ui.input(
                    label="Until value",
                    value=adv.get("loop_until_value", ""),
                ).classes("w-32").props("dense")
                advanced_widgets["loop_until_value"] = loop_until_value

                loop_max = ui.number(
                    label="Max iterations",
                    value=adv.get("loop_max", 100),
                    min=1,
                    max=10000,
                ).classes("w-32").props("dense")
                advanced_widgets["loop_max"] = loop_max

            ui.separator().classes("q-my-xs")

            # Condition
            ui.label("Condition").classes("text-caption text-bold").style(
                f"color: {COLORS.text_secondary};"
            )
            cond_enabled = ui.switch(
                "Only run if condition met",
                value=adv.get("cond_enabled", False),
            )
            advanced_widgets["cond_enabled"] = cond_enabled

            with ui.row().classes("w-full q-gutter-sm"):
                cond_ref = ui.input(
                    label="Reference",
                    value=adv.get("cond_ref", ""),
                    placeholder="steps[0].data.link_up",
                ).classes("flex-grow").props("dense")
                advanced_widgets["cond_ref"] = cond_ref

                cond_op = ui.select(
                    options=_OPERATOR_OPTIONS,
                    label="Operator",
                    value=adv.get("cond_op", "eq"),
                ).classes("w-40").props("dense")
                advanced_widgets["cond_op"] = cond_op

                cond_value = ui.input(
                    label="Value",
                    value=adv.get("cond_value", ""),
                ).classes("w-32").props("dense")
                advanced_widgets["cond_value"] = cond_value

        widgets["__advanced__"] = advanced_widgets

    return widgets
