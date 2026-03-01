"""Tests for workflow recipes: FirmwareValidation, OsaCapture."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.firmware_validation import FirmwareValidation
from serialcables_switchtec.core.workflows.osa_capture import OsaCapture
from serialcables_switchtec.core.workflows.models import (
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError

from tests.unit.test_workflows_helpers import (
    final_results,
    make_mock_device,
    make_part_summary,
    run_recipe,
)


# ---------------------------------------------------------------------------
# FirmwareValidation
# ---------------------------------------------------------------------------


class TestFirmwareValidation:
    """Tests for the FirmwareValidation recipe."""

    def test_parameters_returns_empty_list(self):
        recipe = FirmwareValidation()
        params = recipe.parameters()

        assert params == []

    def test_happy_path_all_pass(self):
        """FW version read, all partitions valid, boot RO => 3 PASS steps."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.return_value = make_part_summary()
        dev.firmware.is_boot_ro.return_value = True

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 3
        assert all(r.status == StepStatus.PASS for r in finals)
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.aborted is False
        # Verify fw_version data attached to step 0
        assert finals[0].data == {"fw_version": "4.20"}
        assert "4.20" in finals[0].detail

    def test_get_fw_version_fails(self):
        """SwitchtecError on get_fw_version => FAIL step 0, early exit."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.side_effect = SwitchtecError("read failed")

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert finals[0].step_index == 0
        assert finals[0].criticality == StepCriticality.CRITICAL
        assert "read failed" in finals[0].detail
        assert summary.failed == 1
        assert summary.passed == 0

    def test_get_part_summary_fails(self):
        """SwitchtecError on get_part_summary => FAIL step 1, early exit."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.side_effect = SwitchtecError("part error")

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 2
        assert finals[0].status == StepStatus.PASS  # fw version read OK
        assert finals[1].status == StepStatus.FAIL
        assert finals[1].step_index == 1
        assert finals[1].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1
        assert summary.passed == 1

    def test_invalid_partitions_warn(self):
        """Some partitions invalid => WARN on step 1."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.return_value = make_part_summary(
            boot_valid=False,
        )
        dev.firmware.is_boot_ro.return_value = True

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[1].status == StepStatus.WARN
        assert finals[1].step_index == 1
        assert "boot" in finals[1].detail
        assert summary.warnings == 1

    def test_boot_writable_info(self):
        """Boot partition not RO => INFO step 2 (development mode)."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.return_value = make_part_summary()
        dev.firmware.is_boot_ro.return_value = False

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[2].status == StepStatus.INFO
        assert finals[2].step_index == 2
        assert "writable" in finals[2].detail
        assert "development" in finals[2].detail
        assert finals[2].data == {"is_boot_ro": False}

    def test_boot_ro_check_fails_warn(self):
        """SwitchtecError on is_boot_ro => WARN step 2 (not FAIL)."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.return_value = make_part_summary()
        dev.firmware.is_boot_ro.side_effect = SwitchtecError("ro check failed")

        results, summary = run_recipe(recipe, dev)
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[2].status == StepStatus.WARN
        assert finals[2].step_index == 2
        assert "ro check failed" in finals[2].detail
        assert summary.warnings == 1
        assert summary.failed == 0

    def test_step_count_consistency(self):
        """Every yielded result reports total_steps == 3."""
        recipe = FirmwareValidation()
        dev = make_mock_device()
        dev.firmware.get_fw_version.return_value = "4.20"
        dev.firmware.get_part_summary.return_value = make_part_summary()
        dev.firmware.is_boot_ro.return_value = True

        results, summary = run_recipe(recipe, dev)

        assert all(r.total_steps == 3 for r in results)
        assert summary.total_steps == 3


# ---------------------------------------------------------------------------
# OsaCapture
# ---------------------------------------------------------------------------


class TestOsaCapture:
    """Tests for the OsaCapture recipe."""

    def test_parameters_returns_three(self):
        recipe = OsaCapture()
        params = recipe.parameters()

        assert len(params) == 3
        param_names = [p.name for p in params]
        assert "stack_id" in param_names
        assert "lane_mask" in param_names
        assert "duration_s" in param_names

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_happy_path_all_pass(self, mock_time):
        """Configure, start, wait, stop+read => 4 PASS steps."""
        # Provide enough monotonic values for the full recipe flow.
        # Calls: start, step0 timing, step1 timing, wait-loop entry,
        # wait-loop condition, wait-loop remaining, wait-loop condition exit,
        # actual_wait, step3 timing, final summary
        mock_time.monotonic.side_effect = [
            0.0,   # recipe start
            0.1,   # after step 0 PASS
            0.2,   # after step 1 PASS
            0.3,   # wait_start
            0.3,   # while condition check
            0.3,   # remaining calc
            11.0,  # while condition check (exceeds duration_s=10)
            11.0,  # actual_wait calc
            11.1,  # after step 3
            11.2,  # final summary
        ]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()
        dev.osa.capture_data.return_value = 0

        results, summary = run_recipe(
            recipe, dev, stack_id=0, lane_mask=0x1, duration_s=10,
        )
        finals = final_results(results)

        assert len(finals) == 4
        assert all(r.status == StepStatus.PASS for r in finals)
        assert summary.passed == 4
        assert summary.failed == 0
        assert summary.aborted is False

        # Verify OSA calls
        dev.osa.configure_type.assert_called_once_with(
            0, direction=0, lane_mask=0x1, link_rate=0, os_types=0xFFFF,
        )
        dev.osa.start.assert_called_once_with(0)
        dev.osa.stop.assert_called_once_with(0)
        # lane_mask=0x1 => first_lane=0
        dev.osa.capture_data.assert_called_once_with(0, lane=0, direction=0)

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_configure_fails(self, mock_time):
        """SwitchtecError on configure_type => FAIL step 0, early exit."""
        mock_time.monotonic.side_effect = [0.0, 0.1]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()
        dev.osa.configure_type.side_effect = SwitchtecError("config error")

        results, summary = run_recipe(
            recipe, dev, stack_id=0, lane_mask=0x1, duration_s=10,
        )
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert finals[0].step_index == 0
        assert finals[0].criticality == StepCriticality.CRITICAL
        assert "config error" in finals[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_start_fails(self, mock_time):
        """SwitchtecError on osa.start => FAIL step 1, early exit."""
        mock_time.monotonic.side_effect = [0.0, 0.1, 0.2]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()
        dev.osa.start.side_effect = SwitchtecError("start error")

        results, summary = run_recipe(
            recipe, dev, stack_id=0, lane_mask=0x1, duration_s=10,
        )
        finals = final_results(results)

        assert len(finals) == 2
        assert finals[0].status == StepStatus.PASS  # configure OK
        assert finals[1].status == StepStatus.FAIL
        assert finals[1].step_index == 1
        assert "start error" in finals[1].detail
        assert summary.failed == 1
        assert summary.passed == 1

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_capture_data_fails(self, mock_time):
        """SwitchtecError on capture_data => FAIL step 3."""
        mock_time.monotonic.side_effect = [
            0.0, 0.1, 0.2,
            0.3, 0.3, 0.3, 11.0, 11.0,
            11.1, 11.2,
        ]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()
        dev.osa.capture_data.side_effect = SwitchtecError("capture failed")

        results, summary = run_recipe(
            recipe, dev, stack_id=0, lane_mask=0x1, duration_s=10,
        )
        finals = final_results(results)

        assert len(finals) == 4
        assert finals[0].status == StepStatus.PASS  # configure
        assert finals[1].status == StepStatus.PASS  # start
        assert finals[2].status == StepStatus.PASS  # wait
        assert finals[3].status == StepStatus.FAIL   # stop+read
        assert finals[3].step_index == 3
        assert "capture failed" in finals[3].detail
        assert summary.failed == 1
        assert summary.passed == 3

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_cancel_during_wait(self, mock_time):
        """Cancellation during the wait loop => osa.stop called, aborted."""
        mock_time.monotonic.side_effect = [
            0.0, 0.1, 0.2,
            0.3,  # wait_start
            0.3,  # while condition (< duration_s, enters loop)
            0.3,  # remaining calc
            0.4,  # while condition after sleep (still < duration, but cancel set)
            0.4,  # actual_wait
            0.5,  # cancel check -> aborted summary
        ]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()

        cancel = threading.Event()

        # Set cancel when sleep is called (simulating user cancel during wait)
        def set_cancel_on_sleep(_duration):
            cancel.set()

        mock_time.sleep.side_effect = set_cancel_on_sleep

        results, summary = run_recipe(
            recipe, dev, cancel=cancel, stack_id=0, lane_mask=0x1, duration_s=10,
        )

        assert summary.aborted is True
        # osa.stop should be called for cleanup on cancel after start
        dev.osa.stop.assert_called_with(0)

    @patch("serialcables_switchtec.core.workflows.osa_capture.time")
    def test_cancel_after_start_before_wait(self, mock_time):
        """Cancel set after start completes => osa.stop called, aborted."""
        mock_time.monotonic.side_effect = [0.0, 0.1, 0.2, 0.3]
        mock_time.sleep = MagicMock()

        recipe = OsaCapture()
        dev = make_mock_device()

        cancel = threading.Event()
        # Cancel right after start succeeds, before wait step begins

        def start_then_cancel(stack_id):
            cancel.set()

        dev.osa.start.side_effect = start_then_cancel

        results, summary = run_recipe(
            recipe, dev, cancel=cancel, stack_id=0, lane_mask=0x1, duration_s=10,
        )

        assert summary.aborted is True
        dev.osa.stop.assert_called_with(0)

    def test_cleanup_calls_osa_stop(self):
        """cleanup() calls dev.osa.stop(stack_id)."""
        recipe = OsaCapture()
        dev = make_mock_device()

        recipe.cleanup(dev, stack_id=3)

        dev.osa.stop.assert_called_once_with(3)
