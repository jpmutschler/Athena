"""Tests for margin diamond pure function: _build_diamond_traces."""

from __future__ import annotations

import pytest

from serialcables_switchtec.models.diagnostics import CrossHairResult
from serialcables_switchtec.ui.components.margin_diamond import (
    _DIAMOND_COLORS,
    _build_diamond_traces,
)


def _make_crosshair(
    lane_id: int = 0,
    left: int = 10,
    right: int = 10,
    top_left: int = 5,
    top_right: int = 5,
    bot_left: int = 5,
    bot_right: int = 5,
) -> CrossHairResult:
    return CrossHairResult(
        lane_id=lane_id,
        state=0,
        state_name="DONE",
        eye_left_lim=left,
        eye_right_lim=right,
        eye_top_left_lim=top_left,
        eye_top_right_lim=top_right,
        eye_bot_left_lim=bot_left,
        eye_bot_right_lim=bot_right,
    )


class TestBuildDiamondTraces:
    """_build_diamond_traces() tests."""

    def test_empty_results(self):
        traces = _build_diamond_traces([])
        assert traces == []

    def test_single_lane(self):
        results = [_make_crosshair(lane_id=0)]
        traces = _build_diamond_traces(results)
        assert len(traces) == 1
        assert traces[0]["name"] == "Lane 0"

    def test_diamond_shape_coordinates(self):
        r = _make_crosshair(left=10, right=12, top_left=6, top_right=8, bot_left=4, bot_right=6)
        traces = _build_diamond_traces([r])
        t = traces[0]
        # top = (6 + 8) / 2 = 7.0
        assert t["y"][0] == 7.0
        # right = 12
        assert t["x"][1] == 12
        # bot = -(4 + 6) / 2 = -5.0
        assert t["y"][2] == -5.0
        # left = -10
        assert t["x"][3] == -10

    def test_diamond_closes_polygon(self):
        traces = _build_diamond_traces([_make_crosshair()])
        t = traces[0]
        assert t["x"][0] == t["x"][4]
        assert t["y"][0] == t["y"][4]
        assert t["x"][0] == 0

    def test_trace_type_is_scatter(self):
        traces = _build_diamond_traces([_make_crosshair()])
        assert traces[0]["type"] == "scatter"

    def test_fill_is_toself(self):
        traces = _build_diamond_traces([_make_crosshair()])
        assert traces[0]["fill"] == "toself"

    def test_color_cycles(self):
        results = [_make_crosshair(lane_id=i) for i in range(20)]
        traces = _build_diamond_traces(results)
        assert len(traces) == 20
        # Colors should cycle
        assert traces[0]["line"]["color"] == traces[16]["line"]["color"]

    def test_multiple_lanes_have_distinct_colors(self):
        results = [_make_crosshair(lane_id=i) for i in range(4)]
        traces = _build_diamond_traces(results)
        colors = [t["line"]["color"] for t in traces]
        assert len(set(colors)) == 4

    def test_fillcolor_has_alpha(self):
        traces = _build_diamond_traces([_make_crosshair()])
        fillcolor = traces[0]["fillcolor"]
        # Hex color gets "26" suffix for ~15% alpha
        assert fillcolor.endswith("26") or "0.15" in fillcolor

    def test_hover_template(self):
        traces = _build_diamond_traces([_make_crosshair(lane_id=3)])
        assert "Lane 3" in traces[0]["hovertemplate"]
