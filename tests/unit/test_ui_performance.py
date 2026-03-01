"""Tests for performance page pure functions: _make_bw_figure, _clear_bw_history."""

from __future__ import annotations

import pytest

from serialcables_switchtec.ui.pages.performance import _make_bw_figure
from serialcables_switchtec.ui.theme import COLORS


class TestMakeBwFigure:
    """_make_bw_figure() tests."""

    def test_empty_history(self):
        fig = _make_bw_figure({})
        assert fig["data"] == []
        assert "layout" in fig

    def test_single_port_creates_two_traces(self):
        history = {
            0: {
                "timestamps": [0.0, 1.0, 2.0],
                "egress": [100, 200, 300],
                "ingress": [50, 100, 150],
            }
        }
        fig = _make_bw_figure(history)
        assert len(fig["data"]) == 2

    def test_two_ports_create_four_traces(self):
        history = {
            0: {"timestamps": [1.0], "egress": [100], "ingress": [50]},
            4: {"timestamps": [1.0], "egress": [200], "ingress": [100]},
        }
        fig = _make_bw_figure(history)
        assert len(fig["data"]) == 4

    def test_egress_trace_is_solid(self):
        history = {0: {"timestamps": [1.0], "egress": [100], "ingress": [50]}}
        fig = _make_bw_figure(history)
        egress_trace = fig["data"][0]
        assert "dash" not in egress_trace.get("line", {})

    def test_ingress_trace_is_dashed(self):
        history = {0: {"timestamps": [1.0], "egress": [100], "ingress": [50]}}
        fig = _make_bw_figure(history)
        ingress_trace = fig["data"][1]
        assert ingress_trace["line"]["dash"] == "dash"

    def test_trace_names_include_port_id(self):
        history = {7: {"timestamps": [1.0], "egress": [100], "ingress": [50]}}
        fig = _make_bw_figure(history)
        assert fig["data"][0]["name"] == "P7 Egress"
        assert fig["data"][1]["name"] == "P7 Ingress"

    def test_layout_has_dark_theme(self):
        fig = _make_bw_figure({})
        layout = fig["layout"]
        assert layout["paper_bgcolor"] == COLORS.bg_primary
        assert layout["plot_bgcolor"] == COLORS.bg_card

    def test_layout_has_axis_titles(self):
        fig = _make_bw_figure({})
        layout = fig["layout"]
        assert layout["xaxis"]["title"] == "Elapsed (s)"
        assert layout["yaxis"]["title"] == "Bytes"

    def test_ports_sorted_by_id(self):
        history = {
            4: {"timestamps": [1.0], "egress": [100], "ingress": [50]},
            0: {"timestamps": [1.0], "egress": [200], "ingress": [100]},
        }
        fig = _make_bw_figure(history)
        assert "P0" in fig["data"][0]["name"]
        assert "P4" in fig["data"][2]["name"]

    def test_trace_mode_is_lines_markers(self):
        history = {0: {"timestamps": [1.0], "egress": [100], "ingress": [50]}}
        fig = _make_bw_figure(history)
        assert fig["data"][0]["mode"] == "lines+markers"

    def test_colors_cycle_for_many_ports(self):
        history = {
            i: {"timestamps": [1.0], "egress": [100], "ingress": [50]}
            for i in range(15)
        }
        fig = _make_bw_figure(history)
        assert len(fig["data"]) == 30

    def test_timestamp_data_matches_input(self):
        timestamps = [0.0, 1.0, 2.0, 3.0]
        history = {0: {"timestamps": timestamps, "egress": [1, 2, 3, 4], "ingress": [5, 6, 7, 8]}}
        fig = _make_bw_figure(history)
        assert fig["data"][0]["x"] == timestamps
