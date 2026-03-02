"""Sequential executor for multi-recipe workflows."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.workflows import RECIPE_REGISTRY
from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStepSummary,
    WorkflowSummary,
)


class WorkflowExecutor:
    """Runs a :class:`WorkflowDefinition` sequentially, yielding prefixed results."""

    def run(
        self,
        definition: WorkflowDefinition,
        dev: SwitchtecDevice,
        cancel: threading.Event,
    ) -> Generator[RecipeResult, None, WorkflowSummary]:
        """Execute each step in *definition*, yielding ``RecipeResult`` objects.

        Results are prefixed so the existing ``RecipeStepper`` can render
        which recipe each step belongs to.

        Returns a :class:`WorkflowSummary` via ``StopIteration.value``.
        """
        total = len(definition.steps)
        step_summaries: list[WorkflowStepSummary] = []
        completed = 0
        aborted = False
        start = time.monotonic()

        # Validate all recipe keys and params up front
        for idx, step in enumerate(definition.steps):
            if step.recipe_key not in RECIPE_REGISTRY:
                msg = (
                    f"Step {idx}: unknown recipe key {step.recipe_key!r}. "
                    f"Available: {', '.join(sorted(RECIPE_REGISTRY))}"
                )
                raise ValueError(msg)
            recipe_cls = RECIPE_REGISTRY[step.recipe_key]
            valid_names = {p.name for p in recipe_cls().parameters()}
            unknown = set(step.params.keys()) - valid_names
            if unknown:
                msg = (
                    f"Step {idx} ({step.recipe_key}): unknown params "
                    f"{unknown}. Valid: {sorted(valid_names)}"
                )
                raise ValueError(msg)

        for idx, step in enumerate(definition.steps):
            if cancel.is_set():
                aborted = True
                # Mark remaining steps as skipped
                for remaining_idx in range(idx, total):
                    remaining_step = definition.steps[remaining_idx]
                    recipe_cls = RECIPE_REGISTRY[remaining_step.recipe_key]
                    step_summaries.append(
                        WorkflowStepSummary(
                            step_index=remaining_idx,
                            recipe_key=remaining_step.recipe_key,
                            recipe_name=recipe_cls.name,
                            skipped=True,
                        ),
                    )
                break

            recipe_cls = RECIPE_REGISTRY[step.recipe_key]
            recipe = recipe_cls()
            prefix = f"[{idx + 1}/{total}] {recipe.name}"

            # Announce step start
            yield RecipeResult(
                recipe_name=prefix,
                step=f"Starting: {recipe.name}",
                step_index=0,
                total_steps=1,
                status=StepStatus.INFO,
                detail=step.label or recipe.description,
            )

            summary: RecipeSummary | None = None
            had_critical_fail = False

            try:
                gen = recipe.run(dev, cancel, **step.params)
                try:
                    while True:
                        result = next(gen)
                        # Prefix the result for workflow-scoped display
                        yield RecipeResult(
                            recipe_name=prefix,
                            step=f"{recipe.name} > {result.step}",
                            step_index=result.step_index,
                            total_steps=result.total_steps,
                            status=result.status,
                            criticality=result.criticality,
                            detail=result.detail,
                            data=result.data,
                        )
                        if (
                            result.status == StepStatus.FAIL
                            and result.criticality == StepCriticality.CRITICAL
                        ):
                            had_critical_fail = True
                except StopIteration as stop:
                    summary = stop.value
            except Exception as exc:
                try:
                    recipe.cleanup(dev, **step.params)
                except Exception:
                    pass

                yield RecipeResult(
                    recipe_name=prefix,
                    step=f"{recipe.name} > Unexpected error",
                    step_index=0,
                    total_steps=1,
                    status=StepStatus.FAIL,
                    criticality=StepCriticality.CRITICAL,
                    detail=str(exc),
                )
                had_critical_fail = True

            if summary is not None:
                completed += 1

            step_summaries.append(
                WorkflowStepSummary(
                    step_index=idx,
                    recipe_key=step.recipe_key,
                    recipe_name=recipe.name,
                    recipe_summary=summary,
                ),
            )

            # Abort on critical failure if configured
            if had_critical_fail and definition.abort_on_critical_fail:
                aborted = True
                for remaining_idx in range(idx + 1, total):
                    remaining_step = definition.steps[remaining_idx]
                    remaining_cls = RECIPE_REGISTRY[remaining_step.recipe_key]
                    step_summaries.append(
                        WorkflowStepSummary(
                            step_index=remaining_idx,
                            recipe_key=remaining_step.recipe_key,
                            recipe_name=remaining_cls.name,
                            skipped=True,
                        ),
                    )
                break

        elapsed = time.monotonic() - start
        return WorkflowSummary(
            workflow_name=definition.name,
            total_recipes=total,
            completed_recipes=completed,
            step_summaries=step_summaries,
            aborted=aborted,
            elapsed_s=round(elapsed, 2),
        )
