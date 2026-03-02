"""Tests for LTSSM path analyzer: histogram, pattern detection, and verdicts."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.core.ltssm_analyzer import (
    LtssmAnalysis,
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
