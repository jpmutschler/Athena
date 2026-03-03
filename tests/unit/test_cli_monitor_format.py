"""Tests for CLI formatting helpers."""

from __future__ import annotations

import pytest

from serialcables_switchtec.cli.monitor_format import (
    _extract_cli_metrics,
    format_result_line,
    format_step_header,
    format_summary_table,
)
from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowStepSummary,
    WorkflowSummary,
)


# ---------------------------------------------------------------------------
# format_step_header
# ---------------------------------------------------------------------------


class TestFormatStepHeader:
    def test_first_step(self) -> None:
        result = format_step_header(0, 3, "Cross-Hair Margin")
        assert result == "=== [1/3] Cross-Hair Margin ==="

    def test_last_step(self) -> None:
        result = format_step_header(2, 3, "Link Health")
        assert result == "=== [3/3] Link Health ==="


# ---------------------------------------------------------------------------
# format_result_line
# ---------------------------------------------------------------------------


class TestFormatResultLine:
    def _make_result(
        self,
        step: str = "Check",
        status: StepStatus = StepStatus.PASS,
        detail: str = "ok",
        data: dict | None = None,
    ) -> RecipeResult:
        return RecipeResult(
            recipe_name="Test",
            step=step,
            step_index=0,
            total_steps=1,
            status=status,
            detail=detail,
            data=data,
        )

    def test_pass_line(self) -> None:
        r = self._make_result(step="Check Link", detail="Link UP")
        line = format_result_line(r)
        assert "[PASS]" in line
        assert "Check Link" in line
        assert "Link UP" in line

    def test_fail_line(self) -> None:
        r = self._make_result(status=StepStatus.FAIL, detail="errors found")
        line = format_result_line(r)
        assert "[FAIL]" in line

    def test_inline_metrics(self) -> None:
        r = self._make_result(data={"temperature": 42.1, "errors": 0})
        line = format_result_line(r)
        assert "errors=0" in line
        assert "temperature=42.1" in line

    def test_strips_recipe_prefix(self) -> None:
        r = self._make_result(step="Cross-Hair Margin > Check Lane 0")
        line = format_result_line(r)
        assert "Check Lane 0" in line
        assert "Cross-Hair Margin >" not in line

    def test_no_data_no_metrics(self) -> None:
        r = self._make_result(data=None)
        line = format_result_line(r)
        assert "(" not in line or line.count("(") == 0

    def test_max_three_metrics(self) -> None:
        r = self._make_result(data={
            "total_errors": 0,
            "temperature": 42.1,
            "link_up": True,
            "ports_up": 10,
        })
        line = format_result_line(r)
        # Count metric entries (comma-separated inside parens)
        metrics_part = line.split("(")[-1].rstrip(")")
        assert metrics_part.count(",") <= 2


# ---------------------------------------------------------------------------
# _extract_cli_metrics
# ---------------------------------------------------------------------------


class TestExtractCliMetrics:
    def test_empty_data(self) -> None:
        assert _extract_cli_metrics(None) == ""
        assert _extract_cli_metrics({}) == ""

    def test_known_keys(self) -> None:
        result = _extract_cli_metrics({"temperature": 42.1, "total_errors": 5})
        assert "total_errors=5" in result
        assert "temperature=42.1" in result

    def test_unknown_keys_ignored(self) -> None:
        result = _extract_cli_metrics({"random_key": 42})
        assert result == ""

    def test_skips_nested_values(self) -> None:
        result = _extract_cli_metrics({"total_errors": 0, "lanes": [1, 2, 3]})
        assert "total_errors=0" in result
        assert "lanes" not in result

    def test_float_formatting(self) -> None:
        result = _extract_cli_metrics({"temperature": 42.123})
        assert "42.1" in result


# ---------------------------------------------------------------------------
# format_summary_table
# ---------------------------------------------------------------------------


class TestFormatSummaryTable:
    def _make_summary(
        self,
        aborted: bool = False,
        step_summaries: list[WorkflowStepSummary] | None = None,
    ) -> WorkflowSummary:
        if step_summaries is None:
            step_summaries = [
                WorkflowStepSummary(
                    step_index=0,
                    recipe_key="cross_hair_margin",
                    recipe_name="Cross-Hair Margin",
                    recipe_summary=RecipeSummary(
                        recipe_name="Cross-Hair Margin",
                        total_steps=2,
                        passed=2,
                        failed=0,
                        warnings=0,
                        skipped=0,
                        elapsed_s=1.5,
                        results=[],
                    ),
                ),
            ]
        return WorkflowSummary(
            workflow_name="Test Workflow",
            total_recipes=len(step_summaries),
            completed_recipes=sum(
                1 for s in step_summaries if not s.skipped
            ),
            step_summaries=step_summaries,
            aborted=aborted,
            elapsed_s=5.0,
        )

    def test_contains_workflow_name(self) -> None:
        result = format_summary_table(self._make_summary())
        assert "Test Workflow" in result

    def test_finished_verdict(self) -> None:
        result = format_summary_table(self._make_summary())
        assert "FINISHED" in result

    def test_aborted_verdict(self) -> None:
        result = format_summary_table(self._make_summary(aborted=True))
        assert "ABORTED" in result

    def test_contains_step_breakdown(self) -> None:
        result = format_summary_table(self._make_summary())
        assert "[1] Cross-Hair Margin" in result
        assert "2P 0F 0W" in result

    def test_skipped_step(self) -> None:
        steps = [
            WorkflowStepSummary(
                step_index=0,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                skipped=True,
                skip_reason="Condition not met",
            ),
        ]
        result = format_summary_table(self._make_summary(step_summaries=steps))
        assert "SKIPPED" in result
        assert "Condition not met" in result

    def test_bordered_format(self) -> None:
        result = format_summary_table(self._make_summary())
        lines = result.split("\n")
        assert lines[0].startswith("=")
        assert lines[-1].startswith("=")
