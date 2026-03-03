"""Mutable runtime state accumulator for the live workflow monitor.

Tracks per-step timing, results, and pass/fail counts as
``RecipeResult`` objects stream in from the ``WorkflowExecutor``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from serialcables_switchtec.core.workflows.models import RecipeResult, StepStatus

_PREFIX_RE = re.compile(r"^\[(\d+)/(\d+)\]\s*(.*)$")


def parse_prefix(recipe_name: str) -> tuple[int, str]:
    """Extract step index and clean name from ``"[1/3] Cross-Hair Margin Analysis"``.

    Returns a 0-based step index and the clean recipe name.
    If the prefix is missing, returns ``(0, recipe_name)``.
    """
    match = _PREFIX_RE.match(recipe_name)
    if match is None:
        return 0, recipe_name
    step_num = int(match.group(1))
    return step_num - 1, match.group(3).strip()


@dataclass  # Not frozen: intentional runtime accumulator, not a DTO
class MonitorStepState:
    """Mutable per-recipe-step state."""

    recipe_key: str
    recipe_name: str
    step_index: int
    started_at: float = 0.0
    finished_at: float = 0.0
    results: list[RecipeResult] = field(default_factory=list)

    @property
    def elapsed_s(self) -> float:
        if self.started_at == 0.0:
            return 0.0
        end = self.finished_at if self.finished_at > 0.0 else time.monotonic()
        return round(end - self.started_at, 2)

    @property
    def is_running(self) -> bool:
        return self.started_at > 0.0 and self.finished_at == 0.0

    @property
    def pass_fail_counts(self) -> dict[str, int]:
        counts = {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0}
        for r in self.results:
            if r.status == StepStatus.PASS:
                counts["passed"] += 1
            elif r.status == StepStatus.FAIL:
                counts["failed"] += 1
            elif r.status == StepStatus.WARN:
                counts["warnings"] += 1
            elif r.status == StepStatus.SKIP:
                counts["skipped"] += 1
        return counts

    @property
    def extracted_data(self) -> dict:
        merged: dict = {}
        for r in self.results:
            if r.data:
                merged.update(r.data)
        return merged


@dataclass  # Not frozen: intentional runtime accumulator, not a DTO
class MonitorState:
    """Mutable workflow-level state for the live monitor."""

    workflow_name: str = ""
    total_steps: int = 0
    started_at: float = 0.0
    steps: dict[int, MonitorStepState] = field(default_factory=dict)
    current_step_index: int = -1
    finished: bool = False
    _step_keys: dict[int, str] = field(default_factory=dict)

    @property
    def elapsed_s(self) -> float:
        if self.started_at == 0.0:
            return 0.0
        return round(time.monotonic() - self.started_at, 2)

    @property
    def completed_count(self) -> int:
        return sum(
            1 for s in self.steps.values() if s.finished_at > 0.0
        )

    @property
    def overall_pass_fail(self) -> dict[str, int]:
        totals = {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0}
        for step_state in self.steps.values():
            counts = step_state.pass_fail_counts
            for key in totals:
                totals[key] += counts[key]
        return totals

    def start(
        self,
        workflow_name: str,
        step_keys: list[tuple[int, str]],
    ) -> None:
        """Initialize state with recipe key mapping from workflow definition steps."""
        self.workflow_name = workflow_name
        self.total_steps = len(step_keys)
        self.started_at = time.monotonic()
        self._step_keys = {idx: key for idx, key in step_keys}
        self.current_step_index = -1
        self.finished = False

    def ingest(self, result: RecipeResult) -> int | None:
        """Process a new result and update state.

        Returns the previous step index if a step transition occurred,
        or ``None`` if no transition.
        """
        step_idx, clean_name = parse_prefix(result.recipe_name)
        previous_step = None

        if step_idx != self.current_step_index:
            # Step transition — finish previous step
            if self.current_step_index >= 0 and self.current_step_index in self.steps:
                prev = self.steps[self.current_step_index]
                if prev.finished_at == 0.0:
                    prev.finished_at = time.monotonic()
                previous_step = self.current_step_index

            self.current_step_index = step_idx

            if step_idx not in self.steps:
                recipe_key = self._step_keys.get(step_idx, "")
                self.steps[step_idx] = MonitorStepState(
                    recipe_key=recipe_key,
                    recipe_name=clean_name,
                    step_index=step_idx,
                    started_at=time.monotonic(),
                )

        step_state = self.steps.get(step_idx)
        if step_state is not None:
            step_state.results.append(result)

        return previous_step
