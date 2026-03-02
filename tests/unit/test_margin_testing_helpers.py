"""Tests for margin testing page helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.ui.pages.margin_testing import (
    _build_heatmap_grids,
    _build_row,
    _error_row,
    _resolve_thresholds,
)


def _make_ch(
    eye_left_lim: int = 4,
    eye_right_lim: int = 3,
    eye_top_left_lim: int = 6,
    eye_top_right_lim: int = 5,
    eye_bot_left_lim: int = 5,
    eye_bot_right_lim: int = 4,
) -> MagicMock:
    """Create a mock CrossHairResult."""
    ch = MagicMock()
    ch.eye_left_lim = eye_left_lim
    ch.eye_right_lim = eye_right_lim
    ch.eye_top_left_lim = eye_top_left_lim
    ch.eye_top_right_lim = eye_top_right_lim
    ch.eye_bot_left_lim = eye_bot_left_lim
    ch.eye_bot_right_lim = eye_bot_right_lim
    return ch


class TestResolveThresholds:
    """_resolve_thresholds tests."""

    def test_gen6_defaults(self):
        t = _resolve_thresholds("gen6")
        assert t["h_warn"] == 7
        assert t["v_warn"] == 10
        assert t["is_pam4"] is True

    def test_gen5_defaults(self):
        t = _resolve_thresholds("gen5")
        assert t["h_warn"] == 20
        assert t["v_warn"] == 30
        assert t["is_pam4"] is False

    def test_gen4_defaults(self):
        t = _resolve_thresholds("gen4")
        assert t["h_warn"] == 25
        assert t["v_warn"] == 35
        assert t["is_pam4"] is False

    def test_gen3_defaults(self):
        t = _resolve_thresholds("gen3")
        assert t["h_warn"] == 30
        assert t["v_warn"] == 40
        assert t["is_pam4"] is False

    def test_custom_overrides(self):
        t = _resolve_thresholds("custom", custom_h=15, custom_v=25)
        assert t["h_warn"] == 15
        assert t["v_warn"] == 25

    def test_custom_without_values_uses_defaults(self):
        t = _resolve_thresholds("custom")
        assert t["h_warn"] == 20
        assert t["v_warn"] == 30

    def test_unknown_gen_falls_back_to_gen5(self):
        t = _resolve_thresholds("gen99")
        assert t["h_warn"] == 20
        assert t["v_warn"] == 30

    def test_gen6_is_pam4(self):
        assert _resolve_thresholds("gen6")["is_pam4"] is True

    def test_gen3_through_5_not_pam4(self):
        for gen in ("gen3", "gen4", "gen5"):
            assert _resolve_thresholds(gen)["is_pam4"] is False


class TestBuildRow:
    """_build_row tests."""

    def test_pam4_pass(self):
        """Gen6 PAM4 with margins above thresholds."""
        ch = _make_ch(eye_left_lim=4, eye_right_lim=4,
                       eye_top_left_lim=6, eye_top_right_lim=6,
                       eye_bot_left_lim=5, eye_bot_right_lim=5)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 8   # 4 + 4
        assert row["v_margin"] == 11  # min(6,6) + min(5,5)
        assert row["verdict"] == "PASS"
        assert row["signaling"] == "PAM4"

    def test_nrz_pass(self):
        """Gen5 NRZ with margins above thresholds."""
        ch = _make_ch(eye_left_lim=12, eye_right_lim=10,
                       eye_top_left_lim=18, eye_top_right_lim=16,
                       eye_bot_left_lim=15, eye_bot_right_lim=14)
        row = _build_row(port_id=1, lane_id=4, lane_offset=0,
                         ch=ch, h_warn=20, v_warn=30, is_pam4=False)
        assert row["h_margin"] == 22  # 12 + 10
        assert row["v_margin"] == 30  # min(18,16) + min(15,14) = 16 + 14
        assert row["verdict"] == "PASS"
        assert row["signaling"] == "NRZ"

    def test_pam4_marginal(self):
        """Margins below threshold but non-zero -> MARGINAL."""
        ch = _make_ch(eye_left_lim=2, eye_right_lim=2,
                       eye_top_left_lim=3, eye_top_right_lim=3,
                       eye_bot_left_lim=2, eye_bot_right_lim=2)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 4
        assert row["v_margin"] == 5
        assert row["verdict"] == "MARGINAL"

    def test_pam4_fail_zero_margins(self):
        """Zero margins -> FAIL."""
        ch = _make_ch(eye_left_lim=0, eye_right_lim=0,
                       eye_top_left_lim=0, eye_top_right_lim=0,
                       eye_bot_left_lim=0, eye_bot_right_lim=0)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["verdict"] == "FAIL"

    def test_exactly_at_threshold_is_pass(self):
        """Margin exactly at threshold -> PASS."""
        ch = _make_ch(eye_left_lim=4, eye_right_lim=3,
                       eye_top_left_lim=5, eye_top_right_lim=5,
                       eye_bot_left_lim=5, eye_bot_right_lim=5)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 7
        assert row["v_margin"] == 10
        assert row["verdict"] == "PASS"

    def test_h_fail_v_pass_is_marginal(self):
        """H below threshold, V above -> MARGINAL (not PASS)."""
        ch = _make_ch(eye_left_lim=2, eye_right_lim=2,
                       eye_top_left_lim=8, eye_top_right_lim=8,
                       eye_bot_left_lim=7, eye_bot_right_lim=7)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 4  # below 7
        assert row["v_margin"] == 15  # above 10
        assert row["verdict"] == "MARGINAL"

    def test_margin_formula_uses_min(self):
        """v_top uses min(top_left, top_right), not average."""
        ch = _make_ch(eye_top_left_lim=10, eye_top_right_lim=2,
                       eye_bot_left_lim=8, eye_bot_right_lim=3)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=0, v_warn=0, is_pam4=True)
        # v_top = min(10, 2) = 2, v_bot = min(8, 3) = 3
        assert row["v_margin"] == 5

    def test_row_fields_present(self):
        ch = _make_ch()
        row = _build_row(port_id=2, lane_id=5, lane_offset=1,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["port_id"] == 2
        assert row["lane_id"] == 5
        assert row["lane_index"] == 1
        assert "eye_left_lim" in row
        assert "eye_bot_right_lim" in row

    def test_pam4_flag_in_row(self):
        ch = _make_ch()
        row_pam4 = _build_row(0, 0, 0, ch, 7, 10, is_pam4=True)
        row_nrz = _build_row(0, 0, 0, ch, 20, 30, is_pam4=False)
        assert row_pam4["signaling"] == "PAM4"
        assert row_nrz["signaling"] == "NRZ"

    def test_negative_eye_limits_produce_fail(self):
        """Negative eye limits (error condition) -> FAIL."""
        ch = _make_ch(eye_left_lim=-5, eye_right_lim=3,
                       eye_top_left_lim=6, eye_top_right_lim=6,
                       eye_bot_left_lim=5, eye_bot_right_lim=5)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == -2  # -5 + 3
        assert row["verdict"] == "FAIL"

    def test_one_sided_zero_h_margin_is_fail(self):
        """H-margin zero but V non-zero -> FAIL (collapsed horizontal eye)."""
        ch = _make_ch(eye_left_lim=0, eye_right_lim=0,
                       eye_top_left_lim=6, eye_top_right_lim=6,
                       eye_bot_left_lim=5, eye_bot_right_lim=5)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 0
        assert row["v_margin"] == 11
        assert row["verdict"] == "FAIL"

    def test_one_sided_zero_v_margin_is_fail(self):
        """V-margin zero but H non-zero -> FAIL (collapsed vertical eye)."""
        ch = _make_ch(eye_left_lim=4, eye_right_lim=4,
                       eye_top_left_lim=0, eye_top_right_lim=0,
                       eye_bot_left_lim=0, eye_bot_right_lim=0)
        row = _build_row(port_id=0, lane_id=0, lane_offset=0,
                         ch=ch, h_warn=7, v_warn=10, is_pam4=True)
        assert row["h_margin"] == 8
        assert row["v_margin"] == 0
        assert row["verdict"] == "FAIL"


class TestErrorRow:
    """_error_row tests."""

    def test_fail_verdict(self):
        row = _error_row(port_id=0, lane_id=0, lane_offset=0, is_pam4=True)
        assert row["verdict"] == "FAIL"

    def test_zero_margins(self):
        row = _error_row(port_id=0, lane_id=0, lane_offset=0, is_pam4=True)
        assert row["h_margin"] == 0
        assert row["v_margin"] == 0

    def test_all_eye_limits_zero(self):
        row = _error_row(port_id=0, lane_id=0, lane_offset=0, is_pam4=False)
        for key in ("eye_left_lim", "eye_right_lim", "eye_top_left_lim",
                     "eye_top_right_lim", "eye_bot_left_lim", "eye_bot_right_lim"):
            assert row[key] == 0

    def test_pam4_signaling(self):
        row = _error_row(port_id=0, lane_id=0, lane_offset=0, is_pam4=True)
        assert row["signaling"] == "PAM4"

    def test_nrz_signaling(self):
        row = _error_row(port_id=0, lane_id=0, lane_offset=0, is_pam4=False)
        assert row["signaling"] == "NRZ"

    def test_port_and_lane_preserved(self):
        row = _error_row(port_id=3, lane_id=12, lane_offset=4, is_pam4=True)
        assert row["port_id"] == 3
        assert row["lane_id"] == 12
        assert row["lane_index"] == 4


class TestBuildHeatmapGrids:
    """_build_heatmap_grids tests."""

    def test_single_port(self):
        rows = [
            {"port_id": 0, "lane_index": 0, "h_margin": 8, "v_margin": 12},
            {"port_id": 0, "lane_index": 1, "h_margin": 7, "v_margin": 10},
        ]
        port_ids, max_lanes, h_grid, v_grid = _build_heatmap_grids(rows)
        assert port_ids == [0]
        assert max_lanes == 2
        assert h_grid == [[8, 7]]
        assert v_grid == [[12, 10]]

    def test_multiple_ports(self):
        rows = [
            {"port_id": 0, "lane_index": 0, "h_margin": 8, "v_margin": 12},
            {"port_id": 2, "lane_index": 0, "h_margin": 6, "v_margin": 9},
        ]
        port_ids, max_lanes, h_grid, v_grid = _build_heatmap_grids(rows)
        assert port_ids == [0, 2]
        assert max_lanes == 1

    def test_uneven_widths_padded_with_none(self):
        rows = [
            {"port_id": 0, "lane_index": 0, "h_margin": 8, "v_margin": 12},
            {"port_id": 0, "lane_index": 1, "h_margin": 7, "v_margin": 10},
            {"port_id": 1, "lane_index": 0, "h_margin": 6, "v_margin": 9},
        ]
        port_ids, max_lanes, h_grid, v_grid = _build_heatmap_grids(rows)
        assert max_lanes == 2
        # Port 1 only has 1 lane, second cell should be None
        assert h_grid[1] == [6, None]
        assert v_grid[1] == [9, None]

    def test_ports_sorted(self):
        rows = [
            {"port_id": 5, "lane_index": 0, "h_margin": 8, "v_margin": 12},
            {"port_id": 1, "lane_index": 0, "h_margin": 6, "v_margin": 9},
        ]
        port_ids, _, _, _ = _build_heatmap_grids(rows)
        assert port_ids == [1, 5]
