"""Tests for workflow definition and summary models."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.models import RecipeSummary
from serialcables_switchtec.core.workflows.workflow_models import (
    LoopConfig,
    OnFailAction,
    StepCondition,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepSummary,
    WorkflowSummary,
)


class TestWorkflowStep:
    def test_frozen(self):
        step = WorkflowStep(recipe_key="link_health_check")
        with pytest.raises(Exception):
            step.recipe_key = "other"

    def test_defaults(self):
        step = WorkflowStep(recipe_key="ber_soak")
        assert step.label == ""
        assert step.params == {}
        assert step.on_fail == OnFailAction.ABORT
        assert step.on_fail_goto == ""
        assert step.param_bindings == {}
        assert step.loop is None
        assert step.condition is None

    def test_with_params(self):
        step = WorkflowStep(
            recipe_key="ber_soak",
            label="BER test",
            params={"port_id": 0, "duration_s": 30},
        )
        assert step.params["port_id"] == 0
        assert step.label == "BER test"

    def test_serialization_round_trip(self):
        step = WorkflowStep(
            recipe_key="thermal_profile",
            label="Thermal",
            params={"duration_s": 10},
        )
        json_str = step.model_dump_json()
        restored = WorkflowStep.model_validate_json(json_str)
        assert restored == step


class TestWorkflowDefinition:
    def test_frozen(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="link_health_check")],
        )
        with pytest.raises(Exception):
            defn.name = "Other"

    def test_defaults(self):
        defn = WorkflowDefinition(
            name="Test",
            steps=[],
        )
        assert defn.description == ""
        assert defn.abort_on_critical_fail is True
        assert defn.created_at == ""
        assert defn.updated_at == ""

    def test_required_name(self):
        with pytest.raises(Exception):
            WorkflowDefinition(steps=[])

    def test_serialization_round_trip(self):
        defn = WorkflowDefinition(
            name="Morning Checkout",
            description="Daily validation",
            steps=[
                WorkflowStep(recipe_key="link_health_check", params={"port_id": 0}),
                WorkflowStep(recipe_key="thermal_profile", params={"duration_s": 10}),
            ],
            abort_on_critical_fail=False,
            created_at="2026-03-01T12:00:00+00:00",
            updated_at="2026-03-01T12:00:00+00:00",
        )
        json_str = defn.model_dump_json()
        restored = WorkflowDefinition.model_validate_json(json_str)
        assert restored == defn
        assert len(restored.steps) == 2
        assert restored.steps[0].recipe_key == "link_health_check"

    def test_empty_steps_allowed(self):
        defn = WorkflowDefinition(name="Empty", steps=[])
        assert defn.steps == []


class TestWorkflowStepSummary:
    def test_frozen(self):
        summary = WorkflowStepSummary(
            step_index=0,
            recipe_key="link_health_check",
            recipe_name="Link Health Check",
        )
        with pytest.raises(Exception):
            summary.step_index = 1

    def test_defaults(self):
        summary = WorkflowStepSummary(
            step_index=0,
            recipe_key="link_health_check",
            recipe_name="Link Health Check",
        )
        assert summary.recipe_summary is None
        assert summary.skipped is False

    def test_with_recipe_summary(self):
        rs = RecipeSummary(
            recipe_name="Link Health Check",
            total_steps=3,
            passed=2,
            failed=1,
            warnings=0,
            skipped=0,
            elapsed_s=1.5,
            results=[],
        )
        summary = WorkflowStepSummary(
            step_index=0,
            recipe_key="link_health_check",
            recipe_name="Link Health Check",
            recipe_summary=rs,
        )
        assert summary.recipe_summary.passed == 2


class TestWorkflowSummary:
    def test_frozen(self):
        wfs = WorkflowSummary(
            workflow_name="Test",
            total_recipes=2,
            completed_recipes=1,
            step_summaries=[],
            elapsed_s=5.0,
        )
        with pytest.raises(Exception):
            wfs.workflow_name = "Other"

    def test_defaults(self):
        wfs = WorkflowSummary(
            workflow_name="Test",
            total_recipes=0,
            completed_recipes=0,
            step_summaries=[],
            elapsed_s=0.0,
        )
        assert wfs.aborted is False

    def test_serialization_round_trip(self):
        wfs = WorkflowSummary(
            workflow_name="Morning Checkout",
            total_recipes=3,
            completed_recipes=2,
            step_summaries=[
                WorkflowStepSummary(
                    step_index=0,
                    recipe_key="link_health_check",
                    recipe_name="Link Health Check",
                ),
                WorkflowStepSummary(
                    step_index=1,
                    recipe_key="thermal_profile",
                    recipe_name="Thermal Profile",
                    skipped=True,
                ),
            ],
            aborted=True,
            elapsed_s=12.5,
        )
        json_str = wfs.model_dump_json()
        restored = WorkflowSummary.model_validate_json(json_str)
        assert restored == wfs
        assert restored.step_summaries[1].skipped is True


class TestBackwardCompatibility:
    """Old JSON without new fields should deserialize correctly."""

    def test_old_step_json_loads(self):
        old_json = '{"recipe_key": "ber_soak", "label": "BER", "params": {"port_id": 0}}'
        step = WorkflowStep.model_validate_json(old_json)
        assert step.recipe_key == "ber_soak"
        assert step.on_fail == OnFailAction.ABORT
        assert step.param_bindings == {}
        assert step.loop is None
        assert step.condition is None

    def test_old_definition_json_loads(self):
        import json

        old = {
            "name": "Legacy",
            "steps": [
                {"recipe_key": "link_health_check", "params": {"port_id": 0}},
            ],
            "abort_on_critical_fail": True,
        }
        defn = WorkflowDefinition.model_validate_json(json.dumps(old))
        assert defn.name == "Legacy"
        assert defn.steps[0].on_fail == OnFailAction.ABORT

    def test_old_step_summary_json_loads(self):
        old_json = (
            '{"step_index": 0, "recipe_key": "lhc", '
            '"recipe_name": "Link Health", "skipped": false}'
        )
        summary = WorkflowStepSummary.model_validate_json(old_json)
        assert summary.skip_reason == ""
        assert summary.loop_iteration is None
        assert summary.iteration_summaries is None


class TestOnFailAction:
    def test_values(self):
        assert OnFailAction.ABORT == "abort"
        assert OnFailAction.CONTINUE == "continue"
        assert OnFailAction.SKIP_NEXT == "skip_next"
        assert OnFailAction.GOTO == "goto"

    def test_step_with_on_fail(self):
        step = WorkflowStep(
            recipe_key="ber_soak",
            on_fail=OnFailAction.GOTO,
            on_fail_goto="recovery",
        )
        assert step.on_fail == OnFailAction.GOTO
        assert step.on_fail_goto == "recovery"


class TestLoopConfig:
    def test_frozen(self):
        lc = LoopConfig(count=5)
        with pytest.raises(Exception):
            lc.count = 10

    def test_count_loop(self):
        lc = LoopConfig(count=3)
        assert lc.count == 3
        assert lc.over_values is None

    def test_over_values_loop(self):
        lc = LoopConfig(over_values=[0, 1, 2, 3], over_param="port_id")
        assert lc.over_values == [0, 1, 2, 3]
        assert lc.over_param == "port_id"

    def test_until_loop(self):
        lc = LoopConfig(until_ref="steps[0].data.link_up", until_value=True)
        assert lc.until_ref == "steps[0].data.link_up"
        assert lc.until_value is True

    def test_defaults(self):
        lc = LoopConfig()
        assert lc.count is None
        assert lc.over_values is None
        assert lc.over_param is None
        assert lc.until_ref is None
        assert lc.until_value is None
        assert lc.max_iterations == 100

    def test_serialization_round_trip(self):
        lc = LoopConfig(count=5, max_iterations=50)
        json_str = lc.model_dump_json()
        restored = LoopConfig.model_validate_json(json_str)
        assert restored == lc


class TestStepCondition:
    def test_frozen(self):
        cond = StepCondition(ref="steps[0].data.link_up")
        with pytest.raises(Exception):
            cond.ref = "other"

    def test_defaults(self):
        cond = StepCondition(ref="steps[0].data.link_up")
        assert cond.operator == "eq"
        assert cond.value is None

    def test_with_operator(self):
        cond = StepCondition(
            ref="steps[0].data.temperature",
            operator="gt",
            value=50,
        )
        assert cond.operator == "gt"
        assert cond.value == 50

    def test_serialization_round_trip(self):
        cond = StepCondition(ref="steps[0].data.x", operator="lte", value=100)
        json_str = cond.model_dump_json()
        restored = StepCondition.model_validate_json(json_str)
        assert restored == cond

    def test_invalid_operator_rejected(self):
        with pytest.raises(Exception):
            StepCondition(ref="steps[0].data.x", operator="bogus")


class TestWorkflowStepWithAdvancedFields:
    def test_full_step_serialization(self):
        step = WorkflowStep(
            recipe_key="ber_soak",
            label="BER test",
            params={"port_id": 0},
            on_fail=OnFailAction.CONTINUE,
            param_bindings={"threshold": "steps[0].data.temperature"},
            loop=LoopConfig(count=3),
            condition=StepCondition(ref="steps[0].data.link_up", operator="eq", value=True),
        )
        json_str = step.model_dump_json()
        restored = WorkflowStep.model_validate_json(json_str)
        assert restored == step
        assert restored.loop.count == 3
        assert restored.condition.ref == "steps[0].data.link_up"
        assert restored.on_fail == OnFailAction.CONTINUE


class TestWorkflowStepSummaryNewFields:
    def test_skip_reason(self):
        summary = WorkflowStepSummary(
            step_index=1,
            recipe_key="ber_soak",
            recipe_name="BER Soak",
            skipped=True,
            skip_reason="Condition not met",
        )
        assert summary.skip_reason == "Condition not met"

    def test_loop_fields(self):
        summary = WorkflowStepSummary(
            step_index=0,
            recipe_key="lhc",
            recipe_name="Link Health",
            loop_iteration=2,
            loop_total=5,
        )
        assert summary.loop_iteration == 2
        assert summary.loop_total == 5

    def test_iteration_summaries(self):
        rs = RecipeSummary(
            recipe_name="LHC",
            total_steps=2,
            passed=2,
            failed=0,
            warnings=0,
            skipped=0,
            elapsed_s=1.0,
            results=[],
        )
        summary = WorkflowStepSummary(
            step_index=0,
            recipe_key="lhc",
            recipe_name="LHC",
            iteration_summaries=[rs, rs],
        )
        assert len(summary.iteration_summaries) == 2
