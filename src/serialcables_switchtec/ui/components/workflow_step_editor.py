"""Single workflow step editor row for the builder page."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.ui.components.param_inputs import param_input
from serialcables_switchtec.ui.theme import COLORS


def workflow_step_editor(
    index: int,
    total: int,
    recipe: Recipe,
    current_params: dict,
    current_label: str,
    on_move_up: Callable[[], None],
    on_move_down: Callable[[], None],
    on_remove: Callable[[], None],
) -> dict[str, object]:
    """Render one step row in the workflow builder.

    Returns a dict mapping ``{param_name: widget_ref, "__label__": label_widget}``
    for value extraction at save/run time.
    """
    widgets: dict[str, object] = {}
    params = recipe.parameters()

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
                    # Use saved value or default
                    if p.name in current_params:
                        # Temporarily override the param default for display
                        override = p.model_copy(update={"default": current_params[p.name]})
                        widget = param_input(override)
                    else:
                        widget = param_input(p)
                    widgets[p.name] = widget

    return widgets
