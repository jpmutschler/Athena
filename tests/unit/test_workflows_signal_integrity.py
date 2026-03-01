"""Tests for signal-integrity workflow recipes: EyeQuickScan, CrossHairMargin, EqReport."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from serialcables_switchtec.core.workflows.eye_quick_scan import EyeQuickScan
from serialcables_switchtec.core.workflows.cross_hair_margin import CrossHairMargin
from serialcables_switchtec.core.workflows.eq_report import EqReport
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError

from tests.unit.test_workflows_helpers import (
    final_results,
    make_cross_hair_result,
    make_eq_coeff,
    make_eq_fslf,
    make_eq_table,
    make_eye_data,
    make_mock_device,
    run_recipe,
)

# Eye diagram grid constants (must match the recipe module).
_X_COUNT = 129
_Y_COUNT = 256
_PIXEL_COUNT = _X_COUNT * _Y_COUNT


def _good_eye_pixels() -> list[float]:
    """Build a pixel array where the centre is open, producing a large eye area.

    The recipe computes eye width/height from the centre row and centre column.
    A pixel value of 0.0 is below any positive threshold, so filling most of
    the grid with 0.0 and only the edges with a high value yields a wide-open
    eye with area well above the 20 % warning threshold.
    """
    pixels = [0.0] * _PIXEL_COUNT
    # Set the outer border rows to a high value so max_val > 0 and threshold > 0.
    for x in range(_X_COUNT):
        pixels[x] = 100.0  # first row
        pixels[(_Y_COUNT - 1) * _X_COUNT + x] = 100.0  # last row
    return pixels


def _poor_eye_pixels() -> list[float]:
    """Build a pixel array where nearly everything is above threshold (tiny eye).

    Fill most pixels with a high value so that area < 20 %.
    Leave a tiny region open in the centre so width/height are small but nonzero.
    """
    pixels = [100.0] * _PIXEL_COUNT
    # Open a small 3x3 patch at the centre.
    center_y = _Y_COUNT // 2
    center_x = _X_COUNT // 2
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            pixels[(center_y + dy) * _X_COUNT + (center_x + dx)] = 0.0
    return pixels


# ---------------------------------------------------------------------------
# EyeQuickScan
# ---------------------------------------------------------------------------


class TestEyeQuickScan:
    """Tests for the EyeQuickScan recipe."""

    def test_parameters(self):
        recipe = EyeQuickScan()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) >= 2

        names = {p.name for p in params}
        assert "lane_id" in names
        assert "step_interval" in names

    @patch("serialcables_switchtec.core.workflows.eye_quick_scan.time")
    def test_happy_path(self, mock_time):
        """Full run: eye_start succeeds, fetch returns good pixel data, area > 20 %."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        good_pixels = _good_eye_pixels()
        eye_data = make_eye_data(pixels=good_pixels)
        dev.diagnostics.eye_fetch.return_value = eye_data

        results, summary = run_recipe(recipe, dev, lane_id=0, step_interval=10)
        final = final_results(results)

        # Four terminal steps: start, wait, metrics, summary
        assert len(final) == 4

        assert final[0].step == "Start eye capture"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Wait for capture"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["pixel_count"] == len(good_pixels)

        assert final[2].step == "Compute metrics"
        assert final[2].status == StepStatus.PASS
        assert "width" in final[2].data
        assert "height" in final[2].data
        assert "area" in final[2].data
        assert final[2].data["area"] > 0.20

        assert final[3].step == "Summary"
        assert final[3].status == StepStatus.PASS
        assert final[3].data["lane_id"] == 0

        assert summary is not None
        assert summary.passed == 4
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.eye_quick_scan.time")
    def test_eye_start_fails(self, mock_time):
        """eye_start raises SwitchtecError -- recipe should FAIL at step 0."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.diagnostics.eye_start.side_effect = SwitchtecError("hw error")

        results, summary = run_recipe(recipe, dev, lane_id=0)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Start eye capture"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL

        assert summary is not None
        assert summary.failed == 1
        assert summary.passed == 0

    @patch("serialcables_switchtec.core.workflows.eye_quick_scan.time")
    def test_eye_fetch_timeout(self, mock_time):
        """eye_fetch always raises -- recipe times out at step 1."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        # Simulate time marching past the 60 s timeout on second monotonic check.
        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            # First call is 0.0 (start), then jump past timeout.
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.diagnostics.eye_fetch.side_effect = SwitchtecError("not ready")

        results, summary = run_recipe(recipe, dev, lane_id=0)
        final = final_results(results)

        # Should have step 0 PASS, then step 1 FAIL (timeout).
        assert any(r.status == StepStatus.FAIL for r in final)
        timeout_step = [r for r in final if r.status == StepStatus.FAIL][0]
        assert timeout_step.step == "Wait for capture"
        assert "timed out" in timeout_step.detail

        assert summary is not None
        assert summary.failed >= 1
        # cleanup should call eye_cancel
        dev.diagnostics.eye_cancel.assert_called()

    @patch("serialcables_switchtec.core.workflows.eye_quick_scan.time")
    def test_poor_eye_area_warns(self, mock_time):
        """Pixel data with area < 20 % triggers WARN at summary step."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        poor_pixels = _poor_eye_pixels()
        eye_data = make_eye_data(pixels=poor_pixels)
        dev.diagnostics.eye_fetch.return_value = eye_data

        results, summary = run_recipe(recipe, dev, lane_id=0)
        final = final_results(results)

        assert len(final) == 4

        summary_step = final[3]
        assert summary_step.step == "Summary"
        assert summary_step.status == StepStatus.WARN
        assert "degraded" in summary_step.detail

        assert summary is not None
        assert summary.warnings == 1

    @patch("serialcables_switchtec.core.workflows.eye_quick_scan.time")
    def test_cancellation_at_start(self, mock_time):
        """Cancellation before eye_start yields an aborted summary."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        cancel = threading.Event()
        cancel.set()

        results, summary = run_recipe(recipe, dev, cancel=cancel, lane_id=0)

        assert summary is not None
        assert summary.aborted is True
        # eye_start should never have been called
        dev.diagnostics.eye_start.assert_not_called()

    def test_cleanup_calls_eye_cancel(self):
        """cleanup() calls dev.diagnostics.eye_cancel."""
        recipe = EyeQuickScan()
        dev = make_mock_device()

        recipe.cleanup(dev)

        dev.diagnostics.eye_cancel.assert_called_once()

    def test_step_count_consistency(self):
        """Recipe reports total_steps=4 for every yielded result."""
        recipe = EyeQuickScan()
        assert recipe.name == "Eye Diagram Quick Scan"
        assert recipe.category == RecipeCategory.SIGNAL_INTEGRITY


