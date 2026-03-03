"""Tests for recipe-specific HTML section renderers."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.core.workflows.report_sections import (
    _SECTION_RENDERERS,
    _render_generic_section,
    render_recipe_section,
)
from serialcables_switchtec.core.workflows.workflow_models import WorkflowStepSummary


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


def _make_step_summary(
    recipe_key: str = "unknown_recipe",
    results: list[RecipeResult] | None = None,
    skipped: bool = False,
    skip_reason: str = "",
) -> WorkflowStepSummary:
    if results is None:
        results = [_make_result()]
    summary = RecipeSummary(
        recipe_name="Test Recipe",
        total_steps=len(results),
        passed=sum(1 for r in results if r.status == StepStatus.PASS),
        failed=sum(1 for r in results if r.status == StepStatus.FAIL),
        warnings=sum(1 for r in results if r.status == StepStatus.WARN),
        skipped=sum(1 for r in results if r.status == StepStatus.SKIP),
        elapsed_s=1.0,
        results=results,
    )
    return WorkflowStepSummary(
        step_index=0,
        recipe_key=recipe_key,
        recipe_name="Test Recipe",
        recipe_summary=None if skipped else summary,
        skipped=skipped,
        skip_reason=skip_reason,
    )


# ---------------------------------------------------------------------------
# Registry dispatch
# ---------------------------------------------------------------------------


class TestRenderRecipeSection:
    def test_dispatch_to_registered_renderer(self) -> None:
        step_summary = _make_step_summary(recipe_key="cross_hair_margin")
        result = render_recipe_section(step_summary)
        assert isinstance(result, str)
        assert "<table>" in result

    def test_generic_fallback_for_unknown_key(self) -> None:
        step_summary = _make_step_summary(recipe_key="nonexistent_recipe")
        result = render_recipe_section(step_summary)
        assert isinstance(result, str)
        assert "<table>" in result

    def test_all_priority_renderers_registered(self) -> None:
        expected = {
            "cross_hair_margin",
            "ber_soak",
            "bandwidth_baseline",
            "all_port_sweep",
            "eye_quick_scan",
            "ltssm_monitor",
        }
        assert expected == set(_SECTION_RENDERERS.keys())


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


class TestGenericSection:
    def test_renders_results_table(self) -> None:
        step_summary = _make_step_summary()
        result = _render_generic_section(step_summary)
        assert "<table>" in result
        assert "PASS" in result

    def test_no_summary_shows_message(self) -> None:
        step_summary = _make_step_summary(skipped=True, skip_reason="Condition not met")
        result = _render_generic_section(step_summary)
        assert "No results" in result

    def test_multiple_results(self) -> None:
        results = [
            _make_result(step="Step 1", status=StepStatus.PASS),
            _make_result(step="Step 2", status=StepStatus.FAIL, detail="error"),
        ]
        step_summary = _make_step_summary(results=results)
        html_str = _render_generic_section(step_summary)
        assert "Step 1" in html_str
        assert "Step 2" in html_str


# ---------------------------------------------------------------------------
# Cross-hair margin
# ---------------------------------------------------------------------------


class TestCrossHairMargin:
    def test_renders_lane_bars(self) -> None:
        results = [
            _make_result(data={
                "lanes": [
                    {"lane": 0, "h_margin": 0.15, "v_margin": 0.20},
                    {"lane": 1, "h_margin": 0.12, "v_margin": 0.18},
                ],
            }),
        ]
        step_summary = _make_step_summary(recipe_key="cross_hair_margin", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Lane 0" in html_str
        assert "Lane 1" in html_str
        assert "Horizontal Margin" in html_str
        assert "Vertical Margin" in html_str

    def test_no_lanes_data(self) -> None:
        step_summary = _make_step_summary(recipe_key="cross_hair_margin")
        html_str = render_recipe_section(step_summary)
        assert "<table>" in html_str  # still gets generic table


# ---------------------------------------------------------------------------
# BER soak
# ---------------------------------------------------------------------------


class TestBerSoak:
    def test_renders_error_cards(self) -> None:
        results = [
            _make_result(data={
                "total_errors": 0,
                "lane_errors": [
                    {"lane": 0, "errors": 0},
                    {"lane": 1, "errors": 5},
                ],
            }),
        ]
        step_summary = _make_step_summary(recipe_key="ber_soak", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Total Errors" in html_str
        assert "Per-Lane Errors" in html_str


# ---------------------------------------------------------------------------
# Bandwidth baseline
# ---------------------------------------------------------------------------


class TestBandwidthBaseline:
    def test_renders_bandwidth_cards(self) -> None:
        # Data mirrors what the BandwidthBaseline recipe actually emits:
        # both raw byte stats and computed Mbps stats
        results = [
            _make_result(data={
                "egress_avg": 625000000,
                "egress_min": 562500000,
                "egress_max": 687500000,
                "ingress_avg": 600000000,
                "ingress_min": 525000000,
                "ingress_max": 650000000,
                "egress_avg_mbps": 5000,
                "egress_min_mbps": 4500,
                "egress_max_mbps": 5500,
                "ingress_avg_mbps": 4800,
                "ingress_min_mbps": 4200,
                "ingress_max_mbps": 5200,
                "sample_count": 10,
            }),
        ]
        step_summary = _make_step_summary(recipe_key="bandwidth_baseline", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Egress Avg" in html_str
        assert "Ingress Avg" in html_str
        assert "MB/s" in html_str
        assert "Egress Bandwidth" in html_str


# ---------------------------------------------------------------------------
# All port sweep
# ---------------------------------------------------------------------------


class TestAllPortSweep:
    def test_renders_port_summary(self) -> None:
        results = [
            _make_result(data={
                "total_ports": 10,
                "ports_up": 8,
                "ports_down": 2,
            }),
        ]
        step_summary = _make_step_summary(recipe_key="all_port_sweep", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Total Ports" in html_str
        assert "Ports UP" in html_str
        assert "Ports DOWN" in html_str

    def test_renders_port_table(self) -> None:
        results = [
            _make_result(data={
                "total_ports": 2,
                "ports_up": 1,
                "ports_down": 1,
                "ports": [
                    {"port_id": 0, "link_up": True, "rate": "32 GT/s", "width": "x16"},
                    {"port_id": 1, "link_up": False, "rate": "-", "width": "-"},
                ],
            }),
        ]
        step_summary = _make_step_summary(recipe_key="all_port_sweep", results=results)
        html_str = render_recipe_section(step_summary)
        assert "UP" in html_str
        assert "DOWN" in html_str


# ---------------------------------------------------------------------------
# Eye quick scan
# ---------------------------------------------------------------------------


class TestEyeQuickScan:
    def test_renders_eye_metrics(self) -> None:
        results = [
            _make_result(data={
                "eye_width": 32,
                "eye_height": 120,
                "eye_area_pct": 85.5,
            }),
        ]
        step_summary = _make_step_summary(recipe_key="eye_quick_scan", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Eye Width" in html_str
        assert "Eye Height" in html_str
        assert "Eye Area" in html_str
        assert "85.5%" in html_str


# ---------------------------------------------------------------------------
# LTSSM monitor
# ---------------------------------------------------------------------------


class TestLtssmMonitor:
    def test_renders_patterns_and_verdict(self) -> None:
        results = [
            _make_result(data={
                "patterns_detected": [
                    {"name": "Flapping", "severity": "critical", "count": 3},
                ],
                "transition_count": 42,
                "verdict": "FAIL",
            }),
        ]
        step_summary = _make_step_summary(recipe_key="ltssm_monitor", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Patterns Detected" in html_str
        assert "Flapping" in html_str
        assert "Transitions" in html_str
        assert "FAIL" in html_str


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_data_dict(self) -> None:
        results = [_make_result(data={})]
        step_summary = _make_step_summary(recipe_key="ber_soak", results=results)
        html_str = render_recipe_section(step_summary)
        assert isinstance(html_str, str)

    def test_none_data(self) -> None:
        results = [_make_result(data=None)]
        step_summary = _make_step_summary(recipe_key="cross_hair_margin", results=results)
        html_str = render_recipe_section(step_summary)
        assert isinstance(html_str, str)

    def test_missing_nested_keys(self) -> None:
        results = [_make_result(data={"lanes": [{"lane": 0}]})]
        step_summary = _make_step_summary(recipe_key="cross_hair_margin", results=results)
        html_str = render_recipe_section(step_summary)
        assert "Lane 0" in html_str
