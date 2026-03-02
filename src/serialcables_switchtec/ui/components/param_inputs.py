"""Shared parameter input widgets for recipe parameters."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.core.workflows.models import RecipeParameter


def param_input(param: RecipeParameter) -> object:
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


def extract_value(param: RecipeParameter, widget: object) -> object:
    """Extract the current value from a parameter widget."""
    val = getattr(widget, "value", None)
    if param.param_type == "int":
        return int(val or 0)
    if param.param_type == "float":
        return float(val or 0)
    if param.param_type == "bool":
        return bool(val)
    return val
