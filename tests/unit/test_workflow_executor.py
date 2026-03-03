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
    LoopConfig,
    OnFailAction,
    StepCondition,
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


class _DataProducingRecipe(Recipe):
    """Yields results with known data dicts for testing data passing."""

    name = "Data Producer"
    description = "Produces data"
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~1s"

    def run(self, dev, cancel, **kwargs):
        r1 = self._make_result(
            "Measure", 0, 1, StepStatus.PASS,
            detail="measured",
            data={"temperature": 42, "link_up": True, "port_id": kwargs.get("port_id", 0)},
        )
        yield r1
        return self._make_summary([r1], 0.5)

    def parameters(self):
        return [
            RecipeParameter(name="port_id", display_name="Port", param_type="int", default=0),
        ]

    def estimated_duration_s(self, **kwargs):
        return 1.0


class _DataConsumingRecipe(Recipe):
    """Records received kwargs for assertion in tests."""

    name = "Data Consumer"
    description = "Consumes data"
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~1s"
    last_kwargs: dict = {}

    def run(self, dev, cancel, **kwargs):
        _DataConsumingRecipe.last_kwargs = dict(kwargs)
        r1 = self._make_result("Check", 0, 1, StepStatus.PASS, detail="ok")
        yield r1
        return self._make_summary([r1], 0.5)

    def parameters(self):
        return [
            RecipeParameter(name="port_id", display_name="Port", param_type="int", default=0),
            RecipeParameter(
                name="threshold", display_name="Threshold", param_type="int",
                default=50, required=False,
            ),
        ]

    def estimated_duration_s(self, **kwargs):
        return 1.0


class _CountingRecipe(Recipe):
    """Counts how many times it has been run (for loop tests)."""

    name = "Counting Recipe"
    description = "Counts runs"
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~1s"
    run_count: int = 0

    def run(self, dev, cancel, **kwargs):
        _CountingRecipe.run_count += 1
        count = _CountingRecipe.run_count
        r1 = self._make_result(
            "Count", 0, 1, StepStatus.PASS,
            detail=f"run #{count}",
            data={"run_count": count, "port_id": kwargs.get("port_id", 0)},
        )
        yield r1
        return self._make_summary([r1], 0.1)

    def parameters(self):
        return [
            RecipeParameter(name="port_id", display_name="Port", param_type="int", default=0),
        ]

    def estimated_duration_s(self, **kwargs):
        return 0.1


_TEST_REGISTRY = {
    "passing_recipe": _PassingRecipe,
    "failing_recipe": _FailingRecipe,
    "non_critical_fail_recipe": _NonCriticalFailRecipe,
    "exploding_recipe": _ExplodingRecipe,
    "data_producing_recipe": _DataProducingRecipe,
    "data_consuming_recipe": _DataConsumingRecipe,
    "counting_recipe": _CountingRecipe,
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
    _DataConsumingRecipe.last_kwargs = {}
    _CountingRecipe.run_count = 0
    yield
    _ExplodingRecipe.cleanup_called = False
    _DataConsumingRecipe.last_kwargs = {}
    _CountingRecipe.run_count = 0


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


# ---------------------------------------------------------------------------
# Phase 1: Data Passing + On-Fail Handling
# ---------------------------------------------------------------------------


class TestDataPassing:
    def test_step_binds_data_from_previous_step(self):
        """Step 0 emits {temperature: 42}, step 1 binds threshold to it."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="data_consuming_recipe",
                    param_bindings={"threshold": "steps[0].data.temperature"},
                ),
            ],
        )
        dev = make_mock_device()
        _run_executor(defn, dev)

        assert _DataConsumingRecipe.last_kwargs["threshold"] == 42

    def test_label_based_reference(self):
        """Bind by label: steps[health].data.link_up."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe", label="health"),
                WorkflowStep(
                    recipe_key="data_consuming_recipe",
                    param_bindings={"threshold": "steps[health].data.temperature"},
                ),
            ],
        )
        dev = make_mock_device()
        _run_executor(defn, dev)

        assert _DataConsumingRecipe.last_kwargs["threshold"] == 42

    def test_missing_ref_falls_back_to_static(self):
        """If binding ref fails, static param is used."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="data_consuming_recipe",
                    params={"threshold": 99},
                    param_bindings={"threshold": "steps[0].data.nonexistent"},
                ),
            ],
        )
        dev = make_mock_device()
        _run_executor(defn, dev)

        assert _DataConsumingRecipe.last_kwargs["threshold"] == 99

    def test_backward_compat_old_definition_still_works(self):
        """A definition with no new fields runs identically to before."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe", params={"port_id": 0}),
                WorkflowStep(recipe_key="passing_recipe", params={"port_id": 1}),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.completed_recipes == 2
        assert summary.aborted is False


