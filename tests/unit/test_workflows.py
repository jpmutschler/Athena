"""Tests for workflow recipes: AllPortSweep, BerSoak, LoopbackSweep."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.all_port_sweep import AllPortSweep
from serialcables_switchtec.core.workflows.ber_soak import BerSoak
from serialcables_switchtec.core.workflows.loopback_sweep import LoopbackSweep
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_recipe(recipe, dev, cancel=None, **kwargs):
    """Drive a recipe generator to completion, returning (results, summary).

    Collects all yielded RecipeResult objects and the RecipeSummary returned
    via StopIteration.value.
    """
    if cancel is None:
        cancel = threading.Event()
    gen = recipe.run(dev, cancel, **kwargs)
    results: list[RecipeResult] = []
    summary: RecipeSummary | None = None
    try:
        while True:
            result = next(gen)
            results.append(result)
    except StopIteration as stop:
        summary = stop.value
    return results, summary


def _final_results(results):
    """Filter out RUNNING status results, keeping only terminal step states."""
    return [r for r in results if r.status != StepStatus.RUNNING]


def _make_port_status(phys_id=0, link_up=True, link_rate="16 GT/s", neg_lnk_width=4):
    """Create a mock PortStatus object."""
    ps = MagicMock()
    ps.port.phys_id = phys_id
    ps.link_up = link_up
    ps.link_rate = link_rate
    ps.neg_lnk_width = neg_lnk_width
    ps.neg_link_width = neg_lnk_width
    return ps


def _make_device_summary(die_temperature=42.5):
    """Create a mock DeviceSummary returned by dev.identify()."""
    summary = MagicMock()
    summary.die_temperature = die_temperature
    return summary


def _make_pattern_mon_result(error_count=0):
    """Create a mock PatternMonResult."""
    mon = MagicMock()
    mon.error_count = error_count
    return mon


def _make_mock_device():
    """Create a MagicMock device with diagnostics sub-mock wired up."""
    dev = MagicMock()
    dev.get_status = MagicMock(return_value=[])
    dev.identify = MagicMock(return_value=_make_device_summary())
    dev.diagnostics = MagicMock()
    dev.diagnostics.pattern_gen_set = MagicMock()
    dev.diagnostics.pattern_mon_set = MagicMock()
    dev.diagnostics.pattern_mon_get = MagicMock(
        return_value=_make_pattern_mon_result(error_count=0),
    )
    dev.diagnostics.ltssm_log = MagicMock(return_value=[])
    dev.diagnostics.loopback_set = MagicMock()
    return dev


# ---------------------------------------------------------------------------
# AllPortSweep
# ---------------------------------------------------------------------------


class TestAllPortSweep:
    """Tests for the AllPortSweep recipe."""

    def test_parameters(self):
        recipe = AllPortSweep()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) == 0

    def test_metadata(self):
        recipe = AllPortSweep()

        assert recipe.name == "All-Port Status Sweep"
        assert recipe.category == RecipeCategory.LINK_HEALTH

    def test_estimated_duration_s(self):
        recipe = AllPortSweep()

        assert recipe.estimated_duration_s() == 3.0
        # kwargs are ignored since there are no parameters
        assert recipe.estimated_duration_s(any_param=99) == 3.0

    def test_run_happy_path(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        port0 = _make_port_status(phys_id=0, link_up=True)
        port1 = _make_port_status(phys_id=1, link_up=False)
        dev.get_status.return_value = [port0, port1]
        dev.identify.return_value = _make_device_summary(55.0)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        # Three terminal steps: enumerate, per-port, temperature
        assert len(final) == 3
        assert all(r.recipe_name == "All-Port Status Sweep" for r in final)

        # Step 1: enumerate ports - PASS
        assert final[0].step == "Enumerating ports"
        assert final[0].status == StepStatus.PASS
        assert "2 ports" in final[0].detail
        assert "1 UP" in final[0].detail
        assert final[0].data["total"] == 2
        assert final[0].data["up"] == 1
        assert final[0].data["down"] == 1

        # Step 2: per-port status - PASS
        assert final[1].step == "Per-port status"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["ports"] is not None
        assert len(final[1].data["ports"]) == 2

        # Step 3: temperature - PASS (55 < 100)
        assert final[2].step == "Die temperature"
        assert final[2].status == StepStatus.PASS
        assert "55.0" in final[2].detail

        # Summary
        assert summary is not None
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.skipped == 0
        assert summary.aborted is False

    def test_run_high_temperature_warns(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        dev.get_status.return_value = [_make_port_status()]
        dev.identify.return_value = _make_device_summary(105.0)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        temp_result = final[2]
        assert temp_result.step == "Die temperature"
        assert temp_result.status == StepStatus.WARN
        assert "105.0" in temp_result.detail

        assert summary.warnings == 1

    def test_run_temperature_error_warns(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        dev.get_status.return_value = [_make_port_status()]
        dev.identify.side_effect = SwitchtecError("temp read fail", -1)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        temp_result = final[2]
        assert temp_result.step == "Die temperature"
        assert temp_result.status == StepStatus.WARN
        assert "Could not read temperature" in temp_result.detail

        assert summary.warnings == 1
        assert summary.failed == 0

    def test_run_cancel_before_enumerate(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        cancel = threading.Event()
        cancel.set()

        results, summary = _run_recipe(recipe, dev, cancel)

        # The SKIP result is appended internally but not yielded,
        # so we check the summary's results list instead.
        assert summary.aborted is True
        assert summary.skipped == 1
        skip_results = [r for r in summary.results if r.status == StepStatus.SKIP]
        assert len(skip_results) == 1
        assert "Cancelled" in skip_results[0].detail

    def test_run_cancel_after_enumerate(self):
        recipe = AllPortSweep()
        cancel = threading.Event()
        dev = _make_mock_device()

        # Set cancel after get_status returns
        def set_cancel_on_get_status():
            cancel.set()
            return [_make_port_status()]

        dev.get_status.side_effect = set_cancel_on_get_status

        results, summary = _run_recipe(recipe, dev, cancel)

        # Enumerate passes (yielded), per-port gets skipped (internal only)
        yielded_final = _final_results(results)
        assert yielded_final[0].step == "Enumerating ports"
        assert yielded_final[0].status == StepStatus.PASS

        # The SKIP result is in summary.results but not yielded
        assert summary.aborted is True
        skip_results = [r for r in summary.results if r.status == StepStatus.SKIP]
        assert len(skip_results) == 1
        assert skip_results[0].step == "Per-port status"

    def test_run_cancel_after_per_port(self):
        recipe = AllPortSweep()
        cancel = threading.Event()
        dev = _make_mock_device()
        dev.get_status.return_value = [_make_port_status()]

        # Drive the generator manually so we can set cancel at the right time
        gen = recipe.run(dev, cancel)
        collected = []
        try:
            while True:
                r = next(gen)
                collected.append(r)
                # After we get the per-port status PASS result, set cancel
                if r.step == "Per-port status" and r.status == StepStatus.PASS:
                    cancel.set()
        except StopIteration as stop:
            summary = stop.value

        # Die temperature SKIP is internal (not yielded), check summary
        assert summary.aborted is True
        skip_results = [r for r in summary.results if r.status == StepStatus.SKIP]
        assert len(skip_results) == 1
        assert skip_results[0].step == "Die temperature"

    def test_run_hardware_error(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        dev.get_status.side_effect = SwitchtecError("hw fail", -1)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        assert len(final) == 1
        assert final[0].step == "Enumerating ports"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "hw fail" in final[0].detail

        assert summary.failed == 1
        assert summary.passed == 0
        assert summary.aborted is False

    def test_summary_counts(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        dev.get_status.return_value = [_make_port_status()]
        dev.identify.return_value = _make_device_summary(42.0)

        _, summary = _run_recipe(recipe, dev)

        assert summary.recipe_name == "All-Port Status Sweep"
        assert summary.total_steps == 3
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.skipped == 0
        assert summary.elapsed_s >= 0

    def test_all_ports_down(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        ports = [
            _make_port_status(phys_id=0, link_up=False),
            _make_port_status(phys_id=1, link_up=False),
        ]
        dev.get_status.return_value = ports
        dev.identify.return_value = _make_device_summary(30.0)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        assert final[0].data["up"] == 0
        assert final[0].data["down"] == 2
        assert "0 UP" in final[0].detail

    def test_empty_port_list(self):
        recipe = AllPortSweep()
        dev = _make_mock_device()
        dev.get_status.return_value = []
        dev.identify.return_value = _make_device_summary(42.0)

        results, summary = _run_recipe(recipe, dev)
        final = _final_results(results)

        assert final[0].data["total"] == 0
        assert "0 ports" in final[0].detail
        assert summary.passed == 3


# ---------------------------------------------------------------------------
# BerSoak
# ---------------------------------------------------------------------------


class TestBerSoak:
    """Tests for the BerSoak recipe."""

    def test_parameters(self):
        recipe = BerSoak()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) == 5

        names = [p.name for p in params]
        assert "port_id" in names
        assert "pattern" in names
        assert "link_speed" in names
        assert "duration_s" in names
        assert "lane_count" in names

        # Verify parameter types
        param_map = {p.name: p for p in params}
        assert param_map["port_id"].param_type == "int"
        assert param_map["link_speed"].param_type == "select"
        assert param_map["link_speed"].choices == [
            "GEN1", "GEN2", "GEN3", "GEN4", "GEN5", "GEN6",
        ]

    def test_metadata(self):
        recipe = BerSoak()

        assert recipe.name == "BER Soak Test"
        assert recipe.category == RecipeCategory.ERROR_TESTING

    def test_estimated_duration_s(self):
        recipe = BerSoak()

        # Default duration is 60, so estimated = 60 + 5 = 65
        assert recipe.estimated_duration_s() == 65.0
        assert recipe.estimated_duration_s(duration_s=10) == 15.0
        assert recipe.estimated_duration_s(duration_s=3600) == 3605.0

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_happy_path(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        # Make time.monotonic() advance so the soak loop terminates quickly
        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=2,
        )
        final = _final_results(results)

        # 6 steps: verify link, patgen set, patmon set, soak, ltssm, cleanup
        assert len(final) == 6

        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Configure pattern generator"
        assert final[1].status == StepStatus.PASS

        assert final[2].step == "Configure pattern monitor"
        assert final[2].status == StepStatus.PASS

        assert final[3].step == "BER soak"
        assert final[3].status == StepStatus.PASS
        assert final[3].data["total_errors"] == 0

        assert final[4].step == "Check LTSSM"
        assert final[4].status == StepStatus.PASS
        assert final[4].data["transition_count"] == 0

        assert final[5].step == "Cleanup"
        assert final[5].status == StepStatus.PASS

        assert summary.passed == 6
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_with_errors_warns(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        # We need the soak loop to execute at least one poll iteration.
        # The loop condition is: time.monotonic() - soak_start < duration_s
        # We use a sequence where soak_start is low, the first loop check
        # passes, the in-loop check fails (exits loop).
        monotonic_sequence = iter([
            0.0,    # start = time.monotonic()
            # Step 1: verify link
            0.1,    # yield RUNNING
            0.2,    # result yield
            # Step 2: configure patgen
            0.3,    # yield RUNNING
            0.4,    # result yield
            # Step 3: configure patmon
            0.5,    # yield RUNNING
            0.6,    # result yield
            # Step 4: soak
            0.7,    # yield RUNNING
            # Baseline reads: 2 lanes
            0.8,    # baseline lane 0 mon_get
            0.9,    # baseline lane 1 mon_get
            1.0,    # soak_start = time.monotonic()
            # First loop iteration: condition check passes (1.1 - 1.0 = 0.1 < 5)
            1.1,    # while condition check
            # Poll lanes
            1.2,    # lane 0 mon_get
            1.3,    # lane 1 mon_get
            # sleep calc: duration_s - (time.monotonic() - soak_start)
            1.4,    # time calc for sleep
            # Second loop: condition fails (100 - 1.0 = 99 > 5)
            100.0,  # while condition -> exit
            # soak result
            100.1,  # summary calc
            # Step 5: LTSSM
            100.2,
            100.3,
            # Step 6: cleanup
            100.4,
            100.5,
            # final summary
            100.6,
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_sequence, 999.0))
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Baseline returns 0, soak poll returns 5 errors per lane
        mon_call_count = {"n": 0}

        def mon_get_side_effect(port_id, lane):
            mon_call_count["n"] += 1
            # First 2 calls are baseline (lane_count=2), subsequent are in soak poll
            if mon_call_count["n"] <= 2:
                return _make_pattern_mon_result(error_count=0)
            return _make_pattern_mon_result(error_count=5)

        dev.diagnostics.pattern_mon_get = MagicMock(side_effect=mon_get_side_effect)
        dev.diagnostics.ltssm_log.return_value = ["retrain1"]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=5, lane_count=2,
        )
        final = _final_results(results)

        # Soak step should WARN because errors > 0
        soak_result = [r for r in final if r.step == "BER soak"][0]
        assert soak_result.status == StepStatus.WARN
        assert soak_result.data["total_errors"] == 10  # 5 per lane * 2 lanes

        # LTSSM should WARN because transitions > 0
        ltssm_result = [r for r in final if r.step == "Check LTSSM"][0]
        assert ltssm_result.status == StepStatus.WARN

        assert summary.warnings == 2

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_link_down_warns(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # Port phys_id=5 but we query port_id=0 -> no match -> link DOWN
        port = _make_port_status(phys_id=5, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.WARN
        assert "DOWN" in final[0].detail

    def test_run_hardware_error_on_get_status(self):
        recipe = BerSoak()
        dev = _make_mock_device()
        dev.get_status.side_effect = SwitchtecError("hw fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert len(final) == 1
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "hw fail" in final[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_hardware_error_on_patgen(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.pattern_gen_set.side_effect = SwitchtecError("patgen fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        # Verify link passes, then patgen fails and recipe exits
        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.PASS
        assert final[1].step == "Configure pattern generator"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1
        assert summary.passed == 1

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_hardware_error_on_patmon_set(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.pattern_mon_set.side_effect = SwitchtecError("patmon fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert final[2].step == "Configure pattern monitor"
        assert final[2].status == StepStatus.FAIL
        assert final[2].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_cancel_early(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # Cancel right after link check
        def get_status_and_cancel():
            cancel.set()
            return [_make_port_status(phys_id=0, link_up=True)]

        dev.get_status.side_effect = get_status_and_cancel

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        # Only "Verify link up" should complete before abort
        assert final[0].step == "Verify link up"
        assert final[0].status == StepStatus.PASS
        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_cancel_during_soak(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()
        cancel = threading.Event()

        monotonic_vals = iter([
            0.0,    # start
            0.0,    # step 1 RUNNING yield -> _make_result
            0.1,    # after get_status check
            0.2,    # verify link PASS -> _make_result
            0.3,    # cancel check after step 1
            0.4,    # step 2 RUNNING yield
            0.5,    # patgen PASS -> _make_result
            0.6,    # cancel check after step 2
            0.7,    # step 3 RUNNING yield
            0.8,    # patmon PASS -> _make_result
            0.9,    # cancel check after step 3
            1.0,    # step 4 RUNNING yield (soak)
            1.1,    # baseline mon_get
            1.2,    # soak_start
            1.3,    # soak loop condition check
            1.4,    # soak loop mon_get
            1.5,    # sleep duration calc
            999.0,  # after cancel, time jumps
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))

        # Set cancel when sleep is called (during soak poll)
        def cancel_on_sleep(duration):
            cancel.set()

        mock_time.sleep = MagicMock(side_effect=cancel_on_sleep)

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=5, lane_count=1,
        )

        assert summary.aborted is True
        # Cleanup should have been called (patgen disabled)
        dev.diagnostics.pattern_gen_set.assert_called()

    def test_cleanup(self):
        recipe = BerSoak()
        dev = _make_mock_device()

        recipe.cleanup(dev, port_id=0, link_speed="GEN4")

        dev.diagnostics.pattern_gen_set.assert_called_once()

    def test_cleanup_gen5(self):
        recipe = BerSoak()
        dev = _make_mock_device()

        recipe.cleanup(dev, port_id=2, link_speed="GEN5")

        dev.diagnostics.pattern_gen_set.assert_called_once()
        call_args = dev.diagnostics.pattern_gen_set.call_args
        from serialcables_switchtec.bindings.constants import (
            DiagPatternGen5,
            DiagPatternLinkRate,
        )
        assert call_args[0][1] == DiagPatternGen5.DISABLED
        assert call_args[0][2] == DiagPatternLinkRate.DISABLED

    def test_cleanup_gen6(self):
        recipe = BerSoak()
        dev = _make_mock_device()

        recipe.cleanup(dev, port_id=3, link_speed="GEN6")

        dev.diagnostics.pattern_gen_set.assert_called_once()
        call_args = dev.diagnostics.pattern_gen_set.call_args
        from serialcables_switchtec.bindings.constants import (
            DiagPatternGen6,
            DiagPatternLinkRate,
        )
        assert call_args[0][1] == DiagPatternGen6.DISABLED
        assert call_args[0][2] == DiagPatternLinkRate.DISABLED

    def test_cleanup_swallows_error(self):
        recipe = BerSoak()
        dev = _make_mock_device()
        dev.diagnostics.pattern_gen_set.side_effect = SwitchtecError("cleanup fail", -1)

        # Should not raise
        recipe.cleanup(dev, port_id=0, link_speed="GEN4")

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_summary_counts(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        _, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )

        assert summary.recipe_name == "BER Soak Test"
        assert summary.total_steps == 6
        assert summary.passed == 6
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.skipped == 0
        assert summary.elapsed_s >= 0

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_ltssm_read_error_warns(self, mock_time):
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.ltssm_log.side_effect = SwitchtecError("ltssm fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        ltssm_result = [r for r in final if r.step == "Check LTSSM"][0]
        assert ltssm_result.status == StepStatus.WARN
        assert "Could not read LTSSM" in ltssm_result.detail

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_cleanup_step_error_warns(self, mock_time):
        """When the final cleanup step's pattern_gen_set fails, it should WARN."""
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # pattern_gen_set: first call (configure) works, second call (cleanup) fails
        patgen_calls = {"n": 0}

        def patgen_side_effect(*args, **kwargs):
            patgen_calls["n"] += 1
            if patgen_calls["n"] > 1:
                raise SwitchtecError("cleanup patgen fail", -1)

        dev.diagnostics.pattern_gen_set = MagicMock(side_effect=patgen_side_effect)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )
        final = _final_results(results)

        cleanup_result = [r for r in final if r.step == "Cleanup"][0]
        assert cleanup_result.status == StepStatus.WARN
        assert "Cleanup warning" in cleanup_result.detail

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_cancel_after_patgen(self, mock_time):
        """Cancel between step 2 (patgen) and step 3 (patmon)."""
        recipe = BerSoak()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Cancel after pattern_gen_set succeeds
        def patgen_and_cancel(*args, **kwargs):
            cancel.set()

        dev.diagnostics.pattern_gen_set = MagicMock(side_effect=patgen_and_cancel)

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )

        assert summary.aborted is True
        # Should have completed verify link + patgen, then aborted
        assert summary.passed == 2
        # Cleanup should have been called
        dev.diagnostics.pattern_gen_set.assert_called()

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_cancel_after_patmon(self, mock_time):
        """Cancel between step 3 (patmon) and step 4 (soak)."""
        recipe = BerSoak()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Cancel after pattern_mon_set succeeds
        def patmon_and_cancel(*args, **kwargs):
            cancel.set()

        dev.diagnostics.pattern_mon_set = MagicMock(side_effect=patmon_and_cancel)

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=1,
        )

        assert summary.aborted is True
        assert summary.passed == 3  # verify + patgen + patmon

    @patch("serialcables_switchtec.core.workflows.ber_soak.time")
    def test_run_baseline_mon_get_error(self, mock_time):
        """SwitchtecError during baseline mon_get defaults to 0."""
        recipe = BerSoak()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # pattern_mon_get always raises -- baseline defaults to 0, soak poll silently fails
        dev.diagnostics.pattern_mon_get = MagicMock(
            side_effect=SwitchtecError("mon read fail", -1),
        )

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, pattern=3, link_speed="GEN4",
            duration_s=1, lane_count=2,
        )
        final = _final_results(results)

        soak_result = [r for r in final if r.step == "BER soak"][0]
        # With all reads failing, total_errors = 0 (no final - no baseline)
        assert soak_result.status == StepStatus.PASS
        assert soak_result.data["total_errors"] == 0


