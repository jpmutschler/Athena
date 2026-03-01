"""Tests for ErrorInjectionRecovery and EventCounterBaseline workflow recipes."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.error_injection_recovery import (
    ErrorInjectionRecovery,
)
from serialcables_switchtec.core.workflows.event_counter_baseline import (
    EventCounterBaseline,
)
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError

from tests.unit.test_workflows_helpers import (
    final_results,
    make_mock_device,
    make_port_status,
    run_recipe,
)


# ---------------------------------------------------------------------------
# ErrorInjectionRecovery
# ---------------------------------------------------------------------------


class TestErrorInjectionRecovery:
    """Tests for the ErrorInjectionRecovery recipe."""

    def test_parameters(self):
        recipe = ErrorInjectionRecovery()
        params = recipe.parameters()

        names = [p.name for p in params]
        assert "port_id" in names
        assert "injection_type" in names
        assert "verify_duration_s" in names

        inj_param = next(p for p in params if p.name == "injection_type")
        assert inj_param.param_type == "select"
        assert set(inj_param.choices) == {
            "dllp_crc", "tlp_lcrc", "tlp_seq_num", "cto",
        }

        assert recipe.category == RecipeCategory.ERROR_TESTING

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_happy_path(self, mock_time):
        """Link up, injection succeeds, link stays up, 0 LTSSM transitions."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 4

        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Inject error"
        assert final[1].status == StepStatus.PASS

        assert final[2].step == "Monitor recovery"
        assert final[2].status == StepStatus.PASS
        assert final[2].data["link_went_down"] is False

        assert final[3].step == "Check LTSSM"
        assert final[3].status == StepStatus.PASS
        assert final[3].data["transition_count"] == 0

        assert summary.passed == 4
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_get_status_fails(self, mock_time):
        """get_status raises SwitchtecError -> FAIL step 0, early exit."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(return_value=0.0)
        mock_time.sleep = MagicMock()

        dev.get_status.side_effect = SwitchtecError("device error")

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_port_not_found(self, mock_time):
        """Port not in status list -> FAIL step 0."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(return_value=0.0)
        mock_time.sleep = MagicMock()

        # Return a port with a different phys_id
        port = make_port_status(phys_id=5, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].status == StepStatus.FAIL
        assert "not found" in final[0].detail

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_port_link_down(self, mock_time):
        """Port found but link is DOWN -> FAIL step 0."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(return_value=0.0)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=False)
        dev.get_status.return_value = [port]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].status == StepStatus.FAIL
        assert "DOWN" in final[0].detail

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_injection_fails(self, mock_time):
        """Injection raises SwitchtecError -> FAIL step 1."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        dev.injector.inject_dllp_crc.side_effect = SwitchtecError("inject failed")

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 2
        assert final[0].status == StepStatus.PASS  # verify link
        assert final[1].step == "Inject error"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_link_down_recovers(self, mock_time):
        """Link goes down then recovers -> WARN on monitor and LTSSM steps."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        # Track get_status calls to control time: after the monitor loop
        # sees down then up, jump time forward to exit the loop.
        status_call = {"n": 0}
        time_jump = {"jumped": False}

        port_up = make_port_status(phys_id=0, link_up=True)
        port_down = make_port_status(phys_id=0, link_up=False)

        status_sequence = [
            [port_up],    # step 0: verify link
            [port_down],  # monitor poll 1: link went down
            [port_up],    # monitor poll 2: link recovered
            [port_up],    # step 3: final link check
        ]

        def get_status_side_effect():
            idx = min(status_call["n"], len(status_sequence) - 1)
            result = status_sequence[idx]
            status_call["n"] += 1
            # After 3 calls (verify + 2 polls), trigger time jump
            if status_call["n"] >= 3:
                time_jump["jumped"] = True
            return result

        dev.get_status = MagicMock(side_effect=lambda: get_status_side_effect())

        call_count = {"n": 0}

        def controlled_monotonic():
            call_count["n"] += 1
            if time_jump["jumped"]:
                return 1000.0
            return float(call_count["n"]) * 0.01

        mock_time.monotonic = MagicMock(side_effect=controlled_monotonic)
        mock_time.sleep = MagicMock()

        # Some LTSSM transitions occurred
        dev.diagnostics.ltssm_log.return_value = [MagicMock(), MagicMock()]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 4

        # Monitor: link went down but recovered -> WARN
        assert final[2].step == "Monitor recovery"
        assert final[2].status == StepStatus.WARN
        assert final[2].data["link_went_down"] is True
        assert final[2].data["link_recovered"] is True

        # LTSSM: link up final, link_recovered, transitions > 0 -> WARN
        assert final[3].step == "Check LTSSM"
        assert final[3].status == StepStatus.WARN
        assert final[3].data["transition_count"] == 2

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_link_down_no_recovery(self, mock_time):
        """Link goes down and stays down -> FAIL steps 2 and 3."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        # Track get_status calls to control time jump after monitor poll
        status_call = {"n": 0}
        time_jump = {"jumped": False}

        port_up = make_port_status(phys_id=0, link_up=True)
        port_down = make_port_status(phys_id=0, link_up=False)

        def get_status_side_effect():
            status_call["n"] += 1
            if status_call["n"] == 1:
                return [port_up]     # step 0: verify link
            # After first monitor poll, trigger time jump
            time_jump["jumped"] = True
            return [port_down]       # monitor + final: always down

        dev.get_status = MagicMock(side_effect=lambda: get_status_side_effect())

        call_count = {"n": 0}

        def controlled_monotonic():
            call_count["n"] += 1
            if time_jump["jumped"]:
                return 1000.0
            return float(call_count["n"]) * 0.01

        mock_time.monotonic = MagicMock(side_effect=controlled_monotonic)
        mock_time.sleep = MagicMock()

        dev.diagnostics.ltssm_log.return_value = [MagicMock()]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )
        final = final_results(results)

        assert len(final) == 4

        # Monitor: link went down, not recovered -> FAIL
        assert final[2].step == "Monitor recovery"
        assert final[2].status == StepStatus.FAIL

        # LTSSM: final_up=False -> FAIL
        assert final[3].step == "Check LTSSM"
        assert final[3].status == StepStatus.FAIL
        assert "still down" in final[3].detail

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_cancellation_after_injection(self, mock_time):
        """Cancel set after injection -> cleanup called, aborted=True."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 0.01)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        cancel = threading.Event()

        # Set cancel during injection (ltssm_clear is called at the start
        # of step 1, before the actual injection). The cancel check happens
        # after step 1 yields its result.
        def set_cancel_on_inject(*args, **kwargs):
            cancel.set()

        dev.injector.inject_dllp_crc.side_effect = set_cancel_on_inject

        results, summary = run_recipe(
            recipe, dev, cancel=cancel,
            port_id=0, injection_type="dllp_crc", verify_duration_s=5,
        )

        assert summary.aborted is True

        # Cleanup: _disable_injection should have been called
        # For dllp_crc, the cancel-path calls inject_dllp_crc(port_id, False, 0)
        disable_calls = [
            c for c in dev.injector.inject_dllp_crc.call_args_list
            if c[0] == (0, False, 0)
        ]
        assert len(disable_calls) >= 1

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_injection_type_tlp_lcrc(self, mock_time):
        """tlp_lcrc injection type calls correct injector method."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=2, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(
            recipe, dev,
            port_id=2, injection_type="tlp_lcrc", verify_duration_s=1,
        )
        final = final_results(results)

        assert final[1].status == StepStatus.PASS
        dev.injector.inject_tlp_lcrc.assert_any_call(2, True, 1)
        dev.injector.inject_tlp_lcrc.assert_any_call(2, False, 0)

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_injection_type_tlp_seq_num(self, mock_time):
        """tlp_seq_num injection type calls correct injector method."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=3, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(
            recipe, dev,
            port_id=3, injection_type="tlp_seq_num", verify_duration_s=1,
        )
        final = final_results(results)

        assert final[1].status == StepStatus.PASS
        dev.injector.inject_tlp_seq_num.assert_called_with(3)

    @patch("serialcables_switchtec.core.workflows.error_injection_recovery.time")
    def test_injection_type_cto(self, mock_time):
        """cto injection type calls correct injector method."""
        recipe = ErrorInjectionRecovery()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=4, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.ltssm_log.return_value = []

        results, summary = run_recipe(
            recipe, dev,
            port_id=4, injection_type="cto", verify_duration_s=1,
        )
        final = final_results(results)

        assert final[1].status == StepStatus.PASS
        dev.injector.inject_cto.assert_called_with(4)


# ---------------------------------------------------------------------------
# EventCounterBaseline
# ---------------------------------------------------------------------------


class TestEventCounterBaseline:
    """Tests for the EventCounterBaseline recipe."""

    def test_parameters(self):
        recipe = EventCounterBaseline()
        params = recipe.parameters()

        names = [p.name for p in params]
        assert "stack_id" in names
        assert "counter_id" in names
        assert "port_mask" in names
        assert "type_mask" in names
        assert "duration_s" in names

        assert recipe.category == RecipeCategory.PERFORMANCE

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_happy_path(self, mock_time):
        """Configure succeeds, baseline read, 0 events during soak -> all PASS."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.evcntr.setup = MagicMock()
        dev.evcntr.get_counts = MagicMock(return_value=[0])

        results, summary = run_recipe(
            recipe, dev,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=30,
        )
        final = final_results(results)

        assert len(final) == 4

        assert final[0].step == "Configure counter"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Read baseline"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["baseline"] == 0

        assert final[2].step == "Soak"
        assert final[2].status == StepStatus.PASS
        assert final[2].data["total_events"] == 0

        assert final[3].step == "Report"
        assert final[3].status == StepStatus.PASS
        assert final[3].data["total_events"] == 0
        assert final[3].data["events_per_second"] == 0

        assert summary.passed == 4
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_setup_fails(self, mock_time):
        """Setup raises SwitchtecError -> FAIL step 0, early exit."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(return_value=0.0)
        mock_time.sleep = MagicMock()

        dev.evcntr.setup.side_effect = SwitchtecError("setup failed")

        results, summary = run_recipe(
            recipe, dev,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=30,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Configure counter"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_get_counts_fails_for_baseline(self, mock_time):
        """get_counts raises SwitchtecError on baseline read -> FAIL step 1."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(return_value=0.0)
        mock_time.sleep = MagicMock()

        dev.evcntr.setup = MagicMock()
        dev.evcntr.get_counts.side_effect = SwitchtecError("read failed")

        results, summary = run_recipe(
            recipe, dev,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=30,
        )
        final = final_results(results)

        assert len(final) == 2
        assert final[0].step == "Configure counter"
        assert final[0].status == StepStatus.PASS
        assert final[1].step == "Read baseline"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_events_detected_during_soak(self, mock_time):
        """Events accumulated during soak -> WARN on Report step."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        # Track get_counts calls: after soak poll returns events, jump time
        counts_call = {"n": 0}
        time_jump = {"jumped": False}

        def get_counts_side_effect(*args, **kwargs):
            counts_call["n"] += 1
            if counts_call["n"] == 1:
                return [0]   # baseline read
            # Soak poll: return events and trigger time jump
            time_jump["jumped"] = True
            return [42]

        dev.evcntr.setup = MagicMock()
        dev.evcntr.get_counts = MagicMock(side_effect=get_counts_side_effect)

        call_count = {"n": 0}

        def controlled_monotonic():
            call_count["n"] += 1
            if time_jump["jumped"]:
                return 1000.0
            return float(call_count["n"]) * 0.01

        mock_time.monotonic = MagicMock(side_effect=controlled_monotonic)
        mock_time.sleep = MagicMock()

        results, summary = run_recipe(
            recipe, dev,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=30,
        )
        final = final_results(results)

        assert len(final) == 4

        assert final[2].step == "Soak"
        assert final[2].data["total_events"] == 42

        assert final[3].step == "Report"
        assert final[3].status == StepStatus.WARN
        assert final[3].data["total_events"] == 42
        assert "unexpected activity" in final[3].detail

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_cancellation_during_soak(self, mock_time):
        """Cancel during soak -> aborted=True in summary."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        # Time: advance through setup steps, then one soak iteration
        monotonic_values = iter([
            0.0,   # start
            0.1,   # step 0 RUNNING
            0.2,   # cancel check
            0.3,   # step 0 PASS
            0.4,   # cancel check
            0.5,   # step 1 RUNNING
            0.6,   # baseline
            0.7,   # step 1 PASS
            0.8,   # cancel check
            0.9,   # step 2 RUNNING
            1.0,   # poll_start
            # First iteration: 1.1 - 1.0 = 0.1 < 30 -> enter loop
            1.1,   # while condition
            # cancel is set inside loop -> break
            1.2,   # actual_duration calc
            1.3,   # step 2 result
            1.4,   # cancel check -> set, return aborted summary
            1.5,   # summary
        ])
        mock_time.monotonic = MagicMock(side_effect=monotonic_values)
        mock_time.sleep = MagicMock()

        dev.evcntr.setup = MagicMock()
        dev.evcntr.get_counts = MagicMock(return_value=[0])

        cancel = threading.Event()

        # Use a side_effect on get_counts during soak to set cancel
        call_number = {"n": 0}

        def get_counts_then_cancel(*args, **kwargs):
            call_number["n"] += 1
            if call_number["n"] == 1:
                # Baseline read
                return [0]
            # Soak poll: set cancel before returning
            cancel.set()
            return [0]

        dev.evcntr.get_counts = MagicMock(side_effect=get_counts_then_cancel)

        results, summary = run_recipe(
            recipe, dev, cancel=cancel,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=30,
        )

        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.event_counter_baseline.time")
    def test_step_count_consistency(self, mock_time):
        """All emitted results report correct total_steps."""
        recipe = EventCounterBaseline()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.evcntr.setup = MagicMock()
        dev.evcntr.get_counts = MagicMock(return_value=[0])

        results, summary = run_recipe(
            recipe, dev,
            stack_id=0, counter_id=0,
            port_mask=0xFFFFFFFF, type_mask=0xFFFFFFFF,
            duration_s=5,
        )

        # Every result (including RUNNING) should have total_steps == 4
        for r in results:
            assert r.total_steps == 4
