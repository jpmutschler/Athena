"""Workflow recipe registry."""

from __future__ import annotations

from serialcables_switchtec.core.workflows.all_port_sweep import AllPortSweep
from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.ber_soak import BerSoak
from serialcables_switchtec.core.workflows.loopback_sweep import LoopbackSweep
from serialcables_switchtec.core.workflows.models import RecipeCategory

RECIPE_REGISTRY: dict[str, type[Recipe]] = {
    "all_port_sweep": AllPortSweep,
    "ber_soak": BerSoak,
    "loopback_sweep": LoopbackSweep,
}


def get_recipe(name: str) -> Recipe:
    """Instantiate a recipe by registry name."""
    cls = RECIPE_REGISTRY[name]
    return cls()


def get_recipes_by_category(category: RecipeCategory) -> list[Recipe]:
    """Return all recipe instances for a given category."""
    return [
        cls()
        for cls in RECIPE_REGISTRY.values()
        if cls.category == category
    ]
