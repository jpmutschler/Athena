"""Sequential executor for multi-recipe workflows.

Supports inter-step data passing, per-step on-fail handling,
loop constructs, and conditional branching.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator
from typing import Any

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.workflows import RECIPE_REGISTRY
from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_context import (
    WorkflowExecutionContext,
)
from serialcables_switchtec.core.workflows.workflow_models import (
    OnFailAction,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepSummary,
    WorkflowSummary,
)

_MAX_GOTO_VISITS = 3


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

        # Validate all recipe keys, params, labels, and GOTO targets up front
        self._validate_definition(definition)

        # Build execution context
        context = WorkflowExecutionContext()
        context.build_label_index(definition.steps)

        # Track visit counts for GOTO cycle detection
        visit_counts: dict[int, int] = {}

        idx = 0
        while idx < total:
            step = definition.steps[idx]

            # Cancel check
            if cancel.is_set():
                aborted = True
                self._skip_remaining(definition, idx, total, step_summaries, "Cancelled")
                break

            # GOTO cycle detection
            visit_counts[idx] = visit_counts.get(idx, 0) + 1
            if visit_counts[idx] > _MAX_GOTO_VISITS:
                aborted = True
                yield RecipeResult(
                    recipe_name=f"[{idx + 1}/{total}] Workflow",
                    step="Cycle detected",
                    step_index=0,
                    total_steps=1,
                    status=StepStatus.FAIL,
                    criticality=StepCriticality.CRITICAL,
                    detail=f"Step {idx} visited {visit_counts[idx]} times — aborting to prevent infinite loop",
                )
                self._skip_remaining(definition, idx, total, step_summaries, "Cycle detected")
                break

            # Condition check
            if step.condition is not None:
                condition_met = context.eval_condition(
                    step.condition.ref,
                    step.condition.operator,
                    step.condition.value,
                )
                if not condition_met:
                    recipe_cls = RECIPE_REGISTRY[step.recipe_key]
                    step_summaries.append(
                        WorkflowStepSummary(
                            step_index=idx,
                            recipe_key=step.recipe_key,
                            recipe_name=recipe_cls.name,
                            skipped=True,
                            skip_reason="Condition not met",
                        ),
                    )
                    yield RecipeResult(
                        recipe_name=f"[{idx + 1}/{total}] {recipe_cls.name}",
                        step=f"Skipped: {recipe_cls.name}",
                        step_index=0,
                        total_steps=1,
                        status=StepStatus.SKIP,
                        detail="Condition not met",
                    )
                    # Store empty data so subsequent refs to this step see it
                    context.set_step_data(idx, step.label, [], had_critical_fail=False)
                    idx += 1
                    continue

            # Resolve param bindings
            resolved_params = context.resolve_step_params(
                dict(step.params), dict(step.param_bindings),
            )

            # Loop handling
            if step.loop is not None:
                loop_summaries, loop_completed, loop_aborted = yield from self._execute_loop(
                    step, idx, total, resolved_params, dev, cancel, context,
                )
                step_summaries.extend(loop_summaries)
                completed += loop_completed
                if loop_aborted:
                    aborted = True
                    self._skip_remaining(definition, idx + 1, total, step_summaries, "Aborted")
                    break
                idx += 1
                continue

            # Execute single recipe step
            step_results, summary, had_critical_fail = yield from self._execute_single_step(
                step, idx, total, resolved_params, dev, cancel,
            )

            # Store output data in context
            context.set_step_data(idx, step.label, step_results, had_critical_fail)

            if summary is not None:
                completed += 1

            step_summaries.append(
                WorkflowStepSummary(
                    step_index=idx,
                    recipe_key=step.recipe_key,
                    recipe_name=RECIPE_REGISTRY[step.recipe_key].name,
                    recipe_summary=summary,
                ),
            )

            # On-fail handling
            if had_critical_fail:
                next_idx = self._handle_on_fail(
                    step, idx, total, context, definition, step_summaries,
                )
                if next_idx is None:
                    aborted = True
                    self._skip_remaining(definition, idx + 1, total, step_summaries)
                    break
                idx = next_idx
            else:
                idx += 1

        elapsed = time.monotonic() - start
        return WorkflowSummary(
            workflow_name=definition.name,
            total_recipes=total,
            completed_recipes=completed,
            step_summaries=step_summaries,
            aborted=aborted,
            elapsed_s=round(elapsed, 2),
        )

    @staticmethod
    def _validate_definition(definition: WorkflowDefinition) -> None:
        """Validate recipe keys, params, labels, and GOTO targets up front."""
        seen_labels: dict[str, int] = {}
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
            # Check for duplicate labels
            if step.label:
                if step.label in seen_labels:
                    msg = (
                        f"Step {idx}: duplicate label {step.label!r} "
                        f"(also used by step {seen_labels[step.label]})"
                    )
                    raise ValueError(msg)
                seen_labels[step.label] = idx

        # Validate GOTO targets reference existing labels
        for idx, step in enumerate(definition.steps):
            if step.on_fail == OnFailAction.GOTO and step.on_fail_goto:
                if step.on_fail_goto not in seen_labels:
                    msg = (
                        f"Step {idx}: on_fail_goto references unknown label "
                        f"{step.on_fail_goto!r}. Available: {sorted(seen_labels)}"
                    )
                    raise ValueError(msg)

    @staticmethod
    def _skip_remaining(
        definition: WorkflowDefinition,
        start_idx: int,
        total: int,
        step_summaries: list[WorkflowStepSummary],
        reason: str = "",
    ) -> None:
        """Append skipped summaries for all steps from *start_idx* onward."""
        for remaining_idx in range(start_idx, total):
            remaining_step = definition.steps[remaining_idx]
            recipe_cls = RECIPE_REGISTRY[remaining_step.recipe_key]
            step_summaries.append(
                WorkflowStepSummary(
                    step_index=remaining_idx,
                    recipe_key=remaining_step.recipe_key,
                    recipe_name=recipe_cls.name,
                    skipped=True,
                    skip_reason=reason,
                ),
            )

    def _execute_single_step(
        self,
        step: WorkflowStep,
        idx: int,
        total: int,
        resolved_params: dict[str, Any],
        dev: SwitchtecDevice,
        cancel: threading.Event,
    ) -> Generator[RecipeResult, None, tuple[list[RecipeResult], RecipeSummary | None, bool]]:
        """Execute a single recipe and yield prefixed results.

        Returns ``(step_results, summary, had_critical_fail)``.
        """
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
        step_results: list[RecipeResult] = []

        try:
            gen = recipe.run(dev, cancel, **resolved_params)
            try:
                while True:
                    result = next(gen)
                    prefixed = RecipeResult(
                        recipe_name=prefix,
                        step=f"{recipe.name} > {result.step}",
                        step_index=result.step_index,
                        total_steps=result.total_steps,
                        status=result.status,
                        criticality=result.criticality,
                        detail=result.detail,
                        data=result.data,
                    )
                    yield prefixed
                    step_results.append(result)
                    if (
                        result.status == StepStatus.FAIL
                        and result.criticality == StepCriticality.CRITICAL
                    ):
                        had_critical_fail = True
            except StopIteration as stop:
                summary = stop.value
        except Exception as exc:
            try:
                recipe.cleanup(dev, **resolved_params)
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

        return step_results, summary, had_critical_fail

    def _handle_on_fail(
        self,
        step: WorkflowStep,
        idx: int,
        total: int,
        context: WorkflowExecutionContext,
        definition: WorkflowDefinition,
        step_summaries: list[WorkflowStepSummary],
    ) -> int | None:
        """Determine the next step index after a critical failure.

        Returns the next index, or ``None`` to abort.
        """
        # Legacy behavior: if the definition uses abort_on_critical_fail and
        # step uses default ABORT, respect definition flag
        if step.on_fail == OnFailAction.ABORT:
            if definition.abort_on_critical_fail:
                return None
            return idx + 1

        if step.on_fail == OnFailAction.CONTINUE:
            return idx + 1

        if step.on_fail == OnFailAction.SKIP_NEXT:
            skip_idx = idx + 1
            if skip_idx < total:
                skipped_step = definition.steps[skip_idx]
                recipe_cls = RECIPE_REGISTRY[skipped_step.recipe_key]
                step_summaries.append(
                    WorkflowStepSummary(
                        step_index=skip_idx,
                        recipe_key=skipped_step.recipe_key,
                        recipe_name=recipe_cls.name,
                        skipped=True,
                        skip_reason="Previous step failed (skip_next)",
                    ),
                )
                # Store empty data for skipped step
                context.set_step_data(skip_idx, skipped_step.label, [], had_critical_fail=False)
            return idx + 2

        if step.on_fail == OnFailAction.GOTO:
            target_label = step.on_fail_goto
            target_idx = context.step_labels.get(target_label)
            if target_idx is None:
                # Invalid goto target — abort
                return None
            return target_idx

        return None

    def _execute_loop(
        self,
        step: WorkflowStep,
        idx: int,
        total: int,
        base_params: dict[str, Any],
        dev: SwitchtecDevice,
        cancel: threading.Event,
        context: WorkflowExecutionContext,
    ) -> Generator[
        RecipeResult,
        None,
        tuple[list[WorkflowStepSummary], int, bool],
    ]:
        """Execute a looping step.

        Returns ``(step_summaries, completed_count, aborted)``.
        """
        loop = step.loop
        loop_summaries: list[WorkflowStepSummary] = []
        iteration_recipe_summaries: list[RecipeSummary] = []
        loop_completed = 0
        loop_aborted = False

        iterations = self._resolve_loop_iterations(loop)
        recipe_cls = RECIPE_REGISTRY[step.recipe_key]
        until_satisfied = False

        for iteration_idx, loop_value in enumerate(iterations):
            if cancel.is_set():
                loop_aborted = True
                break

            # Build iteration params
            iter_params = dict(base_params)
            if loop.over_param and loop_value is not _SENTINEL:
                iter_params[loop.over_param] = loop_value

            # Execute
            iter_step = step.model_copy(update={"loop": None})
            step_results, summary, had_critical_fail = yield from self._execute_single_step(
                iter_step, idx, total, iter_params, dev, cancel,
            )

            # Store iteration data in context (each iteration overwrites)
            context.set_step_data(idx, step.label, step_results, had_critical_fail)

            if summary is not None:
                iteration_recipe_summaries.append(summary)
                loop_completed += 1

            # Check until condition
            if loop.until_ref is not None:
                current = context.resolve(loop.until_ref)
                if current == loop.until_value:
                    until_satisfied = True
                    break

            if had_critical_fail and step.on_fail == OnFailAction.ABORT:
                loop_aborted = True
                break

        # Warn if until loop hit max_iterations without condition being met
        if loop.until_ref is not None and not until_satisfied and not loop_aborted and not cancel.is_set():
            yield RecipeResult(
                recipe_name=f"[{idx + 1}/{total}] {recipe_cls.name}",
                step="Max iterations reached",
                step_index=0,
                total_steps=1,
                status=StepStatus.WARN,
                detail=f"Safety cap of {loop.max_iterations} iterations reached",
            )

        # Create single step summary for the loop
        loop_summaries.append(
            WorkflowStepSummary(
                step_index=idx,
                recipe_key=step.recipe_key,
                recipe_name=recipe_cls.name,
                recipe_summary=iteration_recipe_summaries[-1] if iteration_recipe_summaries else None,
                loop_total=len(iteration_recipe_summaries),
                iteration_summaries=iteration_recipe_summaries if iteration_recipe_summaries else None,
            ),
        )

        return loop_summaries, loop_completed, loop_aborted

    @staticmethod
    def _resolve_loop_iterations(loop) -> list:
        """Determine the iteration values for a loop config."""
        if loop.over_values is not None:
            return loop.over_values

        if loop.count is not None:
            return [_SENTINEL] * loop.count

        if loop.until_ref is not None:
            # until loops run up to max_iterations
            return [_SENTINEL] * loop.max_iterations

        return [_SENTINEL]


class _SentinelType:
    """Sentinel value for loops that don't bind a value."""

    def __repr__(self) -> str:
        return "<NO_VALUE>"


_SENTINEL = _SentinelType()
