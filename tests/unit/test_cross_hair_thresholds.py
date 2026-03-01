"""Tests for generation-aware cross-hair margin thresholds."""

from __future__ import annotations

from unittest.mock import patch

from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.core.workflows.cross_hair_margin import (
    CrossHairMargin,
    _MARGIN_THRESHOLDS,
)
from serialcables_switchtec.core.workflows.models import StepStatus

from tests.unit.test_workflows_helpers import (
    final_results,
    make_cross_hair_result,
    make_mock_device,
    run_recipe,
)


def _advancing_monotonic():
    """Yield monotonically increasing timestamps."""
    t = 0.0
    while True:
        yield t
        t += 0.1


class TestMarginThresholds:
    def test_threshold_table_has_gen3_through_gen6(self):
        assert SwitchtecGen.GEN3 in _MARGIN_THRESHOLDS
        assert SwitchtecGen.GEN4 in _MARGIN_THRESHOLDS
        assert SwitchtecGen.GEN5 in _MARGIN_THRESHOLDS
        assert SwitchtecGen.GEN6 in _MARGIN_THRESHOLDS

    def test_gen6_thresholds_lower_than_gen3(self):
        gen3 = _MARGIN_THRESHOLDS[SwitchtecGen.GEN3]
        gen6 = _MARGIN_THRESHOLDS[SwitchtecGen.GEN6]
        assert gen6["h_warn"] < gen3["h_warn"]
        assert gen6["v_warn"] < gen3["v_warn"]

    def test_gen6_h_warn_is_7(self):
        assert _MARGIN_THRESHOLDS[SwitchtecGen.GEN6]["h_warn"] == 7

    def test_gen6_v_warn_is_10(self):
        assert _MARGIN_THRESHOLDS[SwitchtecGen.GEN6]["v_warn"] == 10

    def test_parameters_include_h_and_v_margin_warn(self):
        recipe = CrossHairMargin()
        params = recipe.parameters()
        names = [p.name for p in params]
        assert "h_margin_warn" in names
        assert "v_margin_warn" in names

    def test_margin_warn_params_depend_on_generation(self):
        recipe = CrossHairMargin()
        params = recipe.parameters()
        h_param = next(p for p in params if p.name == "h_margin_warn")
        v_param = next(p for p in params if p.name == "v_margin_warn")
        assert h_param.depends_on == "generation"
        assert v_param.depends_on == "generation"

    def test_margin_warn_params_are_optional(self):
        recipe = CrossHairMargin()
        params = recipe.parameters()
        h_param = next(p for p in params if p.name == "h_margin_warn")
        v_param = next(p for p in params if p.name == "v_margin_warn")
        assert not h_param.required
        assert not v_param.required


class TestGenAwareMarginAnalysis:
    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_gen6_uses_pam4_thresholds(self, mock_time):
        """Gen6 uses h_warn=7, v_warn=10, so margins of 8/12 pass."""
        mock_time.monotonic.side_effect = _advancing_monotonic()
        mock_time.sleep.return_value = None

        dev = make_mock_device()
        # Margins: h=8 (>7), v=12 (>10) → should PASS with Gen6
        ch = make_cross_hair_result(
            lane_id=0,
            state_name="DONE",
            eye_left_lim=4,
            eye_right_lim=4,
            eye_top_left_lim=6,
            eye_top_right_lim=6,
            eye_bot_left_lim=6,
            eye_bot_right_lim=6,
        )
        dev.diagnostics.cross_hair_get.return_value = [ch]

        recipe = CrossHairMargin()
        results, summary = run_recipe(
            recipe, dev,
            generation=SwitchtecGen.GEN6,
        )
        final = final_results(results)
        analyze_step = final[-1]
        assert analyze_step.status == StepStatus.PASS

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_gen3_uses_nrz_thresholds(self, mock_time):
        """Gen3 uses h_warn=30, v_warn=40, so margins of 8/12 fail."""
        mock_time.monotonic.side_effect = _advancing_monotonic()
        mock_time.sleep.return_value = None

        dev = make_mock_device()
        # Same margins as above, but Gen3 thresholds are higher
        ch = make_cross_hair_result(
            lane_id=0,
            state_name="DONE",
            eye_left_lim=4,
            eye_right_lim=4,
            eye_top_left_lim=6,
            eye_top_right_lim=6,
            eye_bot_left_lim=6,
            eye_bot_right_lim=6,
        )
        dev.diagnostics.cross_hair_get.return_value = [ch]

        recipe = CrossHairMargin()
        results, summary = run_recipe(
            recipe, dev,
            generation=SwitchtecGen.GEN3,
        )
        final = final_results(results)
        analyze_step = final[-1]
        assert analyze_step.status == StepStatus.WARN

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_explicit_threshold_overrides_generation(self, mock_time):
        """Explicit h_margin_warn/v_margin_warn override gen defaults."""
        mock_time.monotonic.side_effect = _advancing_monotonic()
        mock_time.sleep.return_value = None

        dev = make_mock_device()
        ch = make_cross_hair_result(
            lane_id=0,
            state_name="DONE",
            eye_left_lim=3,
            eye_right_lim=3,
            eye_top_left_lim=4,
            eye_top_right_lim=4,
            eye_bot_left_lim=4,
            eye_bot_right_lim=4,
        )
        dev.diagnostics.cross_hair_get.return_value = [ch]

        recipe = CrossHairMargin()
        # Gen3 would use h_warn=30, but explicit override to 5
        results, summary = run_recipe(
            recipe, dev,
            generation=SwitchtecGen.GEN3,
            h_margin_warn=5,
            v_margin_warn=5,
        )
        final = final_results(results)
        analyze_step = final[-1]
        # h=6 > 5, v=8 > 5 → PASS
        assert analyze_step.status == StepStatus.PASS

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_no_generation_uses_legacy_defaults(self, mock_time):
        """Without generation param, uses legacy _H_MARGIN_WARN/_V_MARGIN_WARN."""
        mock_time.monotonic.side_effect = _advancing_monotonic()
        mock_time.sleep.return_value = None

        dev = make_mock_device()
        # h=30, v=40 → meets legacy defaults (h>=20, v>=30)
        ch = make_cross_hair_result(
            lane_id=0,
            state_name="DONE",
            eye_left_lim=15,
            eye_right_lim=15,
            eye_top_left_lim=20,
            eye_top_right_lim=20,
            eye_bot_left_lim=20,
            eye_bot_right_lim=20,
        )
        dev.diagnostics.cross_hair_get.return_value = [ch]

        recipe = CrossHairMargin()
        results, summary = run_recipe(recipe, dev)
        final = final_results(results)
        analyze_step = final[-1]
        assert analyze_step.status == StepStatus.PASS

    @patch("serialcables_switchtec.core.workflows.cross_hair_margin.time")
    def test_gen5_thresholds_match_legacy(self, mock_time):
        """Gen5 thresholds (h=20, v=30) match the legacy defaults."""
        mock_time.monotonic.side_effect = _advancing_monotonic()
        mock_time.sleep.return_value = None

        gen5_thresholds = _MARGIN_THRESHOLDS[SwitchtecGen.GEN5]
        assert gen5_thresholds["h_warn"] == 20
        assert gen5_thresholds["v_warn"] == 30
