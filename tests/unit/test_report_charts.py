"""Tests for CSS-based chart primitives."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.report_charts import (
    css_bar_chart,
    css_metric_card,
    css_results_table,
    css_status_badge,
)


# ---------------------------------------------------------------------------
# css_bar_chart
# ---------------------------------------------------------------------------


class TestCssBarChart:
    def test_produces_bars_with_correct_widths(self) -> None:
        result = css_bar_chart([("A", 50), ("B", 100)], max_value=100)
        assert "50.0%" in result
        assert "100.0%" in result

    def test_labels_present(self) -> None:
        result = css_bar_chart([("Lane 0", 10.5)])
        assert "Lane 0" in result
        assert "10.50" in result

    def test_threshold_coloring(self) -> None:
        result = css_bar_chart(
            [("Low", 0.2), ("High", 0.5)],
            warn_threshold=0.3,
        )
        # Low bar should use default color, high bar should use red
        assert "#ff4444" in result

    def test_empty_bars_returns_no_data(self) -> None:
        result = css_bar_chart([])
        assert "No data" in result

    def test_single_item(self) -> None:
        result = css_bar_chart([("Only", 42)])
        assert "Only" in result
        assert "100.0%" in result  # single bar takes full width

    def test_zero_values_handled(self) -> None:
        result = css_bar_chart([("Zero", 0)])
        assert "Zero" in result

    def test_html_escaping(self) -> None:
        result = css_bar_chart([("<script>", 10)])
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_custom_max_value(self) -> None:
        result = css_bar_chart([("A", 25)], max_value=50)
        assert "50.0%" in result

    def test_default_max_uses_largest(self) -> None:
        result = css_bar_chart([("A", 30), ("B", 60)])
        # B should be 100%, A should be 50%
        assert "100.0%" in result
        assert "50.0%" in result


# ---------------------------------------------------------------------------
# css_metric_card
# ---------------------------------------------------------------------------


class TestCssMetricCard:
    def test_contains_label_and_value(self) -> None:
        result = css_metric_card("Total Errors", "42")
        assert "Total Errors" in result
        assert "42" in result

    def test_custom_color(self) -> None:
        result = css_metric_card("Score", "95", color="#00ff88")
        assert "#00ff88" in result

    def test_html_escaping(self) -> None:
        result = css_metric_card("<b>Label</b>", "<val>")
        assert "<b>" not in result
        assert "&lt;b&gt;" in result


# ---------------------------------------------------------------------------
# css_status_badge
# ---------------------------------------------------------------------------


class TestCssStatusBadge:
    def test_pass_badge_green(self) -> None:
        result = css_status_badge("PASS", "pass")
        assert "#00ff88" in result
        assert "PASS" in result

    def test_fail_badge_red(self) -> None:
        result = css_status_badge("FAIL", "fail")
        assert "#ff4444" in result

    def test_warn_badge_yellow(self) -> None:
        result = css_status_badge("WARN", "warn")
        assert "#ffaa00" in result

    def test_skip_badge_gray(self) -> None:
        result = css_status_badge("SKIP", "skip")
        assert "#666" in result

    def test_unknown_status_falls_back(self) -> None:
        result = css_status_badge("???", "unknown")
        assert "#666" in result

    def test_html_escaping(self) -> None:
        result = css_status_badge("<script>alert(1)</script>", "pass")
        assert "<script>" not in result


# ---------------------------------------------------------------------------
# css_results_table
# ---------------------------------------------------------------------------


class TestCssResultsTable:
    def _make_result(
        self,
        step: str = "Check Link",
        status: StepStatus = StepStatus.PASS,
        detail: str = "ok",
    ) -> RecipeResult:
        return RecipeResult(
            recipe_name="Test",
            step=step,
            step_index=0,
            total_steps=1,
            status=status,
            detail=detail,
        )

    def test_empty_results_shows_no_results(self) -> None:
        result = css_results_table([])
        assert "No results" in result

    def test_produces_table_with_rows(self) -> None:
        results = [
            self._make_result(step="Step A", status=StepStatus.PASS, detail="good"),
            self._make_result(step="Step B", status=StepStatus.FAIL, detail="bad"),
        ]
        html_str = css_results_table(results)
        assert "<table>" in html_str
        assert "Step A" in html_str
        assert "Step B" in html_str
        assert "PASS" in html_str
        assert "FAIL" in html_str
        assert "good" in html_str
        assert "bad" in html_str

    def test_contains_status_badges(self) -> None:
        results = [self._make_result(status=StepStatus.WARN)]
        html_str = css_results_table(results)
        assert "WARN" in html_str
        assert "#ffaa00" in html_str

    def test_criticality_column(self) -> None:
        result = RecipeResult(
            recipe_name="Test",
            step="Critical",
            step_index=0,
            total_steps=1,
            status=StepStatus.FAIL,
            criticality=StepCriticality.CRITICAL,
            detail="failed",
        )
        html_str = css_results_table([result])
        assert "critical" in html_str
