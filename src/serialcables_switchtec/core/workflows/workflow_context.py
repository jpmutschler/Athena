"""Mutable execution context for workflow runs.

Tracks per-step output data and failure state, enabling inter-step
data passing, conditions, and loop-until patterns.

This is internal mutable state — not a frozen Pydantic model, not persisted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from serialcables_switchtec.core.workflows.workflow_expressions import (
    evaluate_condition,
    resolve_params,
    resolve_ref,
)


@dataclass
class WorkflowExecutionContext:
    """Tracks data emitted by completed workflow steps."""

    step_data: dict[int, dict] = field(default_factory=dict)
    step_labels: dict[str, int] = field(default_factory=dict)
    step_failed: dict[int, bool] = field(default_factory=dict)
    total_steps: int = 0

    def build_label_index(self, steps: list) -> None:
        """Build the label-to-index mapping from workflow steps.

        *steps* should be a list of ``WorkflowStep`` objects with a
        ``.label`` attribute.
        """
        self.step_labels = {}
        for idx, step in enumerate(steps):
            label = getattr(step, "label", "")
            if label:
                self.step_labels[label] = idx
        self.total_steps = len(steps)

    def set_step_data(
        self,
        idx: int,
        label: str,
        results: list,
        had_critical_fail: bool,
    ) -> None:
        """Store output data from a completed step.

        Merges all ``data`` dicts from the step's results into a single
        dict keyed by step index.  Also updates the label index if the
        step has a label, and records failure state.
        """
        merged: dict[str, Any] = {}
        for result in results:
            data = getattr(result, "data", None)
            if isinstance(data, dict):
                merged.update(data)
        self.step_data[idx] = merged
        self.step_failed[idx] = had_critical_fail

        if label:
            self.step_labels[label] = idx

    def resolve(self, ref_str: str) -> Any:
        """Resolve a reference string to a value from context."""
        return resolve_ref(
            ref_str,
            self.step_data,
            self.step_failed,
            self.total_steps,
            self.step_labels,
        )

    def eval_condition(self, ref: str, op: str, value: Any) -> bool:
        """Evaluate a condition against context data."""
        return evaluate_condition(
            ref, op, value,
            self.step_data,
            self.step_failed,
            self.total_steps,
            self.step_labels,
        )

    def resolve_step_params(
        self,
        static_params: dict[str, Any],
        param_bindings: dict[str, str],
    ) -> dict[str, Any]:
        """Resolve parameter bindings from context, falling back to static."""
        return resolve_params(
            static_params,
            param_bindings,
            self.step_data,
            self.step_failed,
            self.total_steps,
            self.step_labels,
        )
