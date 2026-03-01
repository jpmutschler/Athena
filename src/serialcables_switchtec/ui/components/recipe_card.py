"""Recipe card component with auto-generated parameter inputs."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.models import RecipeParameter
from serialcables_switchtec.ui.theme import COLORS


def recipe_card(
    recipe: Recipe,
    on_run: Callable[[Recipe, dict], None],
) -> None:
    """Render a recipe card with parameter inputs and a Run button.

    Args:
        recipe: The recipe instance to render.
        on_run: Callback invoked with (recipe, params_dict) when Run is clicked.
    """
    params = recipe.parameters()
    param_widgets: dict[str, object] = {}

    with ui.card().classes("q-pa-md q-mb-md").style(
        f"min-width: 300px; max-width: 480px; flex: 1 1 300px;"
        f" border: 1px solid {COLORS.text_muted};"
    ):
        with ui.row().classes("w-full items-center justify-between q-mb-sm"):
            ui.label(recipe.name).classes("text-subtitle1 text-bold").style(
                f"color: {COLORS.text_primary};"
            )
            ui.badge(recipe.duration_label).style(
                f"background-color: {COLORS.bg_secondary};"
                f" color: {COLORS.text_secondary};"
            )

        ui.label(recipe.description).classes("text-body2 q-mb-sm").style(
            f"color: {COLORS.text_secondary};"
        )

        # Auto-generate parameter inputs
        if params:
            ui.separator().classes("q-my-xs")
            with ui.column().classes("w-full q-gutter-xs"):
                for p in params:
                    widget = _param_input(p)
                    param_widgets[p.name] = widget

        ui.separator().classes("q-my-sm")

        def _on_click() -> None:
            kwargs = {}
            for p in params:
                w = param_widgets[p.name]
                kwargs[p.name] = _extract_value(p, w)
            on_run(recipe, kwargs)

        ui.button("Run", icon="play_arrow", on_click=_on_click).props(
            "unelevated dense color=positive"
        )


def _param_input(param: RecipeParameter) -> object:
    """Create a NiceGUI input widget for a recipe parameter."""
    if param.param_type == "select" and param.choices:
        options = {c: c for c in param.choices}
        return ui.select(
            options=options,
            label=param.display_name,
            value=param.default or param.choices[0],
        ).classes("w-full")

    if param.param_type == "bool":
        return ui.switch(param.display_name, value=bool(param.default))

    if param.param_type in ("int", "float"):
        return ui.number(
            label=param.display_name,
            value=param.default if param.default is not None else 0,
            min=param.min_val,
            max=param.max_val,
        ).classes("w-full")

    # Default: text input
    return ui.input(
        label=param.display_name,
        value=str(param.default) if param.default is not None else "",
    ).classes("w-full")


def _extract_value(param: RecipeParameter, widget: object) -> object:
    """Extract the current value from a parameter widget."""
    val = getattr(widget, "value", None)
    if param.param_type == "int":
        return int(val or 0)
    if param.param_type == "float":
        return float(val or 0)
    if param.param_type == "bool":
        return bool(val)
    return val
