"""Tests for the workflow run report generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from serialcables_switchtec.core.workflows.export import DeviceContext
from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.workflow_models import (
    OnFailAction,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepSummary,
    WorkflowSummary,
)
from serialcables_switchtec.core.workflows.workflow_report import (
    WorkflowReportGenerator,
    WorkflowReportInput,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    step: str = "Check",
    status: StepStatus = StepStatus.PASS,
    detail: str = "ok",
    data: dict | None = None,
) -> RecipeResult:
    return RecipeResult(
        recipe_name="Test Recipe",
        step=step,
        step_index=0,
        total_steps=1,
        status=status,
        detail=detail,
        data=data,
    )


def _make_recipe_summary(
    passed: int = 2,
    failed: int = 0,
    warnings: int = 0,
    skipped: int = 0,
    results: list[RecipeResult] | None = None,
) -> RecipeSummary:
    if results is None:
        results = [_make_result() for _ in range(passed)]
    return RecipeSummary(
        recipe_name="Test Recipe",
        total_steps=len(results),
        passed=passed,
        failed=failed,
        warnings=warnings,
        skipped=skipped,
        elapsed_s=1.5,
        results=results,
    )


def _make_step_summary(
    step_index: int = 0,
    recipe_key: str = "cross_hair_margin",
    recipe_name: str = "Cross-Hair Margin",
    recipe_summary: RecipeSummary | None = None,
    skipped: bool = False,
    skip_reason: str = "",
) -> WorkflowStepSummary:
    return WorkflowStepSummary(
        step_index=step_index,
        recipe_key=recipe_key,
        recipe_name=recipe_name,
        recipe_summary=recipe_summary,
        skipped=skipped,
        skip_reason=skip_reason,
    )


def _make_report_input(
    step_summaries: list[WorkflowStepSummary] | None = None,
    aborted: bool = False,
    steps: list[WorkflowStep] | None = None,
) -> WorkflowReportInput:
    if step_summaries is None:
        step_summaries = [
            _make_step_summary(recipe_summary=_make_recipe_summary()),
        ]
    if steps is None:
        steps = [
            WorkflowStep(recipe_key=s.recipe_key) for s in step_summaries
        ]
    return WorkflowReportInput(
        workflow_summary=WorkflowSummary(
            workflow_name="Test Workflow",
            total_recipes=len(step_summaries),
            completed_recipes=sum(
                1 for s in step_summaries if not s.skipped and s.recipe_summary is not None
            ),
            step_summaries=step_summaries,
            aborted=aborted,
            elapsed_s=5.0,
        ),
        workflow_definition=WorkflowDefinition(
            name="Test Workflow",
            description="A test workflow",
            steps=steps,
        ),
        device_context=DeviceContext(
            device_path="/dev/switchtec0",
            name="PSX 48XG6",
            device_id=0x4000,
            generation="GEN5",
            fw_version="4.20",
            timestamp="2026-03-03T12:00:00+00:00",
        ),
        generated_at="2026-03-03T12:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkflowReportGenerator:
    def test_generate_returns_valid_html(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        html_str = gen.generate(report_input)
        assert html_str.startswith("<!DOCTYPE html>")
        assert "</html>" in html_str
        assert "<head>" in html_str
        assert "<body>" in html_str

    def test_header_contains_device_metadata(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        html_str = gen.generate(report_input)
        assert "PSX 48XG6" in html_str
        assert "GEN5" in html_str
        assert "4.20" in html_str

    def test_header_contains_workflow_name(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        html_str = gen.generate(report_input)
        assert "Test Workflow" in html_str

    def test_summary_dashboard_pass_fail_counts(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                step_index=0,
                recipe_summary=_make_recipe_summary(passed=3, failed=1, warnings=1),
            ),
            _make_step_summary(
                step_index=1,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                recipe_summary=_make_recipe_summary(passed=2, failed=0),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "Executive Summary" in html_str
        assert "FAILED" in html_str  # overall verdict

    def test_summary_dashboard_all_passing(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                recipe_summary=_make_recipe_summary(passed=2, failed=0),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "PASSED" in html_str

    def test_recipe_sections_present(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                step_index=0,
                recipe_summary=_make_recipe_summary(),
            ),
            _make_step_summary(
                step_index=1,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                recipe_summary=_make_recipe_summary(),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "Cross-Hair Margin" in html_str
        assert "BER Soak" in html_str
        assert "Recipe Results" in html_str

    def test_skipped_step_handled(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                step_index=0,
                recipe_summary=_make_recipe_summary(),
            ),
            _make_step_summary(
                step_index=1,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                skipped=True,
                skip_reason="Condition not met",
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "SKIPPED" in html_str
        assert "Condition not met" in html_str

    def test_aborted_workflow_shows_banner(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                recipe_summary=_make_recipe_summary(passed=1, failed=1),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums, aborted=True)
        html_str = gen.generate(report_input)
        assert "ABORTED" in html_str

    def test_loop_iterations_shown(self) -> None:
        gen = WorkflowReportGenerator()
        iter_summaries = [
            _make_recipe_summary(passed=2),
            _make_recipe_summary(passed=1, failed=1),
        ]
        step_sums = [
            WorkflowStepSummary(
                step_index=0,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                recipe_summary=iter_summaries[-1],
                loop_total=2,
                iteration_summaries=iter_summaries,
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "2 iterations" in html_str
        assert "Iteration 1" in html_str
        assert "Iteration 2" in html_str

    def test_workflow_config_section(self) -> None:
        gen = WorkflowReportGenerator()
        steps = [
            WorkflowStep(recipe_key="cross_hair_margin", label="Step A"),
            WorkflowStep(
                recipe_key="ber_soak",
                label="Step B",
                on_fail=OnFailAction.CONTINUE,
            ),
        ]
        step_sums = [
            _make_step_summary(step_index=0, recipe_summary=_make_recipe_summary()),
            _make_step_summary(
                step_index=1,
                recipe_key="ber_soak",
                recipe_name="BER Soak",
                recipe_summary=_make_recipe_summary(),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums, steps=steps)
        html_str = gen.generate(report_input)
        assert "Workflow Configuration" in html_str
        assert "Step A" in html_str
        assert "Step B" in html_str
        assert "continue" in html_str

    def test_generate_to_file(self, tmp_path: Path) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        path = gen.generate_to_file(report_input, tmp_path)
        assert path.exists()
        assert path.suffix == ".html"
        assert path.name.startswith("workflow_report_test_workflow_")
        content = path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_generate_to_file_creates_directory(self, tmp_path: Path) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        nested = tmp_path / "sub" / "dir"
        path = gen.generate_to_file(report_input, nested)
        assert path.exists()

    def test_footer_contains_timestamp(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        html_str = gen.generate(report_input)
        assert "2026-03-03" in html_str
        assert "Serialcables Switchtec" in html_str

    def test_css_included(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = _make_report_input()
        html_str = gen.generate(report_input)
        assert "<style>" in html_str
        assert "#1a1a2e" in html_str

    def test_html_escaping_in_names(self) -> None:
        gen = WorkflowReportGenerator()
        report_input = WorkflowReportInput(
            workflow_summary=WorkflowSummary(
                workflow_name="<script>alert(1)</script>",
                total_recipes=0,
                completed_recipes=0,
                step_summaries=[],
                elapsed_s=0,
            ),
            workflow_definition=WorkflowDefinition(
                name="<script>alert(1)</script>",
                steps=[],
            ),
            device_context=DeviceContext(
                device_path="",
                name="<device>",
                device_id=0,
                generation="",
                fw_version="",
                timestamp="",
            ),
            generated_at="now",
        )
        html_str = gen.generate(report_input)
        assert "<script>" not in html_str
        assert "&lt;script&gt;" in html_str

    def test_warnings_only_verdict(self) -> None:
        gen = WorkflowReportGenerator()
        step_sums = [
            _make_step_summary(
                recipe_summary=_make_recipe_summary(passed=2, warnings=1),
            ),
        ]
        report_input = _make_report_input(step_summaries=step_sums)
        html_str = gen.generate(report_input)
        assert "PASSED WITH WARNINGS" in html_str
