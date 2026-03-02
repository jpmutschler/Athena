"""Pydantic models for multi-recipe workflow definitions and summaries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from serialcables_switchtec.core.workflows.models import RecipeSummary


class WorkflowStep(BaseModel):
    """A single step in a workflow definition."""

    model_config = ConfigDict(frozen=True)

    recipe_key: str
    label: str = ""
    params: dict[str, int | float | str | bool] = {}


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


class WorkflowSummary(BaseModel):
    """Aggregate summary of a completed workflow run."""

    model_config = ConfigDict(frozen=True)

    workflow_name: str
    total_recipes: int
    completed_recipes: int
    step_summaries: list[WorkflowStepSummary]
    aborted: bool = False
    elapsed_s: float
