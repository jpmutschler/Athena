"""Tests for performance/thermal workflow recipes: BandwidthBaseline, LatencyProfile, ThermalProfile."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.bandwidth_baseline import BandwidthBaseline
from serialcables_switchtec.core.workflows.latency_profile import LatencyProfile
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.thermal_profile import ThermalProfile
from serialcables_switchtec.exceptions import SwitchtecError

from tests.unit.test_workflows_helpers import (
    final_results,
    make_bw_result,
    make_lat_result,
    make_mock_device,
    make_port_status,
    run_recipe,
)


# ---------------------------------------------------------------------------
# BandwidthBaseline
# ---------------------------------------------------------------------------


class TestBandwidthBaseline:
    """Tests for the BandwidthBaseline recipe."""

    def test_parameters(self):
        recipe = BandwidthBaseline()
        params = recipe.parameters()
        names = [p.name for p in params]
        assert "port_id" in names
        assert "duration_s" in names
        assert "interval_s" in names

    def test_category_and_metadata(self):
        recipe = BandwidthBaseline()
        assert recipe.category == RecipeCategory.PERFORMANCE
        assert recipe.name == "Bandwidth Baseline"
        assert recipe.estimated_duration_s() == 12.0
        assert recipe.estimated_duration_s(duration_s=30) == 32.0

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_run_happy_path(self, mock_time):
        recipe = BandwidthBaseline()
        dev = make_mock_device()

        # Trace through run(): monotonic() is called at:
        #   1: start
        #   2: poll_start
        #   3: while condition (need < duration_s gap from poll_start)
        #   4: remaining calc inside loop
        #   5: while condition (need >= duration_s gap from poll_start)
        #   6: final summary
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 1.5 - 1.0 = 0.5 < 5 -> enter loop
            2.0,   # remaining calc
            100.0, # while check: 100.0 - 1.0 = 99 >= 5 -> exit
            100.1, # final summary
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.performance.bw_get.return_value = [make_bw_result(1000, 500)]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, duration_s=5, interval_s=1,
        )
        final = final_results(results)

        assert len(final) == 3
        assert final[0].step == "Verify port"
        assert final[0].status == StepStatus.PASS
        assert "Port 0 found" in final[0].detail

        assert final[1].step == "Sample bandwidth"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["sample_count"] == 1

        assert final[2].step == "Compute stats"
        assert final[2].status == StepStatus.PASS
        assert final[2].data["egress_avg"] == 1000
        assert final[2].data["ingress_avg"] == 500

        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_get_status_fails(self, mock_time):
        recipe = BandwidthBaseline()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.get_status.side_effect = SwitchtecError("hw fail", -1)

        results, summary = run_recipe(recipe, dev, port_id=0)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Verify port"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "hw fail" in final[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_port_not_found(self, mock_time):
        recipe = BandwidthBaseline()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # Return ports, but none with phys_id=5
        dev.get_status.return_value = [make_port_status(phys_id=0)]

        results, summary = run_recipe(recipe, dev, port_id=5)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Verify port"
        assert final[0].status == StepStatus.FAIL
        assert "Port 5 not found" in final[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_no_samples_collected(self, mock_time):
        """When all bw_get calls fail, compute stats should WARN."""
        recipe = BandwidthBaseline()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.performance.bw_get.side_effect = SwitchtecError("bw fail", -1)

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, duration_s=1, interval_s=1,
        )
        final = final_results(results)

        assert len(final) == 3
        assert final[0].status == StepStatus.PASS  # verify port
        assert final[1].status == StepStatus.PASS  # sample bandwidth (0 samples)
        assert final[2].step == "Compute stats"
        assert final[2].status == StepStatus.WARN
        assert "No samples collected" in final[2].detail
        assert summary.warnings == 1

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_cancel_during_sampling(self, mock_time):
        """Cancel during the bandwidth sampling loop."""
        recipe = BandwidthBaseline()
        dev = make_mock_device()
        cancel = threading.Event()

        # Monotonic calls: start, poll_start, while check (enter),
        # remaining, while check again (after cancel -> exit via cancel.is_set).
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 0.5 < 5 -> enter
            2.0,   # remaining calc
            999.0, # after cancel, loop re-checks cancel.is_set -> break
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))

        def cancel_on_sleep(duration):
            cancel.set()

        mock_time.sleep = MagicMock(side_effect=cancel_on_sleep)

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]
        dev.performance.bw_get.return_value = [make_bw_result(1000, 500)]

        results, summary = run_recipe(
            recipe, dev, cancel,
            port_id=0, duration_s=5, interval_s=1,
        )

        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.bandwidth_baseline.time")
    def test_multiple_samples_stats(self, mock_time):
        """Verify min/max/avg stats across multiple bandwidth samples."""
        recipe = BandwidthBaseline()
        dev = make_mock_device()

        # Trace through run() monotonic calls for 2 loop iterations:
        #   1: start
        #   2: poll_start
        #   3: while check iter 1 (gap < 5 -> enter)
        #   4: remaining calc iter 1
        #   5: while check iter 2 (gap < 5 -> enter)
        #   6: remaining calc iter 2
        #   7: while check iter 3 (gap >= 5 -> exit)
        #   8: final summary
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 0.5 < 5 -> enter
            2.0,   # remaining calc
            3.0,   # while check: 2.0 < 5 -> enter
            3.5,   # remaining calc
            100.0, # while check: 99.0 >= 5 -> exit
            100.1, # final summary
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))
        mock_time.sleep = MagicMock()

        port = make_port_status(phys_id=0, link_up=True)
        dev.get_status.return_value = [port]

        # Return different values on successive bw_get calls
        dev.performance.bw_get.side_effect = [
            [make_bw_result(800, 400)],
            [make_bw_result(1200, 600)],
        ]

        results, summary = run_recipe(
            recipe, dev,
            port_id=0, duration_s=5, interval_s=1,
        )
        final = final_results(results)

        stats_step = final[2]
        assert stats_step.step == "Compute stats"
        assert stats_step.status == StepStatus.PASS
        assert stats_step.data["egress_min"] == 800
        assert stats_step.data["egress_max"] == 1200
        assert stats_step.data["egress_avg"] == 1000.0
        assert stats_step.data["ingress_min"] == 400
        assert stats_step.data["ingress_max"] == 600
        assert stats_step.data["ingress_avg"] == 500.0
        assert stats_step.data["sample_count"] == 2


# ---------------------------------------------------------------------------
# LatencyProfile
# ---------------------------------------------------------------------------


class TestLatencyProfile:
    """Tests for the LatencyProfile recipe."""

    def test_parameters(self):
        recipe = LatencyProfile()
        params = recipe.parameters()
        names = [p.name for p in params]
        assert "egress_port_id" in names
        assert "ingress_port_id" in names
        assert "sample_count" in names

    def test_category_and_metadata(self):
        recipe = LatencyProfile()
        assert recipe.category == RecipeCategory.PERFORMANCE
        assert recipe.name == "Latency Measurement Profile"
        # Default: 10 samples * 0.25s + 2 = 4.5
        assert recipe.estimated_duration_s() == 4.5
        assert recipe.estimated_duration_s(sample_count=20) == 7.0

    @patch("serialcables_switchtec.core.workflows.latency_profile.time")
    def test_run_happy_path(self, mock_time):
        recipe = LatencyProfile()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(side_effect=lambda: 0.0)
        mock_time.sleep = MagicMock()

        dev.performance.lat_setup = MagicMock()
        dev.performance.lat_get = MagicMock(
            side_effect=[
                make_lat_result(current_ns=100, max_ns=200),
                make_lat_result(current_ns=150, max_ns=250),
                make_lat_result(current_ns=120, max_ns=220),
            ],
        )

        results, summary = run_recipe(
            recipe, dev,
            egress_port_id=0, ingress_port_id=1, sample_count=3,
        )
        final = final_results(results)

        assert len(final) == 3
        assert final[0].step == "Setup latency"
        assert final[0].status == StepStatus.PASS
        assert "egress=0" in final[0].detail
        assert "ingress=1" in final[0].detail

        assert final[1].step == "Collect samples"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["collected"] == 3

        assert final[2].step == "Analyze"
        assert final[2].status == StepStatus.PASS
        assert final[2].data["min_ns"] == 100
        assert final[2].data["max_ns"] == 150
        assert final[2].data["avg_ns"] == (100 + 150 + 120) / 3
        assert final[2].data["max_observed_ns"] == 250
        assert final[2].data["sample_count"] == 3

        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.latency_profile.time")
    def test_lat_setup_fails(self, mock_time):
        recipe = LatencyProfile()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(side_effect=lambda: 0.0)
        mock_time.sleep = MagicMock()

        dev.performance.lat_setup.side_effect = SwitchtecError("lat hw fail", -1)

        results, summary = run_recipe(
            recipe, dev,
            egress_port_id=0, ingress_port_id=1, sample_count=3,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Setup latency"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "lat hw fail" in final[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.latency_profile.time")
    def test_no_samples_collected(self, mock_time):
        """When all lat_get calls fail, analyze step should WARN."""
        recipe = LatencyProfile()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(side_effect=lambda: 0.0)
        mock_time.sleep = MagicMock()

        dev.performance.lat_setup = MagicMock()
        dev.performance.lat_get.side_effect = SwitchtecError("lat read fail", -1)

        results, summary = run_recipe(
            recipe, dev,
            egress_port_id=0, ingress_port_id=1, sample_count=3,
        )
        final = final_results(results)

        assert len(final) == 3
        assert final[0].status == StepStatus.PASS  # setup
        assert final[1].status == StepStatus.PASS  # collect (0/3)
        assert final[2].step == "Analyze"
        assert final[2].status == StepStatus.WARN
        assert "No latency samples collected" in final[2].detail
        assert summary.warnings == 1

    @patch("serialcables_switchtec.core.workflows.latency_profile.time")
    def test_cancel_during_collection(self, mock_time):
        """Cancel during the sample collection loop."""
        recipe = LatencyProfile()
        dev = make_mock_device()
        cancel = threading.Event()

        mock_time.monotonic = MagicMock(side_effect=lambda: 0.0)

        # Cancel when sleep is called (between sample iterations)
        def cancel_on_sleep(duration):
            cancel.set()

        mock_time.sleep = MagicMock(side_effect=cancel_on_sleep)

        dev.performance.lat_setup = MagicMock()
        dev.performance.lat_get = MagicMock(
            return_value=make_lat_result(current_ns=100, max_ns=200),
        )

        results, summary = run_recipe(
            recipe, dev, cancel,
            egress_port_id=0, ingress_port_id=1, sample_count=10,
        )

        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.latency_profile.time")
    def test_partial_samples(self, mock_time):
        """Some lat_get calls fail, others succeed -- analyze uses only successful samples."""
        recipe = LatencyProfile()
        dev = make_mock_device()

        mock_time.monotonic = MagicMock(side_effect=lambda: 0.0)
        mock_time.sleep = MagicMock()

        dev.performance.lat_setup = MagicMock()
        dev.performance.lat_get = MagicMock(
            side_effect=[
                make_lat_result(current_ns=100, max_ns=200),
                SwitchtecError("transient", -1),
                make_lat_result(current_ns=300, max_ns=400),
            ],
        )

        results, summary = run_recipe(
            recipe, dev,
            egress_port_id=0, ingress_port_id=1, sample_count=3,
        )
        final = final_results(results)

        assert final[1].data["collected"] == 2
        assert final[1].data["requested"] == 3

        assert final[2].status == StepStatus.PASS
        assert final[2].data["min_ns"] == 100
        assert final[2].data["max_ns"] == 300
        assert final[2].data["avg_ns"] == 200.0
        assert final[2].data["max_observed_ns"] == 400


# ---------------------------------------------------------------------------
# ThermalProfile
# ---------------------------------------------------------------------------


class TestThermalProfile:
    """Tests for the ThermalProfile recipe."""

    def test_parameters(self):
        recipe = ThermalProfile()
        params = recipe.parameters()
        names = [p.name for p in params]
        assert "duration_s" in names
        assert "interval_s" in names
        assert "num_sensors" in names

    def test_category_and_metadata(self):
        recipe = ThermalProfile()
        assert recipe.category == RecipeCategory.DEBUG
        assert recipe.name == "Switch Thermal Profile"
        # Default: 60 + 2 = 62
        assert recipe.estimated_duration_s() == 62.0
        assert recipe.estimated_duration_s(duration_s=120) == 122.0

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_run_happy_path(self, mock_time):
        recipe = ThermalProfile()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.get_die_temperatures.return_value = [42.5, 43.0, 41.0, 44.0, 42.0]

        results, summary = run_recipe(
            recipe, dev,
            duration_s=10, interval_s=2, num_sensors=5,
        )
        final = final_results(results)

        assert len(final) == 3
        assert final[0].step == "Initial read"
        assert final[0].status == StepStatus.PASS
        assert "S0=42.5C" in final[0].detail

        assert final[1].step == "Monitor"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["sample_count"] >= 1

        assert final[2].step == "Report"
        assert final[2].status == StepStatus.PASS
        assert len(final[2].data["sensors"]) == 5

        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_initial_read_fails(self, mock_time):
        recipe = ThermalProfile()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.get_die_temperatures.side_effect = SwitchtecError("temp read fail", -1)

        results, summary = run_recipe(
            recipe, dev,
            duration_s=10, interval_s=2, num_sensors=5,
        )
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Initial read"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL
        assert "temp read fail" in final[0].detail
        assert summary.failed == 1

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_high_temp_warns(self, mock_time):
        """Max temp >= 100 C should produce a WARN on the report step."""
        recipe = ThermalProfile()
        dev = make_mock_device()

        # Monotonic calls in run() for 1 monitor iteration:
        #   1: start
        #   2: poll_start
        #   3: while check (enter)
        #   4: remaining calc
        #   5: while check (exit)
        #   6: final summary
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 0.5 < 10 -> enter
            2.0,   # remaining calc
            100.0, # while check: 99.0 >= 10 -> exit
            100.1, # final summary
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))
        mock_time.sleep = MagicMock()

        # First call (baseline): normal temps; second call (monitor loop): hot sensor
        dev.get_die_temperatures.side_effect = [
            [42.5, 43.0, 41.0, 44.0, 42.0],
            [42.5, 43.0, 105.0, 44.0, 42.0],  # sensor 2 is >= 100C
        ]

        results, summary = run_recipe(
            recipe, dev,
            duration_s=10, interval_s=2, num_sensors=5,
        )
        final = final_results(results)

        report = final[2]
        assert report.step == "Report"
        assert report.status == StepStatus.WARN
        assert ">= 100C" in report.detail
        assert summary.warnings == 1

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_cancel_during_monitor(self, mock_time):
        """Cancel during the temperature monitoring loop."""
        recipe = ThermalProfile()
        dev = make_mock_device()
        cancel = threading.Event()

        # Monotonic calls: start, poll_start, while check (enter),
        # remaining, then cancel fires during sleep.
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 0.5 < 60 -> enter
            2.0,   # remaining calc
            999.0, # after cancel
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))

        def cancel_on_sleep(duration):
            cancel.set()

        mock_time.sleep = MagicMock(side_effect=cancel_on_sleep)

        dev.get_die_temperatures.return_value = [42.5, 43.0, 41.0, 44.0, 42.0]

        results, summary = run_recipe(
            recipe, dev, cancel,
            duration_s=60, interval_s=2, num_sensors=5,
        )

        assert summary.aborted is True

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_report_per_sensor_stats(self, mock_time):
        """Verify per-sensor min/max/avg are computed correctly across samples."""
        recipe = ThermalProfile()
        dev = make_mock_device()

        # Monotonic calls for 2 monitor loop iterations:
        #   1: start
        #   2: poll_start
        #   3: while check iter 1 (enter)
        #   4: remaining calc iter 1
        #   5: while check iter 2 (enter)
        #   6: remaining calc iter 2
        #   7: while check iter 3 (exit)
        #   8: final summary
        monotonic_vals = iter([
            0.0,   # start
            1.0,   # poll_start
            1.5,   # while check: 0.5 < 10 -> enter
            2.0,   # remaining calc
            3.0,   # while check: 2.0 < 10 -> enter
            3.5,   # remaining calc
            100.0, # while check: 99.0 >= 10 -> exit
            100.1, # final summary
        ])
        mock_time.monotonic = MagicMock(side_effect=lambda: next(monotonic_vals, 999.0))
        mock_time.sleep = MagicMock()

        # Baseline + 2 monitor samples = 3 total samples per sensor.
        # Use 2 sensors for simplicity.
        dev.get_die_temperatures.side_effect = [
            [40.0, 50.0],  # baseline
            [38.0, 55.0],  # monitor iter 1
            [42.0, 48.0],  # monitor iter 2
        ]

        results, summary = run_recipe(
            recipe, dev,
            duration_s=10, interval_s=2, num_sensors=2,
        )
        final = final_results(results)

        report = final[2]
        assert report.step == "Report"
        assert report.status == StepStatus.PASS

        sensors = report.data["sensors"]
        assert len(sensors) == 2
        assert report.data["sample_count"] == 3

        # Sensor 0: readings 40.0, 38.0, 42.0
        assert sensors[0]["min_c"] == 38.0
        assert sensors[0]["max_c"] == 42.0
        assert sensors[0]["avg_c"] == round((40.0 + 38.0 + 42.0) / 3, 2)

        # Sensor 1: readings 50.0, 55.0, 48.0
        assert sensors[1]["min_c"] == 48.0
        assert sensors[1]["max_c"] == 55.0
        assert sensors[1]["avg_c"] == round((50.0 + 55.0 + 48.0) / 3, 2)

    @patch("serialcables_switchtec.core.workflows.thermal_profile.time")
    def test_monitor_read_error_does_not_fail(self, mock_time):
        """SwitchtecError during monitor loop is silently caught; recipe continues."""
        recipe = ThermalProfile()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # First call succeeds (baseline), second call in monitor loop fails
        dev.get_die_temperatures.side_effect = [
            [42.5, 43.0],
            SwitchtecError("transient", -1),
        ]

        results, summary = run_recipe(
            recipe, dev,
            duration_s=10, interval_s=2, num_sensors=2,
        )
        final = final_results(results)

        # Recipe should still complete with PASS for all steps.
        # Only 1 sample (the baseline) since the monitor read failed.
        assert final[1].step == "Monitor"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["sample_count"] == 1

        assert final[2].step == "Report"
        assert final[2].status == StepStatus.PASS
        assert summary.passed == 3
        assert summary.failed == 0