class TestOnFailHandling:
    def test_on_fail_continue(self):
        """on_fail=CONTINUE: critical fail, next step still runs."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.CONTINUE,
                ),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.completed_recipes == 2

    def test_on_fail_skip_next(self):
        """on_fail=SKIP_NEXT: next step skipped, step after runs."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.SKIP_NEXT,
                ),
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="data_consuming_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.step_summaries[1].skipped is True
        assert summary.step_summaries[1].skip_reason == "Previous step failed (skip_next)"
        # Third step should have run
        assert summary.step_summaries[2].skipped is False

    def test_on_fail_goto(self):
        """on_fail=GOTO: jumps to labeled step."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.GOTO,
                    on_fail_goto="recovery",
                ),
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(
                    recipe_key="data_consuming_recipe",
                    label="recovery",
                ),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        # Step 0 ran (failed), jumped to step 2 (recovery)
        assert summary.step_summaries[0].skipped is False
        assert summary.step_summaries[1].recipe_key == "data_consuming_recipe"
        assert summary.step_summaries[1].skipped is False

    def test_on_fail_goto_invalid_label_raises(self):
        """GOTO to invalid label is caught during up-front validation."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.GOTO,
                    on_fail_goto="nonexistent",
                ),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        with pytest.raises(ValueError, match="unknown label"):
            _run_executor(defn, dev)


# ---------------------------------------------------------------------------
# Phase 2: Loop Constructs
# ---------------------------------------------------------------------------


class TestLoops:
    def test_count_loop(self):
        """count=3: recipe runs 3 times."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="counting_recipe",
                    loop=LoopConfig(count=3),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert _CountingRecipe.run_count == 3
        assert summary.step_summaries[0].loop_total == 3
        assert summary.step_summaries[0].iteration_summaries is not None
        assert len(summary.step_summaries[0].iteration_summaries) == 3

    def test_over_values_loop(self):
        """over_values=[0,1,2,3], over_param=port_id: 4 runs with different port_id."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="data_consuming_recipe",
                    loop=LoopConfig(
                        over_values=[0, 1, 2, 3],
                        over_param="port_id",
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        # Last iteration should have port_id=3
        assert _DataConsumingRecipe.last_kwargs["port_id"] == 3
        assert summary.step_summaries[0].loop_total == 4

    def test_until_ref_loop(self):
        """until_ref: runs until condition met."""
        # CountingRecipe emits data.run_count that increments each time
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="counting_recipe",
                    loop=LoopConfig(
                        until_ref="steps[0].data.run_count",
                        until_value=3,
                        max_iterations=10,
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert _CountingRecipe.run_count == 3

    def test_max_iterations_safety_cap(self):
        """max_iterations prevents infinite loops."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="counting_recipe",
                    loop=LoopConfig(
                        until_ref="steps[0].data.run_count",
                        until_value=999,  # Will never be reached
                        max_iterations=5,
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        results, summary = _run_executor(defn, dev)

        assert _CountingRecipe.run_count == 5
        # Should have a warning about max iterations
        warn_results = [r for r in results if r.status == StepStatus.WARN]
        assert len(warn_results) == 1
        assert "Safety cap" in warn_results[0].detail

    def test_cancel_mid_loop(self):
        """Cancel during a loop: remaining iterations skipped."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="counting_recipe",
                    loop=LoopConfig(count=100),
                ),
            ],
        )
        dev = make_mock_device()
        cancel = threading.Event()

        executor = WorkflowExecutor()
        gen = executor.run(defn, dev, cancel)
        results = []

        # Run a few iterations (each iteration = 1 INFO + 1 PASS = 2 results)
        for _ in range(4):
            results.append(next(gen))

        cancel.set()

        try:
            while True:
                results.append(next(gen))
        except StopIteration as stop:
            summary = stop.value

        # Should not have run all 100 iterations
        assert _CountingRecipe.run_count < 100


# ---------------------------------------------------------------------------
# Phase 3: Conditional Branching
# ---------------------------------------------------------------------------


