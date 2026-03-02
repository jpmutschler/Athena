"""Integration tests: WorkflowExecutor -> real Recipes -> real RECIPE_REGISTRY.

These tests exercise multi-layer flows with real recipe code. Only the
SwitchtecDevice is mocked; everything above (executor, recipes, models)
runs as production code.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.core.workflows.workflow_executor import WorkflowExecutor
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowSummary,
)
from serialcables_switchtec.core.workflows.workflow_storage import WorkflowStorage

from tests.integration.conftest import (
    drive_generator,
    make_real_device_summary,
    make_real_port_status,
)


def _make_integration_device() -> MagicMock:
    """Create a mock device returning real Pydantic models."""
    dev = MagicMock()
    dev.get_status.return_value = [
        make_real_port_status(phys_id=0, link_up=True),
        make_real_port_status(phys_id=1, link_up=True),
        make_real_port_status(phys_id=2, link_up=False, ltssm_str="Detect"),
    ]
    dev.get_summary.return_value = make_real_device_summary(port_count=3)
    dev.get_die_temperatures.return_value = [42.5]
    dev.diagnostics = MagicMock()
    dev.diagnostics.ltssm_log.return_value = []
    dev.diagnostics.ltssm_clear.return_value = None
    dev.evcntr = MagicMock()
    dev.evcntr.setup.return_value = None
    dev.evcntr.get_counts.return_value = [0]
    dev.performance = MagicMock()
    dev.fabric = MagicMock()
    dev.firmware = MagicMock()
    dev.osa = MagicMock()
    dev.injector = MagicMock()
    return dev


@pytest.mark.integration
class TestExecutorWithRealRecipes:
    """WorkflowExecutor running real recipe implementations."""

    def test_single_recipe(self, cancel):
        """AllPortSweep through the real executor."""
        dev = _make_integration_device()
        definition = WorkflowDefinition(
            name="Single Test",
            steps=[WorkflowStep(recipe_key="all_port_sweep")],
        )

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(definition, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.completed_recipes == 1
        assert summary.aborted is False
        assert len(results) > 0

    def test_two_recipe_chain(self, cancel):
        """AllPortSweep -> LinkHealthCheck sequential chain."""
        dev = _make_integration_device()
        definition = WorkflowDefinition(
            name="Two-Step Chain",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(
                    recipe_key="link_health_check",
                    params={"port_id": 0},
                ),
            ],
        )

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(definition, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.completed_recipes == 2
        assert summary.aborted is False

    def test_three_recipe_workflow(self, cancel):
        """AllPortSweep -> LinkHealthCheck -> ConfigDump checkout chain."""
        dev = _make_integration_device()
        definition = WorkflowDefinition(
            name="Full Checkout",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(
                    recipe_key="link_health_check",
                    params={"port_id": 0},
                ),
                WorkflowStep(
                    recipe_key="config_dump",
                    params={"port_id": 0},
                ),
            ],
        )

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(definition, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.completed_recipes == 3
        assert summary.aborted is False
        assert len(summary.step_summaries) == 3

    def test_abort_on_critical_failure(self, cancel):
        """Device error during first recipe should abort remaining steps."""
        dev = _make_integration_device()
        dev.get_status.side_effect = Exception("device disconnected")

        definition = WorkflowDefinition(
            name="Abort Test",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(recipe_key="link_health_check", params={"port_id": 0}),
            ],
            abort_on_critical_fail=True,
        )

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(definition, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.aborted is True
        # Second recipe should be skipped
        skipped = [s for s in summary.step_summaries if s.skipped]
        assert len(skipped) >= 1

    def test_cancel_propagation(self, cancel):
        """Setting cancel event should skip remaining real recipes."""
        dev = _make_integration_device()
        cancel.set()  # Pre-cancel

        definition = WorkflowDefinition(
            name="Cancel Test",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(recipe_key="link_health_check", params={"port_id": 0}),
            ],
        )

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(definition, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.aborted is True
        skipped = [s for s in summary.step_summaries if s.skipped]
        assert len(skipped) == 2


@pytest.mark.integration
class TestStorageToExecutorIntegration:
    """Save -> Load -> Execute roundtrip with real recipes."""

    def test_save_load_execute_roundtrip(self, cancel, tmp_path):
        """JSON -> WorkflowStorage -> WorkflowExecutor -> real recipes."""
        dev = _make_integration_device()

        definition = WorkflowDefinition(
            name="Roundtrip Test",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(
                    recipe_key="link_health_check",
                    params={"port_id": 0},
                ),
            ],
        )

        storage = WorkflowStorage(base_dir=tmp_path)
        saved_path = storage.save(definition)
        assert saved_path.exists()

        loaded = storage.load("Roundtrip Test")
        assert loaded.name == definition.name
        assert len(loaded.steps) == 2

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(loaded, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.completed_recipes == 2
        assert summary.aborted is False

    def test_all_link_health_recipes_workflow(self, cancel, tmp_path):
        """Workflow with all link_health category recipes."""
        dev = _make_integration_device()

        # Use link_health_check and link_training_debug (both link_health category)
        definition = WorkflowDefinition(
            name="Link Health Suite",
            steps=[
                WorkflowStep(
                    recipe_key="link_health_check",
                    params={"port_id": 0},
                ),
                WorkflowStep(
                    recipe_key="link_training_debug",
                    params={"port_id": 0},
                ),
            ],
        )

        storage = WorkflowStorage(base_dir=tmp_path)
        storage.save(definition)
        loaded = storage.load("Link Health Suite")

        executor = WorkflowExecutor()
        results, summary = drive_generator(executor.run(loaded, dev, cancel))

        assert isinstance(summary, WorkflowSummary)
        assert summary.completed_recipes == 2
        assert summary.aborted is False

        # Both recipes should have executed
        recipe_names = [s.recipe_name for s in summary.step_summaries]
        assert "Link Health Check" in recipe_names
        assert "Link Training Debug" in recipe_names
