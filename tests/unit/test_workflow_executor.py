"""Tests for the sequential workflow executor."""

from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeParameter,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_executor import WorkflowExecutor
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
)
from tests.unit.test_workflows_helpers import make_mock_device


# ---------------------------------------------------------------------------
# Test recipe stubs
# ---------------------------------------------------------------------------


class _PassingRecipe(Recipe):
    name = "Passing Recipe"
    description = "Always passes"
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~1s"

    def run(self, dev, cancel, **kwargs):
        r1 = self._make_result("Step A", 0, 2, StepStatus.PASS, detail="ok")
        yield r1
        r2 = self._make_result("Step B", 1, 2, StepStatus.PASS, detail="done")
        yield r2
        return self._make_summary([r1, r2], 1.0)

    def parameters(self):
        return [
            RecipeParameter(name="port_id", display_name="Port", param_type="int", default=0),
        ]

    def estimated_duration_s(self, **kwargs):
        return 1.0


class _FailingRecipe(Recipe):
    name = "Failing Recipe"
    description = "Always fails critically"
    category = RecipeCategory.ERROR_TESTING
    duration_label = "~1s"

    def run(self, dev, cancel, **kwargs):
        r1 = self._make_result(
            "Fail Step", 0, 1, StepStatus.FAIL,
            detail="critical failure",
            criticality=StepCriticality.CRITICAL,
        )
        yield r1
        return self._make_summary([r1], 0.5)

    def parameters(self):
        return []

    def estimated_duration_s(self, **kwargs):
        return 1.0


class _NonCriticalFailRecipe(Recipe):
    """Fails with NON_CRITICAL criticality — should NOT trigger abort."""

    name = "Non-Critical Fail Recipe"
    description = "Fails non-critically"
    category = RecipeCategory.ERROR_TESTING
    duration_label = "~1s"

    def run(self, dev, cancel, **kwargs):
        r1 = self._make_result(
            "Soft Fail", 0, 1, StepStatus.FAIL,
            detail="non-critical failure",
            criticality=StepCriticality.NON_CRITICAL,
        )
        yield r1
        return self._make_summary([r1], 0.5)

    def parameters(self):
        return []

    def estimated_duration_s(self, **kwargs):
        return 1.0


class _ExplodingRecipe(Recipe):
    name = "Exploding Recipe"
    description = "Raises an exception"
    category = RecipeCategory.DEBUG
    duration_label = "~1s"
    cleanup_called = False

    def run(self, dev, cancel, **kwargs):
        msg = "boom"
        raise RuntimeError(msg)
        yield  # noqa: F841 — unreachable; makes this a generator

    def parameters(self):
        return []

    def estimated_duration_s(self, **kwargs):
        return 1.0

    def cleanup(self, dev, **kwargs):
        _ExplodingRecipe.cleanup_called = True


_TEST_REGISTRY = {
    "passing_recipe": _PassingRecipe,
    "failing_recipe": _FailingRecipe,
    "non_critical_fail_recipe": _NonCriticalFailRecipe,
    "exploding_recipe": _ExplodingRecipe,
}


def _run_executor(definition, dev, cancel=None):
    """Drive the WorkflowExecutor generator to completion."""
    if cancel is None:
        cancel = threading.Event()
    executor = WorkflowExecutor()
    gen = executor.run(definition, dev, cancel)
    results = []
    wf_summary = None
    try:
        while True:
            results.append(next(gen))
    except StopIteration as stop:
        wf_summary = stop.value
    return results, wf_summary


@pytest.fixture(autouse=True)
def _patch_registry():
    """Patch RECIPE_REGISTRY to use test stubs."""
    with patch(
        "serialcables_switchtec.core.workflows.workflow_executor.RECIPE_REGISTRY",
        _TEST_REGISTRY,
    ):
        yield


@pytest.fixture(autouse=True)
def _reset_exploding_recipe():
    """Reset shared class state before each test."""
    _ExplodingRecipe.cleanup_called = False
    yield
    _ExplodingRecipe.cleanup_called = False


