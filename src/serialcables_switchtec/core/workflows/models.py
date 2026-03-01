"""Pydantic models for the workflow recipe system."""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict


class RecipeCategory(StrEnum):
    LINK_HEALTH = "link_health"
    SIGNAL_INTEGRITY = "signal_integrity"
    ERROR_TESTING = "error_testing"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"
    DEBUG = "debug"


class StepStatus(IntEnum):
    RUNNING = 0
    PASS = 1
    FAIL = 2
    WARN = 3
    INFO = 4
    SKIP = 5


class StepCriticality(StrEnum):
    CRITICAL = "critical"
    NON_CRITICAL = "non_critical"


class RecipeResult(BaseModel):
    """Result of a single recipe step."""

    model_config = ConfigDict(frozen=True)

    recipe_name: str
    step: str
    step_index: int
    total_steps: int
    status: StepStatus
    criticality: StepCriticality = StepCriticality.NON_CRITICAL
    detail: str = ""
    data: dict | None = None


class RecipeSummary(BaseModel):
    """Summary of a completed recipe run."""

    model_config = ConfigDict(frozen=True)

    recipe_name: str
    total_steps: int
    passed: int
    failed: int
    warnings: int
    skipped: int
    aborted: bool = False
    elapsed_s: float
    results: list[RecipeResult]


class RecipeParameter(BaseModel):
    """Definition of a recipe input parameter."""

    model_config = ConfigDict(frozen=True)

    name: str
    display_name: str
    param_type: str  # "int", "float", "str", "bool", "select"
    required: bool = True
    default: int | float | str | bool | None = None
    choices: list[str] | None = None
    min_val: float | None = None
    max_val: float | None = None
    depends_on: str | None = None
