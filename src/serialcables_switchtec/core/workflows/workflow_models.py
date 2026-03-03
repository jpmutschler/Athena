"""Pydantic models for multi-recipe workflow definitions and summaries."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from serialcables_switchtec.core.workflows.models import RecipeSummary


# ---------------------------------------------------------------------------
# New enums for control flow
# ---------------------------------------------------------------------------


class OnFailAction(StrEnum):
    """Action to take when a step encounters a critical failure."""

    ABORT = "abort"
    CONTINUE = "continue"
    SKIP_NEXT = "skip_next"
    GOTO = "goto"


# ---------------------------------------------------------------------------
# New models for loops and conditions
# ---------------------------------------------------------------------------


class LoopConfig(BaseModel):
    """Configuration for repeating a workflow step."""

    model_config = ConfigDict(frozen=True)

    count: int | None = None
    over_values: list[int | float | str] | None = None
    over_param: str | None = None
    until_ref: str | None = None
    until_value: int | float | str | bool | None = None
    max_iterations: int = 100


ConditionOperator = Literal[
    "eq", "ne", "gt", "lt", "gte", "lte", "is_true", "is_false",
]


class StepCondition(BaseModel):
    """Condition that must be met for a step to execute."""

    model_config = ConfigDict(frozen=True)

    ref: str
    operator: ConditionOperator = "eq"
    value: int | float | str | bool | None = None


# ---------------------------------------------------------------------------
# Workflow step and definition models (extended with new optional fields)
# ---------------------------------------------------------------------------


class WorkflowStep(BaseModel):
    """A single step in a workflow definition."""

    model_config = ConfigDict(frozen=True)

    recipe_key: str
    label: str = ""
    params: dict[str, int | float | str | bool] = {}
    on_fail: OnFailAction = OnFailAction.ABORT
    on_fail_goto: str = ""
    param_bindings: dict[str, str] = {}
    loop: LoopConfig | None = None
    condition: StepCondition | None = None


class WorkflowDefinition(BaseModel):
    """A saved multi-recipe workflow."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    steps: list[WorkflowStep]
    abort_on_critical_fail: bool = True
    created_at: str = ""
    updated_at: str = ""


class WorkflowStepSummary(BaseModel):
    """Summary of a single workflow step execution."""

    model_config = ConfigDict(frozen=True)

    step_index: int
    recipe_key: str
    recipe_name: str
    recipe_summary: RecipeSummary | None = None
    skipped: bool = False
    skip_reason: str = ""
    loop_iteration: int | None = None
    loop_total: int | None = None
    iteration_summaries: list[RecipeSummary] | None = None


class WorkflowSummary(BaseModel):
    """Aggregate summary of a completed workflow run."""

    model_config = ConfigDict(frozen=True)

    workflow_name: str
    total_recipes: int
    completed_recipes: int
    step_summaries: list[WorkflowStepSummary]
    aborted: bool = False
    elapsed_s: float
