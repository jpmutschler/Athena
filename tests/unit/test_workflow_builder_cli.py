"""Tests for the workflow builder CLI commands (list-workflows, run-workflow)."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from serialcables_switchtec.cli.recipe import recipe
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
)
from serialcables_switchtec.core.workflows.workflow_storage import WorkflowStorage


class TestListWorkflows:
    def test_no_saved_workflows(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        with patch(
            "serialcables_switchtec.core.workflows.workflow_storage.WorkflowStorage",
            return_value=storage,
        ):
            runner = CliRunner()
            result = runner.invoke(recipe, ["list-workflows"])
            assert result.exit_code == 0
            assert "No saved workflows" in result.output

    def test_with_saved_workflows(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        storage.save(WorkflowDefinition(
            name="Morning Checkout",
            description="Daily validation",
            steps=[
                WorkflowStep(recipe_key="link_health_check"),
                WorkflowStep(recipe_key="thermal_profile"),
            ],
        ))
        storage.save(WorkflowDefinition(
            name="Quick Test",
            description="Fast check",
            steps=[WorkflowStep(recipe_key="link_health_check")],
        ))

        with patch(
            "serialcables_switchtec.core.workflows.workflow_storage.WorkflowStorage",
            return_value=storage,
        ):
            runner = CliRunner()
            result = runner.invoke(recipe, ["list-workflows"])
            assert result.exit_code == 0
            assert "morning_checkout" in result.output
            assert "quick_test" in result.output
            assert "2 step(s)" in result.output
            assert "1 step(s)" in result.output


class TestRunWorkflow:
    def test_missing_device(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        storage.save(WorkflowDefinition(
            name="Test",
            steps=[WorkflowStep(recipe_key="link_health_check")],
        ))

        with patch(
            "serialcables_switchtec.core.workflows.workflow_storage.WorkflowStorage",
            return_value=storage,
        ):
            runner = CliRunner()
            result = runner.invoke(recipe, ["run-workflow", "test"])
            assert result.exit_code == 2

    def test_unknown_workflow_name(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)

        with patch(
            "serialcables_switchtec.core.workflows.workflow_storage.WorkflowStorage",
            return_value=storage,
        ):
            runner = CliRunner()
            result = runner.invoke(recipe, ["run-workflow", "nonexistent", "-d", "/dev/x"])
            assert result.exit_code == 2
            assert "not found" in result.output.lower()

    def test_workflow_not_found_shows_error(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        storage.save(WorkflowDefinition(name="Available", steps=[]))

        with patch(
            "serialcables_switchtec.core.workflows.workflow_storage.WorkflowStorage",
            return_value=storage,
        ):
            runner = CliRunner()
            result = runner.invoke(recipe, ["run-workflow", "missing", "-d", "/dev/x"])
            assert result.exit_code == 2