# ---------------------------------------------------------------------------
# CrossHairMargin
# ---------------------------------------------------------------------------


class TestCrossHairMargin:
    """Tests for the CrossHairMargin recipe."""

    def test_parameters(self):
        recipe = CrossHairMargin()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) >= 2

        names = {p.name for p in params}
        assert "start_lane_id" in names
        assert "num_lanes" in names

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_happy_path(self, mock_time):
        """Enable succeeds, poll returns DONE results with good margins."""
        recipe = CrossHairMargin()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # Two lanes, both DONE with good margins (h=30 >= 20, v=40 >= 30).
        ch0 = make_cross_hair_result(lane_id=0, state_name="DONE",
                                     eye_left_lim=15, eye_right_lim=15,
                                     eye_top_left_lim=20, eye_top_right_lim=20,
                                     eye_bot_left_lim=20, eye_bot_right_lim=20)
        ch1 = make_cross_hair_result(lane_id=1, state_name="DONE",
                                     eye_left_lim=15, eye_right_lim=15,
                                     eye_top_left_lim=20, eye_top_right_lim=20,
                                     eye_bot_left_lim=20, eye_bot_right_lim=20)
        dev.diagnostics.cross_hair_get.return_value = [ch0, ch1]

        results, summary = run_recipe(recipe, dev, start_lane_id=0, num_lanes=2)
        final = final_results(results)

        assert len(final) == 3

        assert final[0].step == "Enable measurement"
        assert final[0].status == StepStatus.PASS

        assert final[1].step == "Poll results"
        assert final[1].status == StepStatus.PASS
        assert "2 lane(s)" in final[1].detail

        assert final[2].step == "Disable + analyze"
        assert final[2].status == StepStatus.PASS
        assert final[2].data is not None
        assert len(final[2].data["lanes"]) == 2

        assert summary is not None
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.aborted is False

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_enable_fails(self, mock_time):
        """cross_hair_enable raises SwitchtecError -- FAIL step 0."""
        recipe = CrossHairMargin()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        dev.diagnostics.cross_hair_enable.side_effect = SwitchtecError("enable failed")

        results, summary = run_recipe(recipe, dev, start_lane_id=0, num_lanes=1)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Enable measurement"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL

        assert summary is not None
        assert summary.failed == 1
        assert summary.passed == 0

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_poll_timeout(self, mock_time):
        """cross_hair_get never returns DONE -- FAIL step 1."""
        recipe = CrossHairMargin()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            # Jump well past the per-lane timeout on second call.
            return float(call_count["n"] * 100)

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # cross_hair_get always raises, so ch_results stays None.
        dev.diagnostics.cross_hair_get.side_effect = SwitchtecError("not ready")

        results, summary = run_recipe(recipe, dev, start_lane_id=0, num_lanes=1)
        final = final_results(results)

        fail_steps = [r for r in final if r.status == StepStatus.FAIL]
        assert len(fail_steps) >= 1
        assert fail_steps[0].step == "Poll results"
        assert "no results" in fail_steps[0].detail

        assert summary is not None
        assert summary.failed >= 1
        dev.diagnostics.cross_hair_disable.assert_called()

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_low_margins_warn(self, mock_time):
        """Low horizontal/vertical margins trigger WARN at analyze step."""
        recipe = CrossHairMargin()
        dev = make_mock_device()

        call_count = {"n": 0}

        def advancing_monotonic():
            call_count["n"] += 1
            return float(call_count["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        # Lane 0 has h_margin=10 (< 20) and v_margin=10 (< 30).
        ch_low = make_cross_hair_result(
            lane_id=0, state_name="DONE",
            eye_left_lim=5, eye_right_lim=5,
            eye_top_left_lim=5, eye_top_right_lim=5,
            eye_bot_left_lim=5, eye_bot_right_lim=5,
        )
        dev.diagnostics.cross_hair_get.return_value = [ch_low]

        results, summary = run_recipe(recipe, dev, start_lane_id=0, num_lanes=1)
        final = final_results(results)

        analyze_step = final[2]
        assert analyze_step.step == "Disable + analyze"
        assert analyze_step.status == StepStatus.WARN
        assert "warning" in analyze_step.detail.lower()

        assert summary is not None
        assert summary.warnings == 1

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_cancellation_during_poll(self, mock_time):
        """Cancel event set during poll -- aborted summary, cleanup called."""
        recipe = CrossHairMargin()
        dev = make_mock_device()

        poll_calls = {"n": 0}

        def advancing_monotonic():
            poll_calls["n"] += 1
            return float(poll_calls["n"])

        mock_time.monotonic = MagicMock(side_effect=advancing_monotonic)
        mock_time.sleep = MagicMock()

        cancel = threading.Event()

        # First call to cross_hair_get: set cancel and return in-progress.
        def get_and_cancel(*args, **kwargs):
            cancel.set()
            result = make_cross_hair_result(lane_id=0, state_name="IN_PROGRESS")
            return [result]

        dev.diagnostics.cross_hair_get.side_effect = get_and_cancel

        results, summary = run_recipe(recipe, dev, cancel=cancel,
                                      start_lane_id=0, num_lanes=1)

        assert summary is not None
        assert summary.aborted is True
        dev.diagnostics.cross_hair_disable.assert_called()

    def test_step_count_consistency(self):
        """Metadata matches expected values."""
        recipe = CrossHairMargin()
        assert recipe.name == "Cross-Hair Margin Analysis"
        assert recipe.category == RecipeCategory.SIGNAL_INTEGRITY
        assert recipe.estimated_duration_s(num_lanes=4) == 40.0


# ---------------------------------------------------------------------------
# EqReport
# ---------------------------------------------------------------------------


class TestEqReport:
    """Tests for the EqReport recipe."""

    def test_parameters(self):
        recipe = EqReport()
        params = recipe.parameters()

        assert isinstance(params, list)
        assert len(params) >= 2

        names = {p.name for p in params}
        assert "port_id" in names
        assert "num_lanes" in names

    def test_happy_path(self):
        """All three reads succeed -- all steps PASS."""
        recipe = EqReport()
        dev = make_mock_device()

        coeff = make_eq_coeff(lane_count=4)
        dev.diagnostics.port_eq_tx_coeff.return_value = coeff

        table = make_eq_table(step_count=10, lane_id=0, active_count=5)
        dev.diagnostics.port_eq_tx_table.return_value = table

        # Four lanes, all with valid FS/LF.
        dev.diagnostics.port_eq_tx_fslf.side_effect = [
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0, num_lanes=4)
        final = final_results(results)

        assert len(final) == 3

        assert final[0].step == "Read TX coefficients"
        assert final[0].status == StepStatus.PASS
        assert final[0].data["lane_count"] == 4
        assert len(final[0].data["cursors"]) == 4

        assert final[1].step == "Read FOM table"
        assert final[1].status == StepStatus.PASS
        assert final[1].data["step_count"] == 10
        assert final[1].data["active_count"] == 5

        assert final[2].step == "Read FS/LF"
        assert final[2].status == StepStatus.PASS
        assert len(final[2].data["fslf"]) == 4

        assert summary is not None
        assert summary.passed == 3
        assert summary.failed == 0
        assert summary.warnings == 0
        assert summary.aborted is False

    def test_tx_coeff_fails(self):
        """port_eq_tx_coeff raises -- FAIL step 0, recipe aborts (CRITICAL)."""
        recipe = EqReport()
        dev = make_mock_device()

        dev.diagnostics.port_eq_tx_coeff.side_effect = SwitchtecError("coeff read fail")

        results, summary = run_recipe(recipe, dev, port_id=0, num_lanes=4)
        final = final_results(results)

        assert len(final) == 1
        assert final[0].step == "Read TX coefficients"
        assert final[0].status == StepStatus.FAIL
        assert final[0].criticality == StepCriticality.CRITICAL

        assert summary is not None
        assert summary.failed == 1
        assert summary.passed == 0

    def test_tx_table_fails_warns(self):
        """port_eq_tx_table raises -- step 1 WARN (non-critical), recipe continues."""
        recipe = EqReport()
        dev = make_mock_device()

        coeff = make_eq_coeff(lane_count=4)
        dev.diagnostics.port_eq_tx_coeff.return_value = coeff

        dev.diagnostics.port_eq_tx_table.side_effect = SwitchtecError("table read fail")

        dev.diagnostics.port_eq_tx_fslf.side_effect = [
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
            make_eq_fslf(fs=63, lf=15),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0, num_lanes=4)
        final = final_results(results)

        assert len(final) == 3

        assert final[0].status == StepStatus.PASS  # coeff read ok
        assert final[1].step == "Read FOM table"
        assert final[1].status == StepStatus.WARN  # table read failed, non-critical
        assert final[2].status == StepStatus.PASS  # FS/LF ok

        assert summary is not None
        assert summary.warnings == 1
        assert summary.failed == 0

    def test_fslf_some_lanes_fs_zero_warns(self):
        """Some lanes have fs=0 -- step 2 WARN."""
        recipe = EqReport()
        dev = make_mock_device()

        coeff = make_eq_coeff(lane_count=2)
        dev.diagnostics.port_eq_tx_coeff.return_value = coeff

        table = make_eq_table(step_count=10, lane_id=0, active_count=5)
        dev.diagnostics.port_eq_tx_table.return_value = table

        # Lane 0 has fs=0 (warning), lane 1 is normal.
        dev.diagnostics.port_eq_tx_fslf.side_effect = [
            make_eq_fslf(fs=0, lf=15),
            make_eq_fslf(fs=63, lf=15),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0, num_lanes=2)
        final = final_results(results)

        assert final[2].step == "Read FS/LF"
        assert final[2].status == StepStatus.WARN
        assert "FS=0" in final[2].detail

        assert summary is not None
        assert summary.warnings == 1

    def test_fslf_some_lanes_raise_error_warns(self):
        """Some lanes raise SwitchtecError during FS/LF read -- step 2 WARN."""
        recipe = EqReport()
        dev = make_mock_device()

        coeff = make_eq_coeff(lane_count=2)
        dev.diagnostics.port_eq_tx_coeff.return_value = coeff

        table = make_eq_table(step_count=10, lane_id=0, active_count=5)
        dev.diagnostics.port_eq_tx_table.return_value = table

        # Lane 0 reads fine, lane 1 raises.
        dev.diagnostics.port_eq_tx_fslf.side_effect = [
            make_eq_fslf(fs=63, lf=15),
            SwitchtecError("lane 1 read fail"),
        ]

        results, summary = run_recipe(recipe, dev, port_id=0, num_lanes=2)
        final = final_results(results)

        assert final[2].step == "Read FS/LF"
        assert final[2].status == StepStatus.WARN
        assert "read failed" in final[2].detail
        assert final[2].data["fslf"][1]["fs"] == -1
        assert final[2].data["fslf"][1]["lf"] == -1

        assert summary is not None
        assert summary.warnings == 1

    def test_cancellation_before_step_1(self):
        """Cancel event set before run -- aborted summary."""
        recipe = EqReport()
        dev = make_mock_device()

        cancel = threading.Event()
        cancel.set()

        results, summary = run_recipe(recipe, dev, cancel=cancel,
                                      port_id=0, num_lanes=4)

        assert summary is not None
        assert summary.aborted is True
        dev.diagnostics.port_eq_tx_coeff.assert_not_called()

    def test_step_count_consistency(self):
        """Metadata matches expected values."""
        recipe = EqReport()
        assert recipe.name == "Port Equalization Report"
        assert recipe.category == RecipeCategory.SIGNAL_INTEGRITY
        assert recipe.estimated_duration_s() == 3.0