class TestConditions:
    def test_condition_met_step_runs(self):
        """When condition is met, step executes normally."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="passing_recipe",
                    condition=StepCondition(
                        ref="steps[0].data.link_up",
                        operator="eq",
                        value=True,
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.completed_recipes == 2
        assert not summary.step_summaries[1].skipped

    def test_condition_not_met_step_skipped(self):
        """When condition is not met, step is skipped with reason."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="passing_recipe",
                    condition=StepCondition(
                        ref="steps[0].data.link_up",
                        operator="eq",
                        value=False,
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.step_summaries[1].skipped is True
        assert summary.step_summaries[1].skip_reason == "Condition not met"

    def test_condition_all_operators(self):
        """Test all comparison operators."""
        dev = make_mock_device()

        # Data producer emits temperature=42
        operators_and_expected = [
            ("eq", 42, True),
            ("eq", 99, False),
            ("ne", 99, True),
            ("ne", 42, False),
            ("gt", 41, True),
            ("gt", 42, False),
            ("lt", 43, True),
            ("lt", 42, False),
            ("gte", 42, True),
            ("gte", 43, False),
            ("lte", 42, True),
            ("lte", 41, False),
        ]
        for op, val, should_run in operators_and_expected:
            defn = WorkflowDefinition(
                name="Test",
                steps=[
                    WorkflowStep(recipe_key="data_producing_recipe"),
                    WorkflowStep(
                        recipe_key="passing_recipe",
                        condition=StepCondition(
                            ref="steps[0].data.temperature",
                            operator=op,
                            value=val,
                        ),
                    ),
                ],
            )
            _, summary = _run_executor(defn, dev)
            actual = not summary.step_summaries[1].skipped
            assert actual == should_run, f"op={op}, val={val}: expected run={should_run}, got {actual}"

    def test_condition_is_true(self):
        dev = make_mock_device()
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="passing_recipe",
                    condition=StepCondition(
                        ref="steps[0].data.link_up",
                        operator="is_true",
                    ),
                ),
            ],
        )
        _, summary = _run_executor(defn, dev)
        assert not summary.step_summaries[1].skipped

    def test_condition_is_false(self):
        dev = make_mock_device()
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="data_producing_recipe"),
                WorkflowStep(
                    recipe_key="passing_recipe",
                    condition=StepCondition(
                        ref="steps[0].data.link_up",
                        operator="is_false",
                    ),
                ),
            ],
        )
        _, summary = _run_executor(defn, dev)
        assert summary.step_summaries[1].skipped is True

    def test_missing_ref_in_condition_failopen(self):
        """Missing ref in condition: step runs (fail-open)."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="passing_recipe",
                    condition=StepCondition(
                        ref="steps[99].data.nonexistent",
                        operator="eq",
                        value=True,
                    ),
                ),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.completed_recipes == 1
        assert not summary.step_summaries[0].skipped


class TestOnFailEdgeCases:
    def test_skip_next_on_last_step(self):
        """SKIP_NEXT on the last step: nothing to skip, workflow ends."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.SKIP_NEXT,
                ),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.completed_recipes == 2
        assert len(summary.step_summaries) == 2

    def test_skip_next_on_second_to_last(self):
        """SKIP_NEXT on second-to-last step: last step is skipped."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.SKIP_NEXT,
                ),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        assert summary.step_summaries[1].skipped is True
        assert summary.step_summaries[1].skip_reason == "Previous step failed (skip_next)"

    def test_goto_forward(self):
        """GOTO to a step ahead of current (skipping intermediate)."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.GOTO,
                    on_fail_goto="final",
                ),
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="passing_recipe"),
                WorkflowStep(recipe_key="data_consuming_recipe", label="final"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)

        assert summary.aborted is False
        # Step 0: failing (ran), step 3: final (ran); steps 1-2: not in summaries
        step_keys = [s.recipe_key for s in summary.step_summaries]
        assert step_keys[0] == "failing_recipe"
        assert step_keys[1] == "data_consuming_recipe"


class TestUpFrontValidation:
    def test_duplicate_label_raises_value_error(self):
        """Duplicate labels are caught during validation."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe", label="dup"),
                WorkflowStep(recipe_key="passing_recipe", label="dup"),
            ],
        )
        dev = make_mock_device()
        with pytest.raises(ValueError, match="duplicate label"):
            _run_executor(defn, dev)

    def test_invalid_goto_target_raises_value_error(self):
        """GOTO referencing a non-existent label is caught during validation."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    on_fail=OnFailAction.GOTO,
                    on_fail_goto="does_not_exist",
                ),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
        )
        dev = make_mock_device()
        with pytest.raises(ValueError, match="unknown label"):
            _run_executor(defn, dev)

    def test_empty_labels_not_treated_as_duplicate(self):
        """Steps with empty labels should not conflict."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(recipe_key="passing_recipe", label=""),
                WorkflowStep(recipe_key="passing_recipe", label=""),
            ],
        )
        dev = make_mock_device()
        _, summary = _run_executor(defn, dev)
        assert summary.completed_recipes == 2


class TestGotoCycleDetection:
    def test_goto_cycle_aborts(self):
        """GOTO that creates a cycle is detected and aborted."""
        defn = WorkflowDefinition(
            name="Test",
            steps=[
                WorkflowStep(
                    recipe_key="failing_recipe",
                    label="loop_start",
                    on_fail=OnFailAction.GOTO,
                    on_fail_goto="loop_start",
                ),
                WorkflowStep(recipe_key="passing_recipe"),
            ],
            abort_on_critical_fail=True,
        )
        dev = make_mock_device()
        results, summary = _run_executor(defn, dev)

        assert summary.aborted is True
        # Should have a cycle detection fail result
        cycle_results = [r for r in results if "Cycle detected" in (r.step or "")]
        assert len(cycle_results) == 1
