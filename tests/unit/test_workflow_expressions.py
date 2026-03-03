"""Tests for workflow expression parsing, resolution, and evaluation."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.workflow_expressions import (
    evaluate_condition,
    parse_ref,
    resolve_params,
    resolve_ref,
    resolve_step_index,
    walk_key_path,
)


class TestParseRef:
    def test_index_with_data_key(self):
        assert parse_ref("steps[0].data.temperature") == ("0", "data.temperature")

    def test_negative_index(self):
        assert parse_ref("steps[-1].data.total_errors") == ("-1", "data.total_errors")

    def test_label_ref(self):
        assert parse_ref("steps[link_check].data.link_up") == (
            "link_check",
            "data.link_up",
        )

    def test_nested_key_path(self):
        assert parse_ref("steps[0].data.ports.0.link_up") == (
            "0",
            "data.ports.0.link_up",
        )

    def test_failed_property(self):
        assert parse_ref("steps[0].failed") == ("0", "failed")

    def test_passed_property(self):
        assert parse_ref("steps[0].passed") == ("0", "passed")

    def test_status_property(self):
        assert parse_ref("steps[0].status") == ("0", "status")

    def test_whitespace_stripped(self):
        assert parse_ref("  steps[0].data.x  ") == ("0", "data.x")

    def test_invalid_format_returns_none(self):
        assert parse_ref("not_a_ref") is None

    def test_empty_string_returns_none(self):
        assert parse_ref("") is None

    def test_missing_bracket(self):
        assert parse_ref("steps[0.data.x") is None

    def test_unknown_property(self):
        assert parse_ref("steps[0].unknown_prop") is None


class TestResolveStepIndex:
    def test_positive_index(self):
        assert resolve_step_index("0", 5, {}) == 0
        assert resolve_step_index("4", 5, {}) == 4

    def test_negative_index(self):
        assert resolve_step_index("-1", 5, {}) == 4
        assert resolve_step_index("-5", 5, {}) == 0

    def test_out_of_bounds_returns_none(self):
        assert resolve_step_index("5", 5, {}) is None
        assert resolve_step_index("-6", 5, {}) is None

    def test_label_lookup(self):
        labels = {"health": 0, "ber": 2}
        assert resolve_step_index("health", 5, labels) == 0
        assert resolve_step_index("ber", 5, labels) == 2

    def test_unknown_label_returns_none(self):
        assert resolve_step_index("missing", 5, {}) is None

    def test_empty_steps(self):
        assert resolve_step_index("0", 0, {}) is None


class TestWalkKeyPath:
    def test_simple_key(self):
        assert walk_key_path({"temp": 42}, "temp") == 42

    def test_nested_key(self):
        data = {"ports": {"0": {"link_up": True}}}
        assert walk_key_path(data, "ports.0.link_up") is True

    def test_list_index(self):
        data = {"ports": [{"link_up": True}, {"link_up": False}]}
        assert walk_key_path(data, "ports.0.link_up") is True
        assert walk_key_path(data, "ports.1.link_up") is False

    def test_missing_key_returns_none(self):
        assert walk_key_path({"a": 1}, "b") is None

    def test_missing_nested_returns_none(self):
        assert walk_key_path({"a": {"b": 1}}, "a.c") is None

    def test_list_out_of_bounds_returns_none(self):
        data = {"items": [1, 2]}
        assert walk_key_path(data, "items.5") is None

    def test_non_dict_intermediate(self):
        assert walk_key_path({"a": 42}, "a.b") is None

    def test_empty_data(self):
        assert walk_key_path({}, "any.path") is None


class TestResolveRef:
    def _make_context(self):
        return {
            "step_data": {0: {"temperature": 42, "link_up": True}},
            "step_failed": {0: False},
            "total_steps": 2,
            "label_index": {"health": 0},
        }

    def test_resolve_data_by_index(self):
        ctx = self._make_context()
        result = resolve_ref("steps[0].data.temperature", **ctx)
        assert result == 42

    def test_resolve_data_by_label(self):
        ctx = self._make_context()
        result = resolve_ref("steps[health].data.link_up", **ctx)
        assert result is True

    def test_resolve_negative_index(self):
        ctx = self._make_context()
        ctx["step_data"][1] = {"errors": 5}
        result = resolve_ref("steps[-1].data.errors", **ctx)
        assert result == 5

    def test_resolve_failed(self):
        ctx = self._make_context()
        assert resolve_ref("steps[0].failed", **ctx) is False

    def test_resolve_passed(self):
        ctx = self._make_context()
        assert resolve_ref("steps[0].passed", **ctx) is True

    def test_resolve_status(self):
        ctx = self._make_context()
        assert resolve_ref("steps[0].status", **ctx) == "passed"

    def test_resolve_failed_step(self):
        ctx = self._make_context()
        ctx["step_failed"][0] = True
        assert resolve_ref("steps[0].failed", **ctx) is True
        assert resolve_ref("steps[0].passed", **ctx) is False
        assert resolve_ref("steps[0].status", **ctx) == "failed"

    def test_missing_step_data_returns_none(self):
        ctx = self._make_context()
        assert resolve_ref("steps[1].data.anything", **ctx) is None

    def test_invalid_ref_returns_none(self):
        ctx = self._make_context()
        assert resolve_ref("garbage", **ctx) is None

    def test_out_of_bounds_index_returns_none(self):
        ctx = self._make_context()
        assert resolve_ref("steps[99].data.x", **ctx) is None

    def test_missing_label_returns_none(self):
        ctx = self._make_context()
        assert resolve_ref("steps[nonexistent].data.x", **ctx) is None


class TestEvaluateCondition:
    def _ctx(self):
        return {
            "step_data": {0: {"temperature": 42, "link_up": True, "errors": 0}},
            "step_failed": {0: False},
            "total_steps": 2,
            "label_index": {},
        }

    def test_eq_true(self):
        assert evaluate_condition("steps[0].data.temperature", "eq", 42, **self._ctx())

    def test_eq_false(self):
        assert not evaluate_condition(
            "steps[0].data.temperature", "eq", 99, **self._ctx()
        )

    def test_ne(self):
        assert evaluate_condition("steps[0].data.temperature", "ne", 99, **self._ctx())

    def test_gt(self):
        assert evaluate_condition("steps[0].data.temperature", "gt", 40, **self._ctx())
        assert not evaluate_condition(
            "steps[0].data.temperature", "gt", 42, **self._ctx()
        )

    def test_lt(self):
        assert evaluate_condition("steps[0].data.temperature", "lt", 50, **self._ctx())

    def test_gte(self):
        assert evaluate_condition(
            "steps[0].data.temperature", "gte", 42, **self._ctx()
        )
        assert evaluate_condition(
            "steps[0].data.temperature", "gte", 41, **self._ctx()
        )

    def test_lte(self):
        assert evaluate_condition(
            "steps[0].data.temperature", "lte", 42, **self._ctx()
        )

    def test_is_true(self):
        assert evaluate_condition(
            "steps[0].data.link_up", "is_true", None, **self._ctx()
        )

    def test_is_false(self):
        assert evaluate_condition(
            "steps[0].data.errors", "is_false", None, **self._ctx()
        )
        assert not evaluate_condition(
            "steps[0].data.link_up", "is_false", None, **self._ctx()
        )

    def test_missing_ref_returns_true_failopen(self):
        assert evaluate_condition(
            "steps[99].data.x", "eq", 42, **self._ctx()
        )

    def test_unknown_operator_returns_true(self):
        assert evaluate_condition(
            "steps[0].data.temperature", "bogus_op", 42, **self._ctx()
        )

    def test_type_error_returns_true(self):
        # Comparing bool with int gt — should fail-open
        assert evaluate_condition(
            "steps[0].data.link_up", "gt", "not_a_number", **self._ctx()
        )


class TestResolveParams:
    def test_no_bindings_returns_static(self):
        result = resolve_params(
            static_params={"port_id": 0, "duration": 60},
            param_bindings={},
            step_data={},
            step_failed={},
            total_steps=0,
            label_index={},
        )
        assert result == {"port_id": 0, "duration": 60}

    def test_binding_overrides_static(self):
        result = resolve_params(
            static_params={"threshold": 50},
            param_bindings={"threshold": "steps[0].data.temperature"},
            step_data={0: {"temperature": 42}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert result["threshold"] == 42

    def test_failed_binding_keeps_static(self):
        result = resolve_params(
            static_params={"threshold": 50},
            param_bindings={"threshold": "steps[0].data.missing_key"},
            step_data={0: {"temperature": 42}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert result["threshold"] == 50

    def test_binding_adds_new_param(self):
        result = resolve_params(
            static_params={"port_id": 0},
            param_bindings={"threshold": "steps[0].data.temperature"},
            step_data={0: {"temperature": 42}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert result == {"port_id": 0, "threshold": 42}

    def test_does_not_mutate_static_params(self):
        static = {"port_id": 0}
        resolve_params(
            static_params=static,
            param_bindings={"threshold": "steps[0].data.temperature"},
            step_data={0: {"temperature": 42}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert "threshold" not in static


class TestAdversarialExpressions:
    """Verify that malicious or malformed expression strings are handled safely."""

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('whoami')",
        "eval('1+1')",
        "steps[0]; import os",
        "steps[0].data.__class__.__bases__",
        "",
        "   ",
        "steps[]",
        "steps[].data.x",
        "steps[0].data.",
        "steps[0].",
        "steps[0].data..x",
        "completely invalid",
        "steps[0].data.x; DROP TABLE users",
        "steps[0].data.x\nsteps[1].data.y",
    ])
    def test_adversarial_parse_ref_returns_none(self, expr):
        assert parse_ref(expr) is None

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('whoami')",
        "eval('1+1')",
        "",
        "garbage",
    ])
    def test_adversarial_resolve_ref_returns_none(self, expr):
        result = resolve_ref(
            expr,
            step_data={0: {"x": 1}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert result is None

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('whoami')",
        "",
        "garbage",
    ])
    def test_adversarial_evaluate_condition_failopen(self, expr):
        result = evaluate_condition(
            expr, "eq", True,
            step_data={0: {"x": 1}},
            step_failed={0: False},
            total_steps=1,
            label_index={},
        )
        assert result is True  # fail-open
