"""Tests for workflow recipes: FabricBindUnbind, ConfigDump."""

from __future__ import annotations

import threading

from serialcables_switchtec.core.workflows.config_dump import ConfigDump
from serialcables_switchtec.core.workflows.fabric_bind_unbind import FabricBindUnbind
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError

from tests.unit.test_workflows_helpers import (
    final_results,
    make_device_summary,
    make_mock_device,
    make_port_config,
    make_port_status,
    run_recipe,
)


# ---------------------------------------------------------------------------
# FabricBindUnbind
# ---------------------------------------------------------------------------


class TestFabricBindUnbind:
    """Tests for the FabricBindUnbind recipe."""

    def test_parameters(self):
        recipe = FabricBindUnbind()
        params = recipe.parameters()
        names = [p.name for p in params]

        assert isinstance(params, list)
        assert len(params) == 4
        assert "host_sw_idx" in names
        assert "host_phys_port_id" in names
        assert "host_log_port_id" in names
        assert "ep_pdfid" in names

    def test_metadata(self):
        recipe = FabricBindUnbind()

        assert recipe.name == "Fabric Bind/Unbind Validation"
        assert recipe.category == RecipeCategory.CONFIGURATION

    def test_happy_path(self):
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        dev.fabric.get_port_config.return_value = make_port_config(
            phys_port_id=2, port_type=1,
        )

        results, summary = run_recipe(
            recipe, dev,
            host_sw_idx=0,
            host_phys_port_id=2,
            host_log_port_id=3,
            ep_pdfid=100,
        )
        final = final_results(results)

        # Four terminal steps: config read, bind, unbind, verify
        assert len(final) == 4
        assert all(r.recipe_name == "Fabric Bind/Unbind Validation" for r in final)

        # Step 0: Read port config - PASS
        assert final[0].step == "Read port config"
        assert final[0].status == StepStatus.PASS
        assert final[0].data["phys_port_id"] == 2
        assert final[0].data["port_type"] == 1

        # Step 1: Bind - PASS
        assert final[1].step == "Bind"
        assert final[1].status == StepStatus.PASS

        # Step 2: Unbind - PASS
        assert final[2].step == "Unbind"
        assert final[2].status == StepStatus.PASS

        # Step 3: Verify - PASS
        assert final[3].step == "Verify"
        assert final[3].status == StepStatus.PASS

        # Summary
        assert summary is not None
        assert summary.passed == 4
        assert summary.failed == 0
        assert summary.aborted is False

    def test_get_port_config_fails(self):
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        dev.fabric.get_port_config.side_effect = SwitchtecError("config read error")

        results, summary = run_recipe(recipe, dev, host_phys_port_id=5)
        final = final_results(results)

        # Only 1 terminal step before early exit
        assert len(final) == 1
        assert final[0].step == "Read port config"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "config read error" in final[0].detail

        assert summary is not None
        assert summary.failed == 1
        assert summary.passed == 0

    def test_bind_fails(self):
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        dev.fabric.get_port_config.return_value = make_port_config()
        dev.fabric.bind.side_effect = SwitchtecError("bind refused")

        results, summary = run_recipe(recipe, dev)
        final = final_results(results)

        # 2 terminal steps: config read PASS, bind FAIL
        assert len(final) == 2
        assert final[0].status == StepStatus.PASS
        assert final[1].step == "Bind"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL
        assert "bind refused" in final[1].detail

        assert summary.failed == 1
        assert summary.passed == 1

    def test_unbind_fails(self):
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        dev.fabric.get_port_config.return_value = make_port_config()
        dev.fabric.unbind.side_effect = SwitchtecError("unbind error")

        results, summary = run_recipe(recipe, dev)
        final = final_results(results)

        # 3 terminal steps: config PASS, bind PASS, unbind FAIL
        assert len(final) == 3
        assert final[0].status == StepStatus.PASS
        assert final[1].status == StepStatus.PASS
        assert final[2].step == "Unbind"
        assert final[2].status == StepStatus.FAIL
        assert final[2].criticality == StepCriticality.CRITICAL
        assert "unbind error" in final[2].detail

        assert summary.failed == 1
        assert summary.passed == 2

    def test_verify_fails_yields_warn(self):
        """Verify step failure is non-critical and yields WARN, not FAIL."""
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        # First call succeeds (step 0), second call fails (step 3 verify)
        dev.fabric.get_port_config.side_effect = [
            make_port_config(),
            SwitchtecError("verify read error"),
        ]

        results, summary = run_recipe(recipe, dev)
        final = final_results(results)

        assert len(final) == 4
        assert final[3].step == "Verify"
        assert final[3].status == StepStatus.WARN
        assert "verify read error" in final[3].detail

        # Verify is non-critical, so summary should show warning not failure
        assert summary.warnings == 1
        assert summary.failed == 0

    def test_cancel_after_bind_calls_cleanup(self):
        """Cancellation after bind triggers cleanup (unbind)."""
        recipe = FabricBindUnbind()
        dev = make_mock_device()
        dev.fabric.get_port_config.return_value = make_port_config()

        cancel = threading.Event()
        # Set cancel after bind step yields its PASS result.
        # We intercept the generator manually to set cancel at the right time.
        gen = recipe.run(
            dev, cancel,
            host_sw_idx=1,
            host_phys_port_id=2,
            host_log_port_id=3,
            ep_pdfid=42,
        )
        step_names = []
        try:
            while True:
                result = next(gen)
                step_names.append((result.step, result.status))
                # Cancel right after bind PASS is yielded
                if result.step == "Bind" and result.status == StepStatus.PASS:
                    cancel.set()
        except StopIteration as stop:
            summary = stop.value

        assert summary.aborted is True
        # fabric.unbind should have been called for cleanup
        # (once from cleanup, even though unbind step was not reached)
        dev.fabric.unbind.assert_called()

    def test_cleanup_calls_unbind(self):
        """cleanup() method directly calls fabric.unbind with correct request."""
        recipe = FabricBindUnbind()
        dev = make_mock_device()

        recipe.cleanup(
            dev,
            host_sw_idx=0,
            host_phys_port_id=5,
            host_log_port_id=6,
            ep_pdfid=200,
        )

        dev.fabric.unbind.assert_called_once()
        unbind_req = dev.fabric.unbind.call_args[0][0]
        assert unbind_req.host_sw_idx == 0
        assert unbind_req.host_phys_port_id == 5
        assert unbind_req.host_log_port_id == 6
        assert unbind_req.pdfid == 200
        assert unbind_req.option == 0


