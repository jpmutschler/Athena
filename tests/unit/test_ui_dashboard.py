"""Tests for dashboard page helper: _temp_color threshold logic."""

from __future__ import annotations

import pytest

from serialcables_switchtec.ui.pages.dashboard import _temp_color
from serialcables_switchtec.ui.theme import COLORS


class TestTempColor:
    """_temp_color() threshold tests."""

    def test_below_70_returns_success(self):
        assert _temp_color(50.0) == COLORS.success

    def test_at_zero_returns_success(self):
        assert _temp_color(0.0) == COLORS.success

    def test_at_69_returns_success(self):
        assert _temp_color(69.9) == COLORS.success

    def test_at_70_returns_warning(self):
        assert _temp_color(70.0) == COLORS.warning

    def test_between_70_and_85_returns_warning(self):
        assert _temp_color(77.5) == COLORS.warning

    def test_at_84_returns_warning(self):
        assert _temp_color(84.9) == COLORS.warning

    def test_at_85_returns_error(self):
        assert _temp_color(85.0) == COLORS.error

    def test_above_85_returns_error(self):
        assert _temp_color(100.0) == COLORS.error

    def test_negative_temp(self):
        assert _temp_color(-10.0) == COLORS.success
