"""Tests for eye chart pure functions: _contiguous_below, _compute_eye_metrics."""

from __future__ import annotations

import pytest

from serialcables_switchtec.ui.components.eye_chart import (
    _compute_eye_metrics,
    _contiguous_below,
)


# ── _contiguous_below() ─────────────────────────────────────────────────


class TestContiguousBelow:
    """_contiguous_below() tests."""

    def test_empty_list(self):
        assert _contiguous_below([], 1.0) == 0

    def test_single_element_below(self):
        assert _contiguous_below([0.5], 1.0) == 1

    def test_single_element_above(self):
        assert _contiguous_below([2.0], 1.0) == 0

    def test_single_element_equal(self):
        assert _contiguous_below([1.0], 1.0) == 1

    def test_all_below(self):
        assert _contiguous_below([0.1, 0.2, 0.3, 0.4, 0.5], 1.0) == 5

    def test_all_above(self):
        assert _contiguous_below([2.0, 3.0, 4.0], 1.0) == 0

    def test_center_above_returns_zero(self):
        data = [0.1, 0.2, 5.0, 0.2, 0.1]
        assert _contiguous_below(data, 1.0) == 0

    def test_center_below_expands_outward(self):
        data = [5.0, 0.1, 0.2, 0.3, 5.0]
        assert _contiguous_below(data, 1.0) == 3

    def test_asymmetric_expansion(self):
        data = [5.0, 5.0, 0.1, 0.2, 0.3]
        assert _contiguous_below(data, 1.0) == 3

    def test_threshold_zero_center_above(self):
        # center index = 2, data[2] = 1.0 > 0.0 -> returns 0
        data = [0.0, 0.0, 1.0, 0.0, 0.0]
        assert _contiguous_below(data, 0.0) == 0

    def test_threshold_zero_center_at_zero(self):
        data = [1.0, 0.0, 0.0, 0.0, 1.0]
        assert _contiguous_below(data, 0.0) == 3

    def test_two_elements_both_below(self):
        assert _contiguous_below([0.1, 0.2], 1.0) == 2

    def test_two_elements_first_above(self):
        assert _contiguous_below([5.0, 0.2], 1.0) == 1

    def test_two_elements_center_above(self):
        # center = 2 // 2 = 1, data[1] = 5.0 > 1.0 -> returns 0
        assert _contiguous_below([0.1, 5.0], 1.0) == 0

    def test_large_open_center(self):
        data = [100] * 5 + [0] * 20 + [100] * 5
        # center index = 15, which is in the open region
        assert _contiguous_below(data, 10) == 20

    def test_negative_values(self):
        data = [-1.0, -0.5, 0.0, -0.5, -1.0]
        assert _contiguous_below(data, 0.0) == 5

    def test_exact_threshold_boundary(self):
        data = [1.0, 0.5, 0.5, 0.5, 1.0]
        assert _contiguous_below(data, 0.5) == 3

    def test_all_equal_to_threshold(self):
        data = [1.0, 1.0, 1.0, 1.0, 1.0]
        assert _contiguous_below(data, 1.0) == 5


# ── _compute_eye_metrics() ──────────────────────────────────────────────


class TestComputeEyeMetrics:
    """_compute_eye_metrics() tests."""

    def test_empty_pixels(self):
        result = _compute_eye_metrics([], 0, 0)
        assert result == {"width": 0, "height": 0, "area_pct": 0.0}

    def test_zero_x_count(self):
        result = _compute_eye_metrics([1.0], 0, 1)
        assert result == {"width": 0, "height": 0, "area_pct": 0.0}

    def test_zero_y_count(self):
        result = _compute_eye_metrics([1.0], 1, 0)
        assert result == {"width": 0, "height": 0, "area_pct": 0.0}

    def test_uniform_zero_pixels(self):
        # All zeros -> 100% open eye
        pixels = [0.0] * 25
        result = _compute_eye_metrics(pixels, 5, 5)
        assert result["width"] == 5
        assert result["height"] == 5
        assert result["area_pct"] == 100.0

    def test_uniform_high_pixels(self):
        # All same high value -> threshold = value * 0.1
        # All pixels above threshold -> mostly closed
        pixels = [100.0] * 25
        result = _compute_eye_metrics(pixels, 5, 5)
        assert result["width"] == 0
        assert result["height"] == 0
        assert result["area_pct"] == 0.0

    def test_open_eye_pattern(self):
        # 5x5 grid: edges high, center low
        x, y = 5, 5
        pixels = []
        for row in range(y):
            for col in range(x):
                if 1 <= row <= 3 and 1 <= col <= 3:
                    pixels.append(0.0)
                else:
                    pixels.append(100.0)
        result = _compute_eye_metrics(pixels, x, y)
        assert result["width"] > 0
        assert result["height"] > 0
        assert 0 < result["area_pct"] < 100

    def test_1x1_grid(self):
        result = _compute_eye_metrics([0.0], 1, 1)
        assert result["width"] == 1
        assert result["height"] == 1
        assert result["area_pct"] == 100.0

    def test_area_pct_is_float(self):
        pixels = [0.0] * 10
        result = _compute_eye_metrics(pixels, 5, 2)
        assert isinstance(result["area_pct"], float)

    def test_width_matches_center_row(self):
        # 5x3 grid: center row (y=1) has 3 zeros, others all high
        x, y = 5, 3
        pixels = [100.0] * 15
        # Set center row (y=1, indices 5-9) center columns to 0
        pixels[6] = 0.0  # (1,1)
        pixels[7] = 0.0  # (1,2) - center
        pixels[8] = 0.0  # (1,3)
        result = _compute_eye_metrics(pixels, x, y)
        assert result["width"] == 3

    def test_height_matches_center_column(self):
        # 3x5 grid: center column (x=1) has 3 zeros, others all high
        x, y = 3, 5
        pixels = [100.0] * 15
        # Set center column (x=1) rows 1-3 to 0
        pixels[1 * x + 1] = 0.0  # (1,1)
        pixels[2 * x + 1] = 0.0  # (2,1) - center
        pixels[3 * x + 1] = 0.0  # (3,1)
        result = _compute_eye_metrics(pixels, x, y)
        assert result["height"] == 3
