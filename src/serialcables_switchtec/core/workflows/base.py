"""Abstract base class for workflow recipes."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Generator

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeParameter,
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)


class Recipe(ABC):
    """Abstract base class for all workflow recipes."""

    name: str = ""
    description: str = ""
    category: RecipeCategory = RecipeCategory.LINK_HEALTH
    duration_label: str = ""

    @abstractmethod
    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        """Execute the recipe, yielding results per step.

        Args:
            dev: Active Switchtec device.
            cancel: Event that signals cancellation.
            **kwargs: Recipe-specific parameters.

        Yields:
            RecipeResult for each step.

        Returns:
            RecipeSummary when complete.
        """

    @abstractmethod
    def parameters(self) -> list[RecipeParameter]:
        """Return the list of configurable parameters for this recipe."""

    @abstractmethod
    def estimated_duration_s(self, **kwargs: object) -> float:
        """Estimate the runtime in seconds for given parameters."""

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        """Best-effort cleanup called when recipe thread encounters unhandled exception.

        Subclasses should override to disable hardware state (pattern generators,
        loopback, etc.) that may have been left active.
        """

    def _make_result(
        self,
        step: str,
        step_index: int,
        total_steps: int,
        status: StepStatus,
        detail: str = "",
        criticality: StepCriticality = StepCriticality.NON_CRITICAL,
        data: dict | None = None,
    ) -> RecipeResult:
        return RecipeResult(
            recipe_name=self.name,
            step=step,
            step_index=step_index,
            total_steps=total_steps,
            status=status,
            criticality=criticality,
            detail=detail,
            data=data,
        )

    def _make_summary(
        self,
        results: list[RecipeResult],
        elapsed_s: float,
        aborted: bool = False,
    ) -> RecipeSummary:
        return RecipeSummary(
            recipe_name=self.name,
            total_steps=len(results),
            passed=sum(1 for r in results if r.status == StepStatus.PASS),
            failed=sum(1 for r in results if r.status == StepStatus.FAIL),
            warnings=sum(1 for r in results if r.status == StepStatus.WARN),
            skipped=sum(1 for r in results if r.status == StepStatus.SKIP),
            aborted=aborted,
            elapsed_s=elapsed_s,
            results=results,
        )
