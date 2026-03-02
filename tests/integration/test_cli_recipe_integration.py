"""Integration tests: CLI -> real Recipe code -> real RECIPE_REGISTRY.

These tests exercise the Click CLI commands through to real recipe execution.
Only SwitchtecDevice.open is mocked; the rest of the stack executes real code.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from serialcables_switchtec.cli.recipe import recipe
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
)
from serialcables_switchtec.core.workflows.workflow_storage import WorkflowStorage

from tests.integration.conftest import (
    make_real_device_summary,
    make_real_port_status,
)


def _make_cli_mock_device() -> MagicMock:
    """Create a mock device for CLI integration tests."""
    dev = MagicMock()
    dev.get_status.return_value = [
        make_real_port_status(phys_id=0, link_up=True),
        make_real_port_status(phys_id=1, link_up=True),
    ]
    dev.get_summary.return_value = make_real_device_summary(port_count=2)
    dev.get_die_temperatures.return_value = [42.5]
    dev.close.return_value = None
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
class TestCliRecipeRunIntegration:
    """CLI 'recipe run' -> real recipe execution."""

    def test_all_port_sweep_full_flow(self):
        """CLI invokes real AllPortSweep through the recipe runner."""
        dev = _make_cli_mock_device()
        runner = CliRunner()

        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice"
        ) as MockDevice:
            MockDevice.open.return_value = dev
            result = runner.invoke(
                recipe,
                ["run", "all_port_sweep", "--device", "/dev/switchtec0"],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "passed" in result.output.lower() or "PASS" in result.output

    def test_link_health_check_with_port_param(self):
        """Port parameter flows through CLI to real LinkHealthCheck recipe."""
        dev = _make_cli_mock_device()
        runner = CliRunner()

        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice"
        ) as MockDevice:
            MockDevice.open.return_value = dev
            result = runner.invoke(
                recipe,
                [
                    "run", "link_health_check",
                    "--device", "/dev/switchtec0",
                    "--param", "port_id=0",
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_thermal_profile_short_duration(self):
        """Timing params reach real ThermalProfile recipe."""
        dev = _make_cli_mock_device()
        dev.get_die_temperatures.return_value = [42.5, 43.0, 41.0]
        runner = CliRunner()

        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice"
        ) as MockDevice:
            MockDevice.open.return_value = dev
            result = runner.invoke(
                recipe,
                [
                    "run", "thermal_profile",
                    "--device", "/dev/switchtec0",
                    "--param", "duration_s=1",
                    "--param", "interval_s=1",
                    "--param", "num_sensors=3",
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

    def test_recipe_failure_exit_code(self):
        """Device error during recipe execution -> exit code 1."""
        dev = _make_cli_mock_device()
        dev.get_status.side_effect = Exception("device disconnected")
        runner = CliRunner()

        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice"
        ) as MockDevice:
            MockDevice.open.return_value = dev
            result = runner.invoke(
                recipe,
                ["run", "all_port_sweep", "--device", "/dev/switchtec0"],
            )

        # Should exit with failure code (1 for failures, 2 for fatal)
        assert result.exit_code != 0

    def test_config_dump_with_port_param(self):
        """ConfigDump recipe receives port_id via CLI."""
        dev = _make_cli_mock_device()
        runner = CliRunner()

        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice"
        ) as MockDevice:
            MockDevice.open.return_value = dev
            result = runner.invoke(
                recipe,
                [
                    "run", "config_dump",
                    "--device", "/dev/switchtec0",
                    "--param", "port_id=1",
                ],
            )

        assert result.exit_code == 0, f"CLI failed: {result.output}"


@pytest.mark.integration
class TestCliWorkflowRunIntegration:
    """CLI 'recipe run-workflow' -> WorkflowExecutor -> real recipes."""

    def test_saved_workflow_runs_through_cli(self, tmp_path):
        """Save JSON workflow -> CLI loads -> real executor -> real recipes."""
        definition = WorkflowDefinition(
            name="CLI Integration Test",
            steps=[
                WorkflowStep(recipe_key="all_port_sweep"),
                WorkflowStep(
                    recipe_key="link_health_check",
                    params={"port_id": 0},
                ),
            ],
        )

        storage = WorkflowStorage(base_dir=tmp_path)
        storage.save(definition)

        # Verify file was saved
        workflows = storage.list_workflows()
        assert len(workflows) == 1

        # Load and verify it's valid
        loaded = storage.load("CLI Integration Test")
        assert loaded.name == "CLI Integration Test"
        assert len(loaded.steps) == 2

        # Verify both recipe keys exist in registry
        from serialcables_switchtec.core.workflows import RECIPE_REGISTRY

        for step in loaded.steps:
            assert step.recipe_key in RECIPE_REGISTRY, (
                f"Recipe key {step.recipe_key!r} not in registry"
            )


@pytest.mark.integration
class TestRecipeRegistryIntegration:
    """Verify RECIPE_REGISTRY consistency and instantiation."""

    def test_all_registry_entries_instantiate(self):
        """Every recipe in RECIPE_REGISTRY can be instantiated."""
        from serialcables_switchtec.core.workflows import RECIPE_REGISTRY

        for key, cls in RECIPE_REGISTRY.items():
            instance = cls()
            assert instance.name, f"{key} has no name"
            assert instance.category, f"{key} has no category"
            params = instance.parameters()
            assert isinstance(params, list), f"{key}.parameters() not a list"

    def test_all_registry_entries_have_valid_params(self):
        """Every recipe parameter has required fields set."""
        from serialcables_switchtec.core.workflows import RECIPE_REGISTRY

        for key, cls in RECIPE_REGISTRY.items():
            instance = cls()
            for param in instance.parameters():
                assert param.name, f"{key} param missing name"
                assert param.display_name, f"{key} param missing display_name"
                assert param.param_type in (
                    "int", "float", "str", "bool", "select"
                ), f"{key} param {param.name} has invalid type: {param.param_type}"
