"""Tests for margin heatmap helpers: build_margin_csv, build_margin_json."""

from __future__ import annotations

import csv
import io
import json

import pytest

from serialcables_switchtec.ui.components.margin_heatmap import (
    build_margin_csv,
    build_margin_json,
)


def _make_row(
    port_id: int = 0,
    lane_index: int = 0,
    lane_id: int = 0,
    h_margin: int = 14,
    v_margin: int = 20,
    verdict: str = "PASS",
) -> dict:
    return {
        "port_id": port_id,
        "lane_index": lane_index,
        "lane_id": lane_id,
        "h_margin": h_margin,
        "v_margin": v_margin,
        "verdict": verdict,
        "eye_left_lim": 7,
        "eye_right_lim": 7,
        "eye_top_left_lim": 10,
        "eye_top_right_lim": 10,
        "eye_bot_left_lim": 10,
        "eye_bot_right_lim": 10,
    }


class TestBuildMarginCsv:
    """build_margin_csv tests."""

    def test_returns_bytes(self):
        data = build_margin_csv([_make_row()])
        assert isinstance(data, bytes)

    def test_utf8_decodable(self):
        data = build_margin_csv([_make_row()])
        text = data.decode("utf-8")
        assert "port_id" in text

    def test_correct_headers(self):
        data = build_margin_csv([_make_row()])
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        expected = {
            "port_id", "lane_index", "lane_id", "h_margin", "v_margin",
            "verdict", "eye_left_lim", "eye_right_lim", "eye_top_left_lim",
            "eye_top_right_lim", "eye_bot_left_lim", "eye_bot_right_lim",
        }
        assert set(reader.fieldnames) == expected

    def test_row_count_matches(self):
        rows = [_make_row(lane_id=i, lane_index=i) for i in range(4)]
        data = build_margin_csv(rows)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        csv_rows = list(reader)
        assert len(csv_rows) == 4

    def test_row_values_correct(self):
        row = _make_row(port_id=2, lane_id=5, h_margin=14, verdict="PASS")
        data = build_margin_csv([row])
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        csv_row = next(reader)
        assert csv_row["port_id"] == "2"
        assert csv_row["lane_id"] == "5"
        assert csv_row["h_margin"] == "14"
        assert csv_row["verdict"] == "PASS"

    def test_empty_rows(self):
        data = build_margin_csv([])
        text = data.decode("utf-8")
        # Header line only
        lines = [line for line in text.strip().split("\n") if line]
        assert len(lines) == 1
        assert "port_id" in lines[0]

    def test_extra_keys_ignored(self):
        row = {**_make_row(), "extra_field": "should_be_ignored"}
        data = build_margin_csv([row])
        text = data.decode("utf-8")
        assert "extra_field" not in text


class TestBuildMarginJson:
    """build_margin_json tests."""

    def test_returns_bytes(self):
        data = build_margin_json([_make_row()], {"h_warn": 7, "v_warn": 10})
        assert isinstance(data, bytes)

    def test_valid_json(self):
        data = build_margin_json([_make_row()], {"h_warn": 7, "v_warn": 10})
        parsed = json.loads(data.decode("utf-8"))
        assert "thresholds" in parsed
        assert "lanes" in parsed

    def test_thresholds_preserved(self):
        thresholds = {"h_warn": 7, "v_warn": 10, "is_pam4": True}
        data = build_margin_json([_make_row()], thresholds)
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["thresholds"] == thresholds

    def test_lanes_count_matches(self):
        rows = [_make_row(lane_id=i) for i in range(3)]
        data = build_margin_json(rows, {"h_warn": 7})
        parsed = json.loads(data.decode("utf-8"))
        assert len(parsed["lanes"]) == 3

    def test_empty_rows(self):
        data = build_margin_json([], {"h_warn": 7, "v_warn": 10})
        parsed = json.loads(data.decode("utf-8"))
        assert parsed["lanes"] == []
        assert parsed["thresholds"] == {"h_warn": 7, "v_warn": 10}

    def test_lane_data_preserved(self):
        row = _make_row(port_id=3, lane_id=7, h_margin=14, verdict="PASS")
        data = build_margin_json([row], {"h_warn": 7})
        parsed = json.loads(data.decode("utf-8"))
        lane = parsed["lanes"][0]
        assert lane["port_id"] == 3
        assert lane["lane_id"] == 7
        assert lane["h_margin"] == 14
        assert lane["verdict"] == "PASS"
