"""Tests for WorkflowExecutionContext."""

from __future__ import annotations

from unittest.mock import MagicMock

from serialcables_switchtec.core.workflows.workflow_context import (
    WorkflowExecutionContext,
)


def _make_result(data=None):
    """Create a mock RecipeResult with the given data dict."""
    r = MagicMock()
    r.data = data
    return r


class TestBuildLabelIndex:
    def test_builds_from_steps(self):
        steps = [MagicMock(label="health"), MagicMock(label=""), MagicMock(label="ber")]
        ctx = WorkflowExecutionContext()
        ctx.build_label_index(steps)

        assert ctx.step_labels == {"health": 0, "ber": 2}
        assert ctx.total_steps == 3

    def test_empty_labels_ignored(self):
        steps = [MagicMock(label=""), MagicMock(label="")]
        ctx = WorkflowExecutionContext()
        ctx.build_label_index(steps)

        assert ctx.step_labels == {}

    def test_empty_steps(self):
        ctx = WorkflowExecutionContext()
        ctx.build_label_index([])

        assert ctx.total_steps == 0
        assert ctx.step_labels == {}


class TestSetStepData:
    def test_merges_result_data(self):
        ctx = WorkflowExecutionContext(total_steps=2)
        results = [
            _make_result({"temperature": 42}),
            _make_result({"link_up": True}),
        ]
        ctx.set_step_data(0, "health", results, had_critical_fail=False)

        assert ctx.step_data[0] == {"temperature": 42, "link_up": True}
        assert ctx.step_failed[0] is False

    def test_records_failure(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.set_step_data(0, "", [_make_result(None)], had_critical_fail=True)

        assert ctx.step_failed[0] is True

    def test_skips_none_data(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        results = [_make_result(None), _make_result({"a": 1})]
        ctx.set_step_data(0, "", results, had_critical_fail=False)

        assert ctx.step_data[0] == {"a": 1}

    def test_updates_label_index(self):
        ctx = WorkflowExecutionContext(total_steps=2)
        ctx.set_step_data(0, "health", [], had_critical_fail=False)

        assert ctx.step_labels["health"] == 0

    def test_empty_label_not_indexed(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.set_step_data(0, "", [], had_critical_fail=False)

        assert ctx.step_labels == {}


class TestResolve:
    def test_resolve_data(self):
        ctx = WorkflowExecutionContext(total_steps=2)
        ctx.step_data = {0: {"temperature": 42}}
        ctx.step_failed = {0: False}

        assert ctx.resolve("steps[0].data.temperature") == 42

    def test_resolve_by_label(self):
        ctx = WorkflowExecutionContext(total_steps=2)
        ctx.step_data = {0: {"link_up": True}}
        ctx.step_labels = {"health": 0}
        ctx.step_failed = {0: False}

        assert ctx.resolve("steps[health].data.link_up") is True

    def test_resolve_missing_returns_none(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        assert ctx.resolve("steps[99].data.x") is None


class TestEvalCondition:
    def test_condition_met(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.step_data = {0: {"link_up": True}}
        ctx.step_failed = {0: False}

        assert ctx.eval_condition("steps[0].data.link_up", "eq", True)

    def test_condition_not_met(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.step_data = {0: {"link_up": False}}
        ctx.step_failed = {0: False}

        assert not ctx.eval_condition("steps[0].data.link_up", "eq", True)

    def test_missing_ref_failopen(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        assert ctx.eval_condition("steps[99].data.x", "eq", True)


class TestResolveStepParams:
    def test_with_binding(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.step_data = {0: {"temperature": 42}}
        ctx.step_failed = {0: False}

        result = ctx.resolve_step_params(
            static_params={"threshold": 50},
            param_bindings={"threshold": "steps[0].data.temperature"},
        )
        assert result["threshold"] == 42

    def test_fallback_to_static(self):
        ctx = WorkflowExecutionContext(total_steps=1)
        ctx.step_data = {0: {}}
        ctx.step_failed = {0: False}

        result = ctx.resolve_step_params(
            static_params={"threshold": 50},
            param_bindings={"threshold": "steps[0].data.missing"},
        )
        assert result["threshold"] == 50
