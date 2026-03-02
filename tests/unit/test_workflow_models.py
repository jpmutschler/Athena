"""Tests for workflow definition and summary models."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.models import RecipeSummary
from serialcables_switchtec.core.workflows.workflow_models import (
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
