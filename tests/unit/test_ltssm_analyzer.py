"""Tests for LTSSM path analyzer: histogram, pattern detection, and verdicts."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.core.ltssm_analyzer import (
    DegradationInfo,
    LtssmAnalysis,
    LtssmContextualAnalysis,
    LtssmHistogramEntry,
    LtssmPathAnalyzer,
    LtssmPattern,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(state: str, rate: str = "Gen6", width: str = "x16", timestamp: int = 0):
    """Create a mock LTSSM log entry with the given state string."""
    entry = MagicMock()
    entry.link_state_str = state
    entry.link_rate = rate
    entry.link_width = width
    entry.timestamp = timestamp
    return entry


def _make_entries(*states: str) -> list:
    """Create a list of mock LTSSM log entries from state name strings.

    Assigns sequential timestamps (0, 1, 2, ...) so the histogram builder
    can compute duration estimates.
    """
    return [_make_entry(s, timestamp=i) for i, s in enumerate(states)]


# ---------------------------------------------------------------------------
# Basic analysis
# ---------------------------------------------------------------------------


class TestEmptyAndSingleEntry:
    """Tests for trivial input cases."""

    def test_empty_entries_clean_verdict(self):
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze([])
        assert isinstance(result, LtssmAnalysis)
        assert result.verdict == "CLEAN"
        assert result.total_transitions == 0

    def test_single_l0_entry_clean(self):
        entries = _make_entries("L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        assert result.verdict == "CLEAN"

    def test_analysis_summary_non_empty(self):
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze([])
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------


class TestHistogram:
    """Tests for state histogram computation."""

    def test_histogram_counts_states(self):
        entries = _make_entries("L0", "Recovery", "L0", "L0", "Recovery")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        histogram_map = {h.state: h.count for h in result.histogram}
        assert histogram_map["L0"] == 3
        assert histogram_map["Recovery"] == 2

    def test_histogram_entries_are_correct_type(self):
        entries = _make_entries("L0", "Detect")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        for h in result.histogram:
            assert isinstance(h, LtssmHistogramEntry)


# ---------------------------------------------------------------------------
# Recovery loop detection
# ---------------------------------------------------------------------------


class TestRecoveryLoopDetection:
    """Tests for detecting consecutive Recovery state loops."""

    def test_recovery_loop_detected(self):
        # 3+ consecutive Recovery states should trigger a recovery_loop pattern
        entries = _make_entries("L0", "Recovery", "Recovery", "Recovery", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        assert "recovery_loop" in pattern_names

    def test_no_recovery_loop_with_only_two(self):
        # Only 2 consecutive Recovery states should not trigger
        entries = _make_entries("L0", "Recovery", "Recovery", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        assert "recovery_loop" not in pattern_names


# ---------------------------------------------------------------------------
# Detect-Polling oscillation
# ---------------------------------------------------------------------------


class TestDetectPollingOscillation:
    """Tests for detecting Detect/Polling oscillation without reaching L0."""

    def test_detect_polling_oscillation(self):
        # >5 alternating Detect/Polling without ever reaching L0
        entries = _make_entries(
            "Detect", "Polling", "Detect", "Polling",
            "Detect", "Polling", "Detect", "Polling",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        assert any("polling" in n or "oscillation" in n for n in pattern_names), (
            f"Expected detect-polling oscillation pattern, got: {pattern_names}"
        )

    def test_detect_polling_with_l0_no_oscillation(self):
        # Detect -> Polling -> L0 is a normal link-up sequence
        entries = _make_entries("Detect", "Polling", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        oscillation_found = any(
            "polling" in n or "oscillation" in n for n in pattern_names
        )
        assert not oscillation_found, (
            f"Should not detect oscillation with L0 present, got: {pattern_names}"
        )


# ---------------------------------------------------------------------------
# EQ stuck detection
# ---------------------------------------------------------------------------


class TestEqStuckDetection:
    """Tests for equalization stuck detection."""

    def test_eq_stuck_detected(self):
        # >10 EQ transitions without L0 suggests equalization is stuck
        eq_states = ["EQ"] * 12
        entries = _make_entries(*eq_states)
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        assert any("eq" in n.lower() and "stuck" in n.lower() for n in pattern_names), (
            f"Expected eq_stuck pattern, got: {pattern_names}"
        )

    def test_eq_not_stuck_with_l0_between(self):
        # EQ states interspersed with L0 should not trigger eq_stuck
        entries = _make_entries("EQ", "EQ", "L0", "EQ", "EQ", "L0", "EQ", "EQ")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        eq_stuck_found = any(
            "eq" in n.lower() and "stuck" in n.lower() for n in pattern_names
        )
        assert not eq_stuck_found, (
            f"Should not detect eq_stuck with L0 interspersed, got: {pattern_names}"
        )


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


class TestVerdictLogic:
    """Tests for the overall verdict based on detected patterns."""

    def test_verdict_fail_for_critical_patterns(self):
        # Recovery loop is critical severity -> FAIL verdict
        entries = _make_entries(
            "L0", "Recovery", "Recovery", "Recovery", "Recovery",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        assert result.verdict == "FAIL"

    def test_verdict_warn_for_warning_patterns(self):
        # Detect-Polling oscillation is warning severity -> WARN verdict
        entries = _make_entries(
            "Detect", "Polling", "Detect", "Polling",
            "Detect", "Polling", "Detect", "Polling",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        assert result.verdict in ("WARN", "FAIL")

    def test_multiple_patterns_detected(self):
        # Mix of recovery loop and oscillation -> both detected
        entries = _make_entries(
            "Detect", "Polling", "Detect", "Polling",
            "Detect", "Polling", "Detect", "Polling",
            "Recovery", "Recovery", "Recovery",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)

        pattern_names = [p.name for p in result.patterns]
        has_recovery = "recovery_loop" in pattern_names
        has_oscillation = any(
            "polling" in n or "oscillation" in n for n in pattern_names
        )
        assert has_recovery and has_oscillation, (
            f"Expected both recovery and oscillation patterns, got: {pattern_names}"
        )


# ---------------------------------------------------------------------------
# Dataclass contracts
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gen6 FLIT encoding pattern
# ---------------------------------------------------------------------------


class TestGen6FlitPattern:
    """Tests for Gen6 FLIT encoding informational pattern."""

    def test_gen6_adds_flit_pattern(self):
        entries = _make_entries("L0", "Recovery", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries, generation=SwitchtecGen.GEN6)

        pattern_names = [p.name for p in result.patterns]
        assert "gen6_flit_encoding" in pattern_names

    def test_gen6_flit_pattern_is_info_severity(self):
        entries = _make_entries("L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries, generation=SwitchtecGen.GEN6)

        flit_patterns = [p for p in result.patterns if p.name == "gen6_flit_encoding"]
        assert len(flit_patterns) == 1
        assert flit_patterns[0].severity == "info"

    def test_gen6_flit_does_not_affect_clean_verdict(self):
        """Info-severity pattern should not change verdict from CLEAN."""
        entries = _make_entries("L0", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries, generation=SwitchtecGen.GEN6)
        assert result.verdict == "CLEAN"

    def test_gen5_does_not_add_flit_pattern(self):
        entries = _make_entries("L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries, generation=SwitchtecGen.GEN5)

        pattern_names = [p.name for p in result.patterns]
        assert "gen6_flit_encoding" not in pattern_names

    def test_no_generation_no_flit_pattern(self):
        entries = _make_entries("L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries, generation=None)

        pattern_names = [p.name for p in result.patterns]
        assert "gen6_flit_encoding" not in pattern_names


class TestDataclassContracts:
    """Tests for frozen dataclass structure of analysis types."""

    def test_ltssm_pattern_is_frozen(self):
        pattern = LtssmPattern(
            name="test",
            severity="warning",
            occurrences=1,
            description="A test pattern",
            entries=[],
        )
        with pytest.raises(AttributeError):
            pattern.name = "mutated"

    def test_ltssm_histogram_entry_is_frozen(self):
        entry = LtssmHistogramEntry(
            state="L0",
            count=5,
            total_duration_estimate=0.0,
        )
        with pytest.raises(AttributeError):
            entry.count = 10

    def test_degradation_info_is_frozen(self):
        info = DegradationInfo(
            degradation_type="speed",
            configured="Gen5",
            negotiated="Gen4",
            severity="warning",
            description="test",
        )
        with pytest.raises(AttributeError):
            info.severity = "critical"

    def test_contextual_analysis_is_frozen(self):
        analysis = LtssmAnalysis(
            total_transitions=0, histogram=[], patterns=[],
            verdict="CLEAN", summary="test",
        )
        ctx = LtssmContextualAnalysis(
            analysis=analysis, degradations=[],
            overall_verdict="CLEAN", overall_summary="test",
        )
        with pytest.raises(AttributeError):
            ctx.overall_verdict = "FAIL"


# ---------------------------------------------------------------------------
# L1 exit issues detection
# ---------------------------------------------------------------------------


class TestL1ExitIssues:
    """Tests for L1->Recovery->L1 cycle detection without sustained L0."""

    def test_l1_exit_issues_detected(self):
        """3+ L1->Recovery->L1 cycles should flag l1_exit_issues."""
        entries = _make_entries(
            "L1", "Recovery", "L1",
            "Recovery", "L1",
            "Recovery", "L1",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "l1_exit_issues" in pattern_names

    def test_sustained_l0_breaks_l1_cycle(self):
        """L1->Recovery->L0 (sustained) should not trigger l1_exit_issues."""
        entries = _make_entries(
            "L1", "Recovery", "L0", "L0", "L0",
            "L1", "Recovery", "L0", "L0", "L0",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "l1_exit_issues" not in pattern_names

    def test_single_l1_recovery_cycle_ok(self):
        """A single L1->Recovery cycle is normal and should not flag."""
        entries = _make_entries("L1", "Recovery", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "l1_exit_issues" not in pattern_names

    def test_l1_exit_issues_severity_is_warning(self):
        entries = _make_entries(
            "L1", "Recovery", "L1",
            "Recovery", "L1",
            "Recovery", "L1",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        l1_patterns = [p for p in result.patterns if p.name == "l1_exit_issues"]
        assert len(l1_patterns) == 1
        assert l1_patterns[0].severity == "warning"


# ---------------------------------------------------------------------------
# L0s oscillation detection
# ---------------------------------------------------------------------------


class TestL0sOscillation:
    """Tests for excessive L0<->L0s round-trips."""

    def test_l0s_oscillation_detected(self):
        """10+ L0<->L0s round-trips should flag l0s_oscillation."""
        states = []
        for _ in range(12):
            states.extend(["L0", "L0s"])
        entries = _make_entries(*states)
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "l0s_oscillation" in pattern_names

    def test_normal_l0s_usage_no_flag(self):
        """A few L0<->L0s transitions are normal ASPM behavior."""
        entries = _make_entries("L0", "L0s", "L0", "L0s", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "l0s_oscillation" not in pattern_names

    def test_l0s_oscillation_severity_is_warning(self):
        states = []
        for _ in range(12):
            states.extend(["L0", "L0s"])
        entries = _make_entries(*states)
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        l0s_patterns = [p for p in result.patterns if p.name == "l0s_oscillation"]
        assert len(l0s_patterns) == 1
        assert l0s_patterns[0].severity == "warning"


# ---------------------------------------------------------------------------
# Compliance mode detection
# ---------------------------------------------------------------------------


class TestComplianceMode:
    """Tests for Compliance state detection."""

    def test_single_compliance_entry_warning(self):
        entries = _make_entries("Detect", "Polling", "Compliance", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        comp_patterns = [p for p in result.patterns if p.name == "compliance_mode"]
        assert len(comp_patterns) == 1
        assert comp_patterns[0].severity == "warning"

    def test_repeated_compliance_critical(self):
        entries = _make_entries(
            "Detect", "Compliance", "Detect", "Compliance", "L0",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        comp_patterns = [p for p in result.patterns if p.name == "compliance_mode"]
        assert len(comp_patterns) == 1
        assert comp_patterns[0].severity == "critical"

    def test_no_compliance_clean(self):
        entries = _make_entries("Detect", "Polling", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "compliance_mode" not in pattern_names


# ---------------------------------------------------------------------------
# Hot reset storm detection
# ---------------------------------------------------------------------------


class TestHotResetStorm:
    """Tests for Hot Reset storm detection."""

    def test_two_hot_resets_warning(self):
        entries = _make_entries(
            "L0", "Hot Reset", "L0", "Hot Reset", "L0",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        hr_patterns = [p for p in result.patterns if p.name == "hot_reset_storm"]
        assert len(hr_patterns) == 1
        assert hr_patterns[0].severity == "warning"

    def test_three_plus_hot_resets_critical(self):
        entries = _make_entries(
            "L0", "Hot Reset", "L0", "Hot Reset", "L0", "Hot Reset", "L0",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        hr_patterns = [p for p in result.patterns if p.name == "hot_reset_storm"]
        assert len(hr_patterns) == 1
        assert hr_patterns[0].severity == "critical"

    def test_single_hot_reset_no_pattern(self):
        entries = _make_entries("L0", "Hot Reset", "L0")
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(entries)
        pattern_names = [p.name for p in result.patterns]
        assert "hot_reset_storm" not in pattern_names


# ---------------------------------------------------------------------------
# Speed/width degradation detection (Phase 2)
# ---------------------------------------------------------------------------


class TestDegradationDetection:
    """Tests for speed and width degradation detection."""

    def _make_port_ctx(
        self,
        link_up=True,
        link_rate="Gen4",
        max_link_rate="Gen5",
        neg_lnk_width=8,
        cfg_lnk_width=16,
    ):
        ctx = MagicMock()
        ctx.link_up = link_up
        ctx.link_rate = link_rate
        ctx.max_link_rate = max_link_rate
        ctx.neg_lnk_width = neg_lnk_width
        ctx.cfg_lnk_width = cfg_lnk_width
        return ctx

    def test_speed_degradation_one_gen_drop_warning(self):
        """Gen5 configured but negotiated Gen4 -> warning."""
        entries = _make_entries("L0", "L0")
        port_ctx = self._make_port_ctx(
            link_rate="Gen4", max_link_rate="Gen5",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        assert isinstance(result, LtssmContextualAnalysis)
        speed_degs = [d for d in result.degradations if d.degradation_type == "speed"]
        assert len(speed_degs) == 1
        assert speed_degs[0].severity == "warning"
        assert speed_degs[0].configured == "Gen5"
        assert speed_degs[0].negotiated == "Gen4"

    def test_speed_degradation_two_gen_drop_critical(self):
        """Gen5 configured but negotiated Gen3 -> critical."""
        entries = _make_entries("L0")
        port_ctx = self._make_port_ctx(
            link_rate="Gen3", max_link_rate="Gen5",
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        speed_degs = [d for d in result.degradations if d.degradation_type == "speed"]
        assert len(speed_degs) == 1
        assert speed_degs[0].severity == "critical"

    def test_width_degradation_x16_to_x4_critical(self):
        """x16 configured but negotiated x4 -> critical (25% utilization)."""
        entries = _make_entries("L0")
        port_ctx = self._make_port_ctx(
            neg_lnk_width=4, cfg_lnk_width=16,
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        width_degs = [d for d in result.degradations if d.degradation_type == "width"]
        assert len(width_degs) == 1
        assert width_degs[0].severity == "critical"

    def test_link_down_skips_degradation_checks(self):
        """When link is down, no degradation checks should run."""
        entries = _make_entries("Detect")
        port_ctx = self._make_port_ctx(
            link_up=False, link_rate="Gen1", max_link_rate="Gen5",
            neg_lnk_width=0, cfg_lnk_width=16,
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        assert result.degradations == []

    def test_no_degradation_full_speed_and_width(self):
        """No degradation when running at configured speed and width."""
        entries = _make_entries("L0")
        port_ctx = self._make_port_ctx(
            link_rate="Gen5", max_link_rate="Gen5",
            neg_lnk_width=16, cfg_lnk_width=16,
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        assert result.degradations == []
        assert result.overall_verdict == "CLEAN"

    def test_combined_speed_and_width_degradation(self):
        """Both speed and width degraded should both appear."""
        entries = _make_entries("L0")
        port_ctx = self._make_port_ctx(
            link_rate="Gen3", max_link_rate="Gen5",
            neg_lnk_width=4, cfg_lnk_width=16,
        )
        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze_with_context(entries, port_ctx)

        types = {d.degradation_type for d in result.degradations}
        assert "speed" in types
        assert "width" in types
        assert result.overall_verdict == "FAIL"