# ---------------------------------------------------------------------------
# LoopbackSweep
# ---------------------------------------------------------------------------


class TestLoopbackSweep:
    """Tests for the LoopbackSweep recipe."""

    def test_parameters(self):
        recipe = LoopbackSweep()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) == 4

        names = [p.name for p in params]
        assert "port_id" in names
        assert "gen" in names
        assert "duration_per_pattern_s" in names
        assert "lane_count" in names

        param_map = {p.name: p for p in params}
        assert param_map["gen"].param_type == "select"
        assert param_map["gen"].choices == ["gen3", "gen4", "gen5", "gen6"]
        assert param_map["duration_per_pattern_s"].default == 10

    def test_metadata(self):
        recipe = LoopbackSweep()

        assert recipe.name == "Loopback BER Sweep"
        assert recipe.category == RecipeCategory.ERROR_TESTING

    def test_estimated_duration_s(self):
        recipe = LoopbackSweep()

        # gen4 has 6 patterns, default dur=10 -> 6*10 + 10 = 70
        assert recipe.estimated_duration_s() == 70.0
        assert recipe.estimated_duration_s(gen="gen4") == 70.0

        # gen5 has 8 patterns -> 8*10 + 10 = 90
        assert recipe.estimated_duration_s(gen="gen5") == 90.0

        # gen6 has 7 patterns -> 7*10 + 10 = 80
        assert recipe.estimated_duration_s(gen="gen6") == 80.0

        # gen3 has 6 patterns, custom duration -> 6*5 + 10 = 40
        assert recipe.estimated_duration_s(gen="gen3", duration_per_pattern_s=5) == 40.0

    def test_estimated_duration_s_unknown_gen(self):
        recipe = LoopbackSweep()

        # Unknown gen has 0 patterns -> 0 * dur + 10 = 10
        assert recipe.estimated_duration_s(gen="gen99") == 10.0

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_happy_path(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        # gen4: 6 patterns + verify link + enable loopback + disable loopback = 9 steps
        assert final[0].step == "Verify link"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Enable loopback"
        assert final[1].status == StepStatus.PASS

        # 6 pattern steps
        pattern_results = final[2:-1]
        assert len(pattern_results) == 6
        for pr in pattern_results:
            assert pr.status == StepStatus.PASS
            assert pr.data["errors"] == 0

        # Disable loopback step
        assert final[-1].step == "Disable loopback"
        assert final[-1].status == StepStatus.PASS

        assert summary.passed == 9
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_with_errors_warns(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Alternate: baseline returns 0, final returns 10 errors
        mon_calls = {"n": 0}

        def mon_get_side_effect(port_id, lane):
            mon_calls["n"] += 1
            # Each pattern reads baseline (1 call), then final (1 call) for 1 lane
            # Odd calls = baseline (0), Even calls = final (10)
            if mon_calls["n"] % 2 == 1:
                return _make_pattern_mon_result(error_count=0)
            return _make_pattern_mon_result(error_count=10)

        dev.diagnostics.pattern_mon_get = MagicMock(side_effect=mon_get_side_effect)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        pattern_results = [r for r in final if r.step.startswith("Pattern ")]
        for pr in pattern_results:
            assert pr.status == StepStatus.WARN
            assert pr.data["errors"] == 10

        assert summary.warnings == 6  # All 6 patterns warn

    def test_run_hardware_error_on_get_status(self):
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        dev.get_status.side_effect = SwitchtecError("hw fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert len(final) == 1
        assert final[0].step == "Verify link"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_hardware_error_on_loopback_enable(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.diagnostics.loopback_set.side_effect = SwitchtecError("loopback fail", -1)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert final[0].step == "Verify link"
        assert final[0].status == StepStatus.PASS
        assert final[1].step == "Enable loopback"
        assert final[1].status == StepStatus.FAIL
        assert final[1].criticality == StepCriticality.CRITICAL
        assert summary.failed == 1
        assert summary.passed == 1

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_pattern_setup_error_continues(self, mock_time):
        """When pattern_gen_set fails for a specific pattern, recipe continues."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # First call to pattern_gen_set fails, rest succeed
        patgen_calls = {"n": 0}

        def patgen_side_effect(*args, **kwargs):
            patgen_calls["n"] += 1
            if patgen_calls["n"] == 1:
                raise SwitchtecError("pattern setup fail", -1)

        dev.diagnostics.pattern_gen_set = MagicMock(side_effect=patgen_side_effect)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        pattern_results = [r for r in final if r.step.startswith("Pattern ")]
        # First pattern should fail
        assert pattern_results[0].status == StepStatus.FAIL
        assert "Setup failed" in pattern_results[0].detail

        # Remaining patterns should pass (patgen succeeds after first call)
        for pr in pattern_results[1:]:
            assert pr.status == StepStatus.PASS

        assert summary.failed == 1
        assert summary.passed >= 5  # verify + enable + 5 patterns + disable

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_cancel_early(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        def get_status_and_cancel():
            cancel.set()
            return [_make_port_status(phys_id=0, link_up=True)]

        dev.get_status.side_effect = get_status_and_cancel

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert final[0].step == "Verify link"
        assert final[0].status == StepStatus.PASS
        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_cancel_after_loopback_enable(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        def loopback_set_and_cancel(*args, **kwargs):
            # Only cancel on the first (enable) call
            if args[1] is True:
                cancel.set()

        dev.diagnostics.loopback_set = MagicMock(side_effect=loopback_set_and_cancel)

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )

        assert summary.aborted is True
        # Cleanup should have been called: loopback_set(port_id, False)
        loopback_calls = dev.diagnostics.loopback_set.call_args_list
        # At least one call to disable loopback (False)
        assert any(
            call[0][1] is False
            for call in loopback_calls
            if len(call[0]) >= 2
        )

    def test_cleanup(self):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        recipe.cleanup(dev, port_id=0, gen="gen4")

        # Should disable pattern generator and loopback
        dev.diagnostics.pattern_gen_set.assert_called_once()
        dev.diagnostics.loopback_set.assert_called_once()

        # Verify loopback was disabled (False)
        lb_call = dev.diagnostics.loopback_set.call_args
        assert lb_call[0][0] == 0  # port_id
        assert lb_call[0][1] is False

    def test_cleanup_gen5(self):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        recipe.cleanup(dev, port_id=1, gen="gen5")

        call_args = dev.diagnostics.pattern_gen_set.call_args
        from serialcables_switchtec.bindings.constants import DiagPatternLinkRate

        # gen5 disabled_val = 10
        assert call_args[0][1] == 10
        assert call_args[0][2] == DiagPatternLinkRate.DISABLED

    def test_cleanup_swallows_errors(self):
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        dev.diagnostics.pattern_gen_set.side_effect = SwitchtecError("patgen fail", -1)
        dev.diagnostics.loopback_set.side_effect = SwitchtecError("loopback fail", -1)

        # Should not raise
        recipe.cleanup(dev, port_id=0, gen="gen4")

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_summary_counts(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        _, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )

        assert summary.recipe_name == "Loopback BER Sweep"
        # gen4: verify + enable loopback + 6 patterns + disable loopback = 9
        assert summary.total_steps == 9
        assert summary.passed == 9
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.skipped == 0
        assert summary.elapsed_s >= 0

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_gen5_has_8_patterns(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen5",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        pattern_results = [r for r in final if r.step.startswith("Pattern ")]
        assert len(pattern_results) == 8

        # Verify pattern names include gen5-specific patterns
        pattern_names = [r.data["pattern"] for r in pattern_results]
        assert "PRBS5" in pattern_names
        assert "PRBS20" in pattern_names

        # Total steps: verify + enable + 8 patterns + disable = 11
        assert summary.total_steps == 11

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_gen6_has_7_patterns(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen6",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        pattern_results = [r for r in final if r.step.startswith("Pattern ")]
        assert len(pattern_results) == 7

        # Total steps: verify + enable + 7 patterns + disable = 10
        assert summary.total_steps == 10

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_link_down_warns(self, mock_time):
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # No port matches phys_id=0
        port = _make_port_status(phys_id=99, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        assert final[0].step == "Verify link"
        assert final[0].status == StepStatus.WARN
        assert "DOWN" in final[0].detail

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_disable_loopback_error_warns(self, mock_time):
        """When the final disable step fails, it should WARN rather than FAIL."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # loopback_set: first call (enable) works, second call (disable) fails
        lb_calls = {"n": 0}

        def loopback_side_effect(*args, **kwargs):
            lb_calls["n"] += 1
            if lb_calls["n"] > 1:
                raise SwitchtecError("disable fail", -1)

        dev.diagnostics.loopback_set = MagicMock(side_effect=loopback_side_effect)

        # pattern_gen_set: first N calls work, last (disable) raises
        patgen_calls = {"n": 0}

        def patgen_side_effect(*args, **kwargs):
            patgen_calls["n"] += 1
            # The disable call happens at the end; gen4 has 6 patterns
            # so there are 6 patgen calls for patterns + 1 for disable = 7
            if patgen_calls["n"] > 6:
                raise SwitchtecError("patgen disable fail", -1)

        dev.diagnostics.pattern_gen_set = MagicMock(side_effect=patgen_side_effect)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        disable_result = [r for r in final if r.step == "Disable loopback"][0]
        assert disable_result.status == StepStatus.WARN
        assert "Cleanup warning" in disable_result.detail

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_cancel_during_pattern_sweep(self, mock_time):
        """Cancel midway through the pattern sweep."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        cancel = threading.Event()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Cancel after the second pattern_gen_set call (i.e., after 2 patterns started)
        patgen_calls = {"n": 0}

        def patgen_cancel_midway(*args, **kwargs):
            patgen_calls["n"] += 1
            if patgen_calls["n"] >= 3:
                cancel.set()

        dev.diagnostics.pattern_gen_set = MagicMock(side_effect=patgen_cancel_midway)

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )

        assert summary.aborted is True
        # Should have fewer than all 6 patterns completed
        pattern_results = [
            r for r in _final_results(results) if r.step.startswith("Pattern ")
        ]
        assert len(pattern_results) < 6

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_multiple_lanes(self, mock_time):
        """Verify that multiple lanes are polled correctly."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Use gen3 (6 patterns) with 4 lanes
        # Each pattern: 4 baseline reads + 4 final reads = 8 mon_get calls
        lane_args_collected = []

        def mon_get_tracking(port_id, lane):
            lane_args_collected.append(lane)
            return _make_pattern_mon_result(error_count=0)

        dev.diagnostics.pattern_mon_get = MagicMock(side_effect=mon_get_tracking)

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen3",
            duration_per_pattern_s=1, lane_count=4,
        )

        # Each pattern reads lanes 0..3 for baseline, then 0..3 for final
        # With 6 patterns: 6 * 8 = 48 calls
        assert len(lane_args_collected) == 48

        # Verify lanes 0,1,2,3 appear in the captured arguments
        unique_lanes = set(lane_args_collected)
        assert unique_lanes == {0, 1, 2, 3}

        assert summary.passed == 9  # verify + enable + 6 patterns + disable

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_baseline_mon_get_error(self, mock_time):
        """SwitchtecError during baseline mon_get defaults to 0."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # pattern_mon_get raises on all calls
        dev.diagnostics.pattern_mon_get = MagicMock(
            side_effect=SwitchtecError("mon read fail", -1),
        )

        results, summary = _run_recipe(
            recipe, dev,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )
        final = _final_results(results)

        # Patterns should all pass (0 errors since reads fail silently)
        pattern_results = [r for r in final if r.step.startswith("Pattern ")]
        for pr in pattern_results:
            assert pr.status == StepStatus.PASS
            assert pr.data["errors"] == 0

    @patch("serialcables_switchtec.core.workflows.loopback_sweep.time")
    def test_run_soak_loop_with_cancel(self, mock_time):
        """Cancel within the pattern soak loop (while time < deadline)."""
        recipe = LoopbackSweep()
        dev = _make_mock_device()
        cancel = threading.Event()

        # Use a time sequence that lets the soak loop execute once then cancel
        monotonic_vals = []
        # Pre-soak: enough values for verify + enable loopback overhead
        for i in range(20):
            monotonic_vals.append(float(i) * 0.1)
        # For the first pattern's soak:
        # deadline = time.monotonic() + dur_per -> e.g., 2.0 + 1 = 3.0
        monotonic_vals.append(2.0)  # deadline calc
        monotonic_vals.append(2.1)  # while condition (2.1 < 3.0 = True)
        # cancel check -> not set yet
        # sleep call -> we set cancel here
        monotonic_vals.append(2.2)  # sleep duration calc
        # after sleep: while condition (2.3 < 3.0 = True but cancel is set)
        monotonic_vals.append(2.3)
        # Rest: large values to finish everything
        for i in range(50):
            monotonic_vals.append(1000.0 + i)

        val_iter = iter(monotonic_vals)
        mock_time.monotonic = MagicMock(side_effect=lambda: next(val_iter, 9999.0))

        def cancel_on_sleep(duration):
            cancel.set()

        mock_time.sleep = MagicMock(side_effect=cancel_on_sleep)

        port = _make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        results, summary = _run_recipe(
            recipe, dev, cancel,
            port_id=0, gen="gen4",
            duration_per_pattern_s=1, lane_count=1,
        )

        assert summary.aborted is True
        mock_time.sleep.assert_called()
