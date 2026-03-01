"""Tests for generation-aware equalization validation."""

from __future__ import annotations

import dataclasses

import pytest

from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.models.eq_validation import (
    EqRange,
    GEN_EQ_RANGES,
    GEN_FOM_THRESHOLDS,
    validate_eq_cursor,
    validate_eq_table,
    validate_fom,
)


class TestGenEqRanges:
    def test_gen_eq_ranges_has_all_gens(self):
        assert SwitchtecGen.GEN3 in GEN_EQ_RANGES
        assert SwitchtecGen.GEN4 in GEN_EQ_RANGES
        assert SwitchtecGen.GEN5 in GEN_EQ_RANGES
        assert SwitchtecGen.GEN6 in GEN_EQ_RANGES

    def test_gen6_pre_range_bipolar(self):
        gen6_pre = GEN_EQ_RANGES[SwitchtecGen.GEN6]["pre"]
        assert gen6_pre.min_val == -10
        assert gen6_pre.max_val == 10

    def test_gen3_post_range(self):
        gen3_post = GEN_EQ_RANGES[SwitchtecGen.GEN3]["post"]
        assert gen3_post.min_val == -4
        assert gen3_post.max_val == 0


class TestGenFomThresholds:
    def test_gen_fom_thresholds_has_all_gens(self):
        assert SwitchtecGen.GEN3 in GEN_FOM_THRESHOLDS
        assert SwitchtecGen.GEN4 in GEN_FOM_THRESHOLDS
        assert SwitchtecGen.GEN5 in GEN_FOM_THRESHOLDS
        assert SwitchtecGen.GEN6 in GEN_FOM_THRESHOLDS


class TestValidateEqCursor:
    def test_validate_cursor_in_range(self):
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-2, gen=SwitchtecGen.GEN4
        )
        assert result.valid is True

    def test_validate_cursor_out_of_range(self):
        # Gen3 pre range is [-3, 0], so -8 is out of range
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-8, gen=SwitchtecGen.GEN3
        )
        assert result.valid is False

    def test_validate_cursor_gen6_positive(self):
        # Gen6 pre range is [-10, 10], so +5 is valid
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=5, gen=SwitchtecGen.GEN6
        )
        assert result.valid is True

    def test_validate_cursor_unknown_gen(self):
        # UNKNOWN gen has no ranges defined, so any value is accepted
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=99, gen=SwitchtecGen.UNKNOWN
        )
        assert result.valid is True

    def test_validate_cursor_boundary_min(self):
        # Gen3 pre min is -3
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-3, gen=SwitchtecGen.GEN3
        )
        assert result.valid is True

    def test_validate_cursor_boundary_max(self):
        # Gen3 pre max is 0
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=0, gen=SwitchtecGen.GEN3
        )
        assert result.valid is True

    def test_validate_cursor_one_past_min(self):
        # Gen3 pre min is -3, so -4 is out of range
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-4, gen=SwitchtecGen.GEN3
        )
        assert result.valid is False

    def test_validate_cursor_result_contains_lane_info(self):
        result = validate_eq_cursor(
            lane=7, cursor_name="post", value=-1, gen=SwitchtecGen.GEN4
        )
        assert result.lane == 7
        assert result.cursor_name == "post"
        assert result.value == -1

    def test_validate_cursor_invalid_message_contains_range(self):
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-8, gen=SwitchtecGen.GEN3
        )
        assert "outside" in result.message
        assert "[-3, 0]" in result.message

    def test_validate_cursor_valid_message_contains_range(self):
        result = validate_eq_cursor(
            lane=0, cursor_name="pre", value=-1, gen=SwitchtecGen.GEN3
        )
        assert "within" in result.message


class TestValidateFom:
    def test_validate_fom_gen5_above_threshold(self):
        # Gen5 threshold is 8
        result = validate_fom(lane=0, fom=10, gen=SwitchtecGen.GEN5)
        assert result.valid is True

    def test_validate_fom_gen5_below_threshold(self):
        result = validate_fom(lane=0, fom=5, gen=SwitchtecGen.GEN5)
        assert result.valid is False

    def test_validate_fom_gen6_threshold_12(self):
        # Gen6 threshold is 12; exactly 12 should be valid (>=)
        result = validate_fom(lane=0, fom=12, gen=SwitchtecGen.GEN6)
        assert result.valid is True

    def test_validate_fom_gen3_zero_ok(self):
        # Gen3 threshold is 0, so fom=0 is valid (>= 0)
        result = validate_fom(lane=0, fom=0, gen=SwitchtecGen.GEN3)
        assert result.valid is True

    def test_validate_fom_result_contains_threshold(self):
        result = validate_fom(lane=2, fom=5, gen=SwitchtecGen.GEN5)
        assert result.threshold == 8
        assert result.lane == 2
        assert result.fom == 5

    def test_validate_fom_valid_message(self):
        result = validate_fom(lane=0, fom=20, gen=SwitchtecGen.GEN5)
        assert ">=" in result.message

    def test_validate_fom_invalid_message(self):
        result = validate_fom(lane=0, fom=5, gen=SwitchtecGen.GEN5)
        assert "<" in result.message


class TestValidateEqTable:
    def test_validate_eq_table_all_valid(self):
        # Gen4 pre range [-6, 0], post range [-9, 0]
        cursors = [(-1, -2), (-3, -4), (-5, -6), (-2, -1)]
        results = validate_eq_table(cursors, SwitchtecGen.GEN4)
        assert len(results) == 8  # 4 lanes x 2 cursors
        assert all(r.valid for r in results)

    def test_validate_eq_table_some_invalid(self):
        # Gen3 pre range [-3, 0], post range [-4, 0]
        # Lane 0: valid pre, valid post
        # Lane 1: invalid pre (-8 outside [-3,0]), valid post
        cursors = [(-1, -2), (-8, -1)]
        results = validate_eq_table(cursors, SwitchtecGen.GEN3)
        assert len(results) == 4  # 2 lanes x 2 cursors
        valid_count = sum(1 for r in results if r.valid)
        invalid_count = sum(1 for r in results if not r.valid)
        assert valid_count == 3
        assert invalid_count == 1

    def test_validate_eq_table_lane_numbering(self):
        cursors = [(-1, -1), (-2, -2)]
        results = validate_eq_table(cursors, SwitchtecGen.GEN4)
        # Lane 0 pre, lane 0 post, lane 1 pre, lane 1 post
        assert results[0].lane == 0
        assert results[0].cursor_name == "pre"
        assert results[1].lane == 0
        assert results[1].cursor_name == "post"
        assert results[2].lane == 1
        assert results[2].cursor_name == "pre"
        assert results[3].lane == 1
        assert results[3].cursor_name == "post"


class TestEqRangeImmutable:
    def test_eq_range_immutable(self):
        eq_range = EqRange(min_val=-3, max_val=0, name="Pre-cursor")
        with pytest.raises(dataclasses.FrozenInstanceError):
            eq_range.min_val = 5  # type: ignore[misc]
