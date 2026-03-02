"""Tests for link analysis workflow recipes: LinkHealthCheck, LinkTrainingDebug, LtssmMonitor."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.link_health_check import LinkHealthCheck
from serialcables_switchtec.core.workflows.link_training_debug import LinkTrainingDebug
from serialcables_switchtec.core.workflows.ltssm_continuous import LtssmContinuousCapture
from serialcables_switchtec.core.workflows.ltssm_event_capture import LtssmEventCapture
from serialcables_switchtec.core.workflows.ltssm_monitor import LtssmMonitor
from serialcables_switchtec.core.workflows.models import (
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError
from tests.unit.test_workflows_helpers import (
    final_results,
    make_ltssm_entry,
    make_mock_device,
    make_port_status,
    run_recipe,
)


# ---------------------------------------------------------------------------
# LinkHealthCheck
# ---------------------------------------------------------------------------


class TestLinkHealthCheck:
    """Tests for the LinkHealthCheck recipe."""

    def test_parameters_returns_port_id(self):
        recipe = LinkHealthCheck()
        params = recipe.parameters()

        assert len(params) == 1
        assert params[0].name == "port_id"
        assert params[0].param_type == "int"
        assert params[0].default == 0

    def test_happy_path_link_up_temp_normal(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, link_rate="16 GT/s", neg_lnk_width=4),
        ]
        dev.get_die_temperatures.return_value = [42.5]

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[0].status == StepStatus.PASS  # Read port status
        assert finals[1].status == StepStatus.PASS  # Check link state
        assert "UP" in finals[1].detail
        assert finals[2].status == StepStatus.PASS  # Read temperature
        assert "42.5" in finals[2].detail
        assert summary.failed == 0
        assert summary.aborted is False

    def test_get_status_fails(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.side_effect = SwitchtecError("device error")

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert finals[0].criticality == StepCriticality.CRITICAL
        assert "device error" in finals[0].detail
        assert summary.failed == 1

    def test_port_not_found(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=5, link_up=True),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        # Step 0 passes (status retrieved), step 1 fails (port not found)
        assert finals[0].status == StepStatus.PASS
        assert finals[1].status == StepStatus.FAIL
        assert "not found" in finals[1].detail
        assert summary.failed == 1

    def test_port_link_down_warns_with_ltssm(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(
                phys_id=0,
                link_up=False,
                ltssm=0x03,
                ltssm_str="Polling.Active",
            ),
        ]
        dev.get_die_temperatures.return_value = [40.0]

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        link_step = finals[1]
        assert link_step.status == StepStatus.WARN
        assert "DOWN" in link_step.detail
        assert "Polling.Active" in link_step.detail
        assert summary.warnings >= 1

    def test_temperature_at_threshold_warns(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True),
        ]
        dev.get_die_temperatures.return_value = [85.0]

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        temp_step = finals[2]
        assert temp_step.status == StepStatus.WARN
        assert "85.0" in temp_step.detail

    def test_temperature_read_fails_warns(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True),
        ]
        dev.get_die_temperatures.side_effect = SwitchtecError("sensor error")

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        temp_step = finals[2]
        assert temp_step.status == StepStatus.WARN
        assert "Could not read temperature" in temp_step.detail

    def test_cancellation_aborts(self):
        recipe = LinkHealthCheck()
        dev = make_mock_device()
        cancel = threading.Event()
        cancel.set()

        results, summary = run_recipe(recipe, dev, cancel=cancel, port_id=0)

        assert summary.aborted is True


# ---------------------------------------------------------------------------
# LinkTrainingDebug
# ---------------------------------------------------------------------------


class TestLinkTrainingDebug:
    """Tests for the LinkTrainingDebug recipe."""

    def test_parameters_returns_port_id(self):
        recipe = LinkTrainingDebug()
        params = recipe.parameters()

        assert len(params) == 1
        assert params[0].name == "port_id"

    def test_happy_path_link_up_no_transitions(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, ltssm_str="L0"),
        ]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert len(finals) == 4
        assert finals[0].status == StepStatus.PASS  # Read port status
        assert finals[1].status == StepStatus.PASS  # Read LTSSM state
        assert finals[2].status == StepStatus.PASS  # Read LTSSM log (0 transitions)
        assert finals[3].status == StepStatus.PASS  # Analyze
        assert "no training issue" in finals[3].detail
        assert summary.failed == 0

    def test_get_status_fails(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.side_effect = SwitchtecError("device error")

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert finals[0].criticality == StepCriticality.CRITICAL

    def test_port_not_found(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=7, link_up=True),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert "not found" in finals[0].detail

    def test_link_down_with_transitions_warns(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=False, ltssm_str="Polling.Active"),
        ]
        entries = [
            make_ltssm_entry("Detect.Quiet", "8 GT/s", 4),
            make_ltssm_entry("Polling.Active", "8 GT/s", 4),
            make_ltssm_entry("Polling.Compliance", "8 GT/s", 4),
        ]
        dev.diagnostics.ltssm_log.return_value = entries

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert finals[2].status == StepStatus.WARN  # LTSSM log has transitions
        assert finals[3].status == StepStatus.WARN  # Analyze: likely training failure
        assert "likely training failure" in finals[3].detail

    def test_link_down_no_transitions_passes(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=False, ltssm_str="Detect.Quiet"),
        ]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        assert finals[3].status == StepStatus.PASS
        assert "unused or disconnected" in finals[3].detail

    def test_ltssm_log_fails_warns_and_continues(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, ltssm_str="L0"),
        ]
        dev.diagnostics.ltssm_log.side_effect = SwitchtecError("ltssm read error")

        results, summary = run_recipe(recipe, dev, port_id=0)
        finals = final_results(results)

        # Step 2 warns, step 3 still produces analysis (with 0 transitions)
        assert finals[2].status == StepStatus.WARN
        assert "Could not read LTSSM log" in finals[2].detail
        assert finals[3].status == StepStatus.PASS  # Link is UP
        assert len(finals) == 4

    def test_ltssm_clear_called_before_log(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, ltssm_str="L0"),
        ]
        dev.diagnostics.ltssm_log.return_value = []

        run_recipe(recipe, dev, port_id=0)

        dev.diagnostics.ltssm_clear.assert_called_once_with(0)
        dev.diagnostics.ltssm_log.assert_called_once_with(0)

    def test_cancellation_after_step_1(self):
        recipe = LinkTrainingDebug()
        dev = make_mock_device()
        dev.get_status.return_value = [
            make_port_status(phys_id=0, link_up=True, ltssm_str="L0"),
        ]
        cancel = threading.Event()

        # Cancel after the LTSSM state step (step index 1) RUNNING yield
        call_count = 0
        original_is_set = cancel.is_set

        def cancel_after_step_1():
            nonlocal call_count
            call_count += 1
            # The cancel checks happen at: before step 0 call, before step 1 call,
            # before step 2 call, before step 3 call.
            # We want to cancel before step 2 (the 3rd check).
            if call_count >= 3:
                cancel.set()
            return original_is_set()

        cancel.is_set = cancel_after_step_1

        results, summary = run_recipe(recipe, dev, cancel=cancel, port_id=0)

        assert summary.aborted is True


# ---------------------------------------------------------------------------
# LtssmMonitor
# ---------------------------------------------------------------------------


class TestLtssmMonitor:
    """Tests for the LtssmMonitor recipe."""

    def test_parameters_returns_port_id_and_duration(self):
        recipe = LtssmMonitor()
        params = recipe.parameters()

        assert len(params) == 2
        names = {p.name for p in params}
        assert "port_id" in names
        assert "duration_s" in names

    @patch("serialcables_switchtec.core.workflows.ltssm_monitor.time")
    def test_happy_path_no_transitions(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # step 0 pass summary calc
            0.0,    # monitor_start
            0.5,    # first loop elapsed check
            5.5,    # second loop elapsed check -> remaining <= 0, break
            5.5,    # step 1 result yield
            5.5,    # step 2 RUNNING cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmMonitor()
        dev = make_mock_device()
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(recipe, dev, port_id=0, duration_s=5)
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[0].status == StepStatus.PASS  # Clear
        assert finals[1].status == StepStatus.PASS  # Monitor (0 transitions)
        assert finals[2].status == StepStatus.PASS  # Final analysis
        assert "stable" in finals[2].detail
        assert summary.failed == 0

    @patch("serialcables_switchtec.core.workflows.ltssm_monitor.time")
    def test_clear_fails(self, mock_time):
        mock_time.monotonic.side_effect = [0.0, 0.0]

        recipe = LtssmMonitor()
        dev = make_mock_device()
        dev.diagnostics.ltssm_clear.side_effect = SwitchtecError("clear failed")

        results, summary = run_recipe(recipe, dev, port_id=0, duration_s=5)
        finals = final_results(results)

        assert len(finals) == 1
        assert finals[0].status == StepStatus.FAIL
        assert finals[0].criticality == StepCriticality.CRITICAL
        assert "clear failed" in finals[0].detail

    @patch("serialcables_switchtec.core.workflows.ltssm_monitor.time")
    def test_transitions_detected_warns(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # monitor_start
            0.5,    # first loop elapsed
            5.5,    # second loop elapsed -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmMonitor()
        dev = make_mock_device()
        entries = [
            make_ltssm_entry("Polling.Active", "16 GT/s", 4),
            make_ltssm_entry("L0", "16 GT/s", 4),
        ]
        dev.diagnostics.ltssm_log.return_value = entries

        results, summary = run_recipe(recipe, dev, port_id=0, duration_s=5)
        finals = final_results(results)

        assert finals[1].status == StepStatus.WARN  # Monitor detected transitions
        assert finals[2].status == StepStatus.WARN  # Final analysis
        assert "unstable" in finals[2].detail

    @patch("serialcables_switchtec.core.workflows.ltssm_monitor.time")
    def test_final_log_read_fails_warns(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # monitor_start
            5.5,    # first loop elapsed -> break immediately
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmMonitor()
        dev = make_mock_device()

        # First call during monitor returns [], second call (final) raises
        call_count = 0

        def ltssm_log_side_effect(port_id):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return []
            raise SwitchtecError("final read failed")

        dev.diagnostics.ltssm_log.side_effect = ltssm_log_side_effect

        results, summary = run_recipe(recipe, dev, port_id=0, duration_s=5)
        finals = final_results(results)

        # Find the final analysis step
        final_step = finals[-1]
        assert final_step.status == StepStatus.WARN
        assert "Could not read final LTSSM log" in final_step.detail

    @patch("serialcables_switchtec.core.workflows.ltssm_monitor.time")
    def test_cancellation_during_monitor_loop(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # monitor_start
            0.5,    # first loop elapsed check
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmMonitor()
        dev = make_mock_device()
        dev.diagnostics.ltssm_log.return_value = []
        cancel = threading.Event()

        # Cancel after the first poll iteration's cancel check
        original_is_set = cancel.is_set
        call_count = 0

        def cancel_in_loop():
            nonlocal call_count
            call_count += 1
            # Cancel checks: step 0 RUNNING, step 1 RUNNING, then inside loop
            if call_count >= 3:
                cancel.set()
            return original_is_set()

        cancel.is_set = cancel_in_loop

        results, summary = run_recipe(recipe, dev, cancel=cancel, port_id=0, duration_s=30)

        assert summary.aborted is True


# ---------------------------------------------------------------------------
# LtssmContinuousCapture
# ---------------------------------------------------------------------------


class TestLtssmContinuousCapture:
    """Tests for the LtssmContinuousCapture recipe."""

    def test_parameters_returns_expected(self):
        recipe = LtssmContinuousCapture()
        params = recipe.parameters()
        names = {p.name for p in params}
        assert "port_id" in names
        assert "duration_s" in names
        assert "poll_interval_s" in names
        assert "max_entries" in names

    @patch("serialcables_switchtec.core.workflows.ltssm_continuous.time")
    def test_happy_path_no_transitions(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # poll_start
            5.5,    # first loop -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmContinuousCapture()
        dev = make_mock_device()
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(
            recipe, dev, port_id=0, duration_s=5,
            poll_interval_s=0.5, max_entries=4096,
        )
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[0].status == StepStatus.PASS   # Clear
        assert finals[1].status == StepStatus.PASS   # Capture (0 entries)
        assert finals[2].status == StepStatus.PASS   # Analysis
        assert summary.failed == 0

    @patch("serialcables_switchtec.core.workflows.ltssm_continuous.time")
    def test_cancel_mid_capture(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # poll_start
            0.5,    # first loop elapsed
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmContinuousCapture()
        dev = make_mock_device()
        dev.diagnostics.ltssm_log.return_value = []
        cancel = threading.Event()

        original_is_set = cancel.is_set
        call_count = 0

        def cancel_in_loop():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                cancel.set()
            return original_is_set()

        cancel.is_set = cancel_in_loop

        results, summary = run_recipe(
            recipe, dev, cancel=cancel, port_id=0, duration_s=60,
        )

        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.ltssm_continuous.time")
    def test_wrap_during_capture(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # poll_start
            0.5,    # first loop
            1.0,    # second loop
            5.5,    # third loop -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmContinuousCapture()
        dev = make_mock_device()

        # First poll: entries 100-200, second: wrap to 10-20
        batch1 = [MagicMock(timestamp=100, link_state_str="L0", link_rate="Gen5", link_width=16)]
        batch2 = [MagicMock(timestamp=10, link_state_str="Recovery", link_rate="Gen5", link_width=16)]
        dev.diagnostics.ltssm_log.side_effect = [batch1, batch2, []]

        results, summary = run_recipe(
            recipe, dev, port_id=0, duration_s=5,
        )
        finals = final_results(results)

        capture_step = finals[1]
        assert capture_step.data["wrap_count"] >= 1
        assert capture_step.data["total_entries"] == 2

    @patch("serialcables_switchtec.core.workflows.ltssm_continuous.time")
    def test_final_analysis_integration(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after clear
            0.0,    # poll_start
            0.5,    # first loop
            5.5,    # second loop -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmContinuousCapture()
        dev = make_mock_device()

        entries = [
            MagicMock(timestamp=i, link_state_str="Recovery", link_rate="Gen5", link_width=16)
            for i in range(5)
        ]
        dev.diagnostics.ltssm_log.side_effect = [entries, []]

        results, summary = run_recipe(
            recipe, dev, port_id=0, duration_s=5,
        )
        finals = final_results(results)

        analysis_step = finals[2]
        assert analysis_step.data["ltssm_verdict"] in ("FAIL", "WARN")


# ---------------------------------------------------------------------------
# LtssmEventCapture
# ---------------------------------------------------------------------------


class TestLtssmEventCapture:
    """Tests for the LtssmEventCapture recipe."""

    def test_parameters_returns_expected(self):
        recipe = LtssmEventCapture()
        params = recipe.parameters()
        names = {p.name for p in params}
        assert "port_id" in names
        assert "duration_s" in names
        assert "event_timeout_ms" in names

    @patch("serialcables_switchtec.core.workflows.ltssm_event_capture.time")
    def test_normal_trigger_flow(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after arm
            0.0,    # wait_start
            0.5,    # after first wait_and_capture
            5.5,    # second loop -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmEventCapture()
        dev = make_mock_device()
        dev.events = MagicMock()
        dev.events.event_ctl = MagicMock(return_value=0)

        entries = [
            MagicMock(timestamp=i, link_state_str="L0", link_rate="Gen5", link_width=16)
            for i in range(3)
        ]
        dev.diagnostics.ltssm_log.return_value = entries
        dev.events.wait_for_event = MagicMock(return_value=None)

        results, summary = run_recipe(
            recipe, dev, port_id=0, duration_s=5, event_timeout_ms=5000,
        )
        finals = final_results(results)

        assert len(finals) == 3
        assert finals[0].status == StepStatus.PASS   # Arm
        assert finals[1].status == StepStatus.WARN   # Events captured
        assert finals[1].data["trigger_count"] >= 1

    @patch("serialcables_switchtec.core.workflows.ltssm_event_capture.time")
    def test_timeout_no_events(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after arm
            0.0,    # wait_start
            5.5,    # after first wait -> break
            5.5,    # step 1 result
            5.5,    # step 2 cancel check
            5.5,    # final summary
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmEventCapture()
        dev = make_mock_device()
        dev.events = MagicMock()
        dev.events.event_ctl = MagicMock(return_value=0)
        dev.events.wait_for_event = MagicMock(side_effect=TimeoutError("timeout"))

        results, summary = run_recipe(
            recipe, dev, port_id=0, duration_s=5, event_timeout_ms=5000,
        )
        finals = final_results(results)

        assert finals[1].status == StepStatus.PASS   # No events = stable
        assert finals[1].data["trigger_count"] == 0
        assert finals[2].status == StepStatus.PASS   # No entries = stable

    @patch("serialcables_switchtec.core.workflows.ltssm_event_capture.time")
    def test_cancel_during_wait(self, mock_time):
        mock_time.monotonic.side_effect = [
            0.0,    # start
            0.0,    # after arm
            0.0,    # wait_start
            0.5,    # after first wait
        ]
        mock_time.sleep.return_value = None

        recipe = LtssmEventCapture()
        dev = make_mock_device()
        dev.events = MagicMock()
        dev.events.event_ctl = MagicMock(return_value=0)
        dev.events.wait_for_event = MagicMock(side_effect=TimeoutError("timeout"))

        cancel = threading.Event()
        original_is_set = cancel.is_set
        call_count = 0

        def cancel_in_loop():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                cancel.set()
            return original_is_set()

        cancel.is_set = cancel_in_loop

        results, summary = run_recipe(
            recipe, dev, cancel=cancel, port_id=0, duration_s=120,
        )

        assert summary.aborted is True