# ---------------------------------------------------------------------------
# ConfigDump
# ---------------------------------------------------------------------------


class TestConfigDump:
    """Tests for the ConfigDump recipe."""

    def test_parameters(self):
        recipe = ConfigDump()
        params = recipe.parameters()
        names = [p.name for p in params]

        assert isinstance(params, list)
        assert len(params) == 1
        assert "port_id" in names

    def test_metadata(self):
        recipe = ConfigDump()

        assert recipe.name == "Config Space Dump"
        assert recipe.category == RecipeCategory.CONFIGURATION

    def test_happy_path_link_up(self):
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.return_value = make_device_summary(
            name="PSX 48XG6", generation="GEN6", fw_version="4.20",
        )
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, link_rate="16 GT/s", neg_lnk_width=4),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0)
        final = final_results(results)

        # 3 terminal steps: device summary, port status, report config
        assert len(final) == 3

        # Step 0: Device summary - PASS
        assert final[0].step == "Device summary"
        assert final[0].status == StepStatus.PASS
        assert final[0].data["name"] == "PSX 48XG6"
        assert final[0].data["generation"] == "GEN6"
        assert final[0].data["fw_version"] == "4.20"

        # Step 1: Port status - PASS (link up)
        assert final[1].step == "Port status"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["link_up"] is True
        assert final[1].data["pci_bdf"] == "00:00.0"
        assert final[1].data["vendor_id"] == 0x11F8
        assert final[1].data["cfg_lnk_width"] == 4

        # Step 2: Report config - PASS
        assert final[2].step == "Report config"
        assert final[2].status == StepStatus.PASS
        assert "Config dump complete" in final[2].detail

        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.warnings == 0

    def test_get_summary_fails(self):
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.side_effect = SwitchtecError("summary unavailable")

        results, summary = run_recipe(recipe, dev, port_id=0)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Device summary"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "summary unavailable" in final[0].detail

        assert summary.failed == 1
        assert summary.passed == 0

    def test_get_status_fails(self):
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.return_value = make_device_summary()
        dev.get_status.side_effect = SwitchtecError("status error")

        results, summary = run_recipe(recipe, dev, port_id=0)
        final = final_results(results)

        # 2 terminal steps: summary PASS, port status FAIL
        assert len(final) == 2
        assert final[0].status == StepStatus.PASS
        assert final[1].step == "Port status"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL

        assert summary.failed == 1
        assert summary.passed == 1

    def test_port_not_found(self):
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.return_value = make_device_summary()
        # Return ports, but none matching port_id=5
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True),
            make_port_status(phys_id=1, link_up=True),
        ]

        results, summary = run_recipe(recipe, dev, port_id=5)
        final = final_results(results)

        assert len(final) == 2
        assert final[1].step == "Port status"
        assert final[1].status == StepStatus.FAIL
        assert "Port 5 not found" in final[1].detail

        assert summary.failed == 1

    def test_port_link_down_yields_warn(self):
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.return_value = make_device_summary()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=False),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0)
        final = final_results(results)

        assert len(final) == 3

        # Step 1: Port status - WARN (link down)
        assert final[1].step == "Port status"
        assert final[1].status == StepStatus.WARN
        assert "DOWN" in final[1].detail

        # Step 2: Report config - WARN (link down propagates)
        assert final[2].step == "Report config"
        assert final[2].status == StepStatus.WARN
        assert "DOWN" in final[2].detail

        assert summary.warnings == 2
        assert summary.failed == 0

    def test_step_count_consistency(self):
        """Every result reports total_steps=3 matching the recipe design."""
        recipe = ConfigDump()
        dev = make_mock_device()
        dev.get_summary.return_value = make_device_summary()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0)

        for r in results:
            assert r.total_steps == 3, (
                f"Step '{r.step}' reports total_steps={r.total_steps}, expected 3"
            )