class TestHappyPath:
    def test_two_passing_recipes(self):
        defn = WorkflowDefinition(
            name="Test Workflow",
            steps=[
                WorkflowStep(recipe_key="passing_recipe", params={"port_id": 0}),
                WorkflowStep(recipe_key="passing_recipe", params={"port_id": 1}),
            ],
        )
        dev = make_mock_device()
        results, summary = _run_executor(defn, dev)

        assert summary is not None
        assert summary.workflow_name == "Test Workflow"
        assert summary.total_recipes == 2
        assert summary.completed_recipes == 2
        assert summary.aborted is False
        assert len(summary.step_summaries) == 2

    def test_results_are_prefixed(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="passing_recipe")],
        )
        dev = make_mock_device()
        results, _ = _run_executor(defn, dev)

        # First result is INFO "Starting" announcement
        assert results[0].status == StepStatus.INFO
        assert "Starting" in results[0].step

        # Subsequent results should have prefixed recipe_name
        assert "[1/1]" in results[1].recipe_name
        assert "Passing Recipe" in results[1].recipe_name

    def test_step_names_include_recipe_name(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="passing_recipe")],
        )
        dev = make_mock_device()
        results, _ = _run_executor(defn, dev)

        # Recipe step results should be prefixed: "Passing Recipe > Step A"
        step_results = [r for r in results if r.status == StepStatus.PASS]
        assert len(step_results) == 2
        assert "Passing Recipe > Step A" in step_results[0].step

    def test_workflow_summary_step_summaries(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        for step_sum in summary.step_summaries:
            assert step_sum.recipe_summary is not None
            assert step_sum.recipe_summary.passed == 2
            assert step_sum.skipped is False


class TestAbortOnCriticalFail:
    def test_abort_stops_after_critical_failure(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="failing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is True
        assert summary.completed_recipes == 1
        assert len(summary.step_summaries) == 2
        assert summary.step_summaries[0].skipped is False
        assert summary.step_summaries[1].skipped is True

    def test_continue_after_failure_when_disabled(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="failing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=False,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.completed_recipes == 2
        assert all(not s.skipped for s in summary.step_summaries)

    def test_non_critical_fail_does_not_abort(self):
        """A NON_CRITICAL failure should NOT trigger abort even with abort_on_critical_fail=True."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="non_critical_fail_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.completed_recipes == 2
        assert all(not s.skipped for s in summary.step_summaries)

    def test_three_recipe_pass_noncritfail_pass(self):
        """pass -> non-critical fail -> pass should complete all three."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="non_critical_fail_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.completed_recipes == 3
        assert all(not s.skipped for s in summary.step_summaries)


class TestCancellation:
    def test_cancel_before_first_recipe(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
        )
        dev = make_mock_device()
        cancel = threading.Event()
        cancel.set()  # Cancel immediately

        _, summary = _run_executor(defn, dev, cancel)

        assert summary.aborted is True
        assert summary.completed_recipes == 0
        assert all(s.skipped for s in summary.step_summaries)

    def test_cancel_between_recipes(self):
        """Cancel after first recipe completes."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
        )
        dev = make_mock_device()
        cancel = threading.Event()

        executor = WorkflowExecutor()
        gen = executor.run(defn, dev, cancel)
        results = []

        # Consume first recipe: 1 INFO + 2 PASS = 3 results
        for _ in range(3):
            results.append(next(gen))

        # Cancel before second recipe
        cancel.set()

        # Drain remaining
        try:
            while True:
                results.append(next(gen))
        except StopIteration as stop:
            summary = stop.value

        assert summary.aborted is True
        assert summary.completed_recipes == 1


class TestExceptionHandling:
    def test_exploding_recipe_calls_cleanup(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="exploding_recipe")],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert _ExplodingRecipe.cleanup_called is True
        assert summary.aborted is True

    def test_exploding_recipe_yields_fail_result(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="exploding_recipe")],
        )
        dev = make_mock_device()
        results, _ = _run_executor(defn, dev)

        fail_results = [r for r in results if r.status == StepStatus.FAIL]
        assert len(fail_results) == 1
        assert "boom" in fail_results[0].detail

    def test_exploding_then_passing_with_abort(self):
        """Exception in first recipe should skip remaining when abort_on_critical_fail."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="exploding_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is True
        assert summary.completed_recipes == 0
        assert summary.step_summaries[1].skipped is True


class TestValidation:
    def test_invalid_recipe_key_raises_value_error(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="nonexistent_recipe")],
        )
        dev = make_mock_device()
        with pytest.raises(ValueError, match="unknown recipe key"):
            _run_executor(defn, dev)

    def test_invalid_param_raises_value_error(self):
        """Unknown params should be caught during up-front validation."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="passing_recipe", params={"bogus": 42})],
        )
        dev = make_mock_device()
        with pytest.raises(ValueError, match="unknown params"):
            _run_executor(defn, dev)

    def test_empty_workflow(self):
        defn = WorkflowDefinition(name="Empty", steps=[])
        dev = make_mock_device()
        results, summary = _run_executor(defn, dev)

        assert results == []
        assert summary.total_recipes == 0
        assert summary.completed_recipes == 0
        assert summary.step_summaries == []
        assert summary.aborted is False

    def test_summary_counts_are_correct(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="failing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.total_recipes == 3
        assert summary.completed_recipes == 2
        # Third recipe should be skipped due to abort
        assert summary.step_summaries[2].skipped is True
