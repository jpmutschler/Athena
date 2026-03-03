"""Tests for the live workflow monitor state accumulator."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.monitor_state import (
    MonitorState,
    MonitorStepState,
    parse_prefix,
)


# ---------------------------------------------------------------------------
# parse_prefix
# ---------------------------------------------------------------------------


class TestParsePrefix:
    def test_standard_prefix(self) -> None:
        idx, name = parse_prefix("[1/3] Cross-Hair Margin Analysis")
        assert idx == 0
        assert name == "Cross-Hair Margin Analysis"

    def test_middle_step(self) -> None:
        idx, name = parse_prefix("[2/5] BER Soak")
        assert idx == 1
        assert name == "BER Soak"

    def test_last_step(self) -> None:
        idx, name = parse_prefix("[3/3] Link Health Check")
        assert idx == 2
        assert name == "Link Health Check"

    def test_no_prefix(self) -> None:
        idx, name = parse_prefix("Some Recipe Name")
        assert idx == 0
        assert name == "Some Recipe Name"

    def test_single_step(self) -> None:
        idx, name = parse_prefix("[1/1] Only Step")
        assert idx == 0
        assert name == "Only Step"

    def test_double_digit_steps(self) -> None:
        idx, name = parse_prefix("[10/15] Recipe Ten")
        assert idx == 9
        assert name == "Recipe Ten"

    def test_extra_whitespace(self) -> None:
        idx, name = parse_prefix("[1/3]   Spaced Name  ")
        assert idx == 0
        assert name == "Spaced Name"

    def test_empty_string(self) -> None:
        idx, name = parse_prefix("")
        assert idx == 0
        assert name == ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    recipe_name: str = "[1/3] Test Recipe",
    step: str = "Check",
    step_index: int = 0,
    total_steps: int = 2,
    status: StepStatus = StepStatus.PASS,
    detail: str = "ok",
    data: dict | None = None,
) -> RecipeResult:
    return RecipeResult(
        recipe_name=recipe_name,
        step=step,
        step_index=step_index,
        total_steps=total_steps,
        status=status,
        detail=detail,
        data=data,
    )


def _make_state_with_keys(keys: list[tuple[int, str]]) -> MonitorState:
    state = MonitorState()
    state.start("Test Workflow", keys)
    return state


# ---------------------------------------------------------------------------
# MonitorStepState
# ---------------------------------------------------------------------------


class TestMonitorStepState:
    def test_empty_state_defaults(self) -> None:
        step = MonitorStepState(recipe_key="test", recipe_name="Test", step_index=0)
        assert step.elapsed_s == 0.0
        assert not step.is_running
        assert step.pass_fail_counts == {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0}
        assert step.extracted_data == {}

    def test_is_running_when_started(self) -> None:
        step = MonitorStepState(
            recipe_key="test",
            recipe_name="Test",
            step_index=0,
            started_at=time.monotonic(),
        )
        assert step.is_running

    def test_not_running_when_finished(self) -> None:
        now = time.monotonic()
        step = MonitorStepState(
            recipe_key="test",
            recipe_name="Test",
            step_index=0,
            started_at=now,
            finished_at=now + 1.0,
        )
        assert not step.is_running

    def test_elapsed_when_finished(self) -> None:
        now = time.monotonic()
        step = MonitorStepState(
            recipe_key="test",
            recipe_name="Test",
            step_index=0,
            started_at=now,
            finished_at=now + 2.5,
        )
        assert step.elapsed_s == 2.5

    def test_pass_fail_counts(self) -> None:
        step = MonitorStepState(recipe_key="test", recipe_name="Test", step_index=0)
        step.results = [
            _make_result(status=StepStatus.PASS),
            _make_result(status=StepStatus.PASS),
            _make_result(status=StepStatus.FAIL),
            _make_result(status=StepStatus.WARN),
            _make_result(status=StepStatus.SKIP),
            _make_result(status=StepStatus.INFO),
        ]
        counts = step.pass_fail_counts
        assert counts == {"passed": 2, "failed": 1, "warnings": 1, "skipped": 1}

    def test_extracted_data_merges_dicts(self) -> None:
        step = MonitorStepState(recipe_key="test", recipe_name="Test", step_index=0)
        step.results = [
            _make_result(data={"a": 1, "b": 2}),
            _make_result(data={"b": 3, "c": 4}),
            _make_result(data=None),
        ]
        data = step.extracted_data
        assert data == {"a": 1, "b": 3, "c": 4}

    def test_extracted_data_empty_when_no_data(self) -> None:
        step = MonitorStepState(recipe_key="test", recipe_name="Test", step_index=0)
        step.results = [
            _make_result(data=None),
            _make_result(data=None),
        ]
        assert step.extracted_data == {}


# ---------------------------------------------------------------------------
# MonitorState
# ---------------------------------------------------------------------------


class TestMonitorState:
    def test_start_initializes(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a"), (1, "recipe_b")])
        assert state.workflow_name == "Test Workflow"
        assert state.total_steps == 2
        assert state.started_at > 0
        assert state.current_step_index == -1
        assert not state.finished

    def test_elapsed_s_when_not_started(self) -> None:
        state = MonitorState()
        assert state.elapsed_s == 0.0

    def test_elapsed_s_while_running(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a")])
        assert state.elapsed_s >= 0.0

    def test_completed_count_empty(self) -> None:
        state = _make_state_with_keys([(0, "a"), (1, "b")])
        assert state.completed_count == 0

    def test_ingest_creates_step_on_first_result(self) -> None:
        state = _make_state_with_keys([(0, "cross_hair_margin")])
        result = _make_result(recipe_name="[1/1] Cross-Hair Margin")
        state.ingest(result)

        assert 0 in state.steps
        assert state.steps[0].recipe_key == "cross_hair_margin"
        assert state.steps[0].recipe_name == "Cross-Hair Margin"
        assert state.current_step_index == 0

    def test_ingest_appends_results(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a")])
        state.ingest(_make_result(recipe_name="[1/1] Recipe A", step="Step 1"))
        state.ingest(_make_result(recipe_name="[1/1] Recipe A", step="Step 2"))

        assert len(state.steps[0].results) == 2

    def test_ingest_detects_step_transition(self) -> None:
        state = _make_state_with_keys([
            (0, "recipe_a"),
            (1, "recipe_b"),
        ])

        # First step
        prev = state.ingest(_make_result(recipe_name="[1/2] Recipe A"))
        assert prev is None  # first step, no previous

        # Second step
        prev = state.ingest(_make_result(recipe_name="[2/2] Recipe B"))
        assert prev == 0  # transitioned from step 0
        assert state.current_step_index == 1
        assert state.steps[0].finished_at > 0.0

    def test_ingest_no_transition_same_step(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a")])
        state.ingest(_make_result(recipe_name="[1/1] Recipe A", step="Step 1"))
        prev = state.ingest(_make_result(recipe_name="[1/1] Recipe A", step="Step 2"))
        assert prev is None

    def test_overall_pass_fail_aggregates(self) -> None:
        state = _make_state_with_keys([
            (0, "recipe_a"),
            (1, "recipe_b"),
        ])
        state.ingest(_make_result(recipe_name="[1/2] A", status=StepStatus.PASS))
        state.ingest(_make_result(recipe_name="[1/2] A", status=StepStatus.FAIL))
        state.ingest(_make_result(recipe_name="[2/2] B", status=StepStatus.PASS))
        state.ingest(_make_result(recipe_name="[2/2] B", status=StepStatus.WARN))

        totals = state.overall_pass_fail
        assert totals == {"passed": 2, "failed": 1, "warnings": 1, "skipped": 0}

    def test_completed_count_after_transitions(self) -> None:
        state = _make_state_with_keys([
            (0, "recipe_a"),
            (1, "recipe_b"),
            (2, "recipe_c"),
        ])

        state.ingest(_make_result(recipe_name="[1/3] A"))
        state.ingest(_make_result(recipe_name="[2/3] B"))
        # Step 0 should now be finished
        assert state.completed_count == 1

        state.ingest(_make_result(recipe_name="[3/3] C"))
        # Steps 0 and 1 finished
        assert state.completed_count == 2

    def test_ingest_without_prefix_uses_index_zero(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a")])
        state.ingest(_make_result(recipe_name="Plain Name"))
        assert 0 in state.steps
        assert state.steps[0].recipe_name == "Plain Name"

    def test_multiple_results_with_data_merge(self) -> None:
        state = _make_state_with_keys([(0, "recipe_a")])
        state.ingest(_make_result(recipe_name="[1/1] A", data={"temp": 42.1}))
        state.ingest(_make_result(recipe_name="[1/1] A", data={"errors": 0}))

        data = state.steps[0].extracted_data
        assert data == {"temp": 42.1, "errors": 0}

    def test_step_key_mapping(self) -> None:
        state = _make_state_with_keys([
            (0, "cross_hair_margin"),
            (1, "ber_soak"),
            (2, "link_health_check"),
        ])

        state.ingest(_make_result(recipe_name="[2/3] BER Soak"))
        assert state.steps[1].recipe_key == "ber_soak"

        state.ingest(_make_result(recipe_name="[3/3] Link Health"))
        assert state.steps[2].recipe_key == "link_health_check"
