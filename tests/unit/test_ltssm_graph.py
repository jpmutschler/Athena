"""Tests for LTSSM state graph builder."""

from __future__ import annotations

from unittest.mock import MagicMock

from serialcables_switchtec.core.ltssm_graph import (
    LtssmStateGraph,
    StateTransition,
    build_state_graph,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(state: str, timestamp: int = 0):
    entry = MagicMock()
    entry.link_state_str = state
    entry.timestamp = timestamp
    return entry


def _make_entries(*state_ts_pairs):
    """Create entries from (state, timestamp) pairs."""
    return [_make_entry(s, ts) for s, ts in state_ts_pairs]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildStateGraph:
    """Tests for the build_state_graph pure function."""

    def test_simple_transitions(self):
        entries = _make_entries(
            ("Detect", 0), ("Polling", 10), ("Config", 20), ("L0", 30),
        )
        graph = build_state_graph(entries)

        assert isinstance(graph, LtssmStateGraph)
        assert "Detect" in graph.states
        assert "Polling" in graph.states
        assert "Config" in graph.states
        assert "L0" in graph.states

        transition_pairs = {(t.from_state, t.to_state) for t in graph.transitions}
        assert ("Detect", "Polling") in transition_pairs
        assert ("Polling", "Config") in transition_pairs
        assert ("Config", "L0") in transition_pairs

    def test_repeated_transitions_counted(self):
        entries = _make_entries(
            ("L0", 0), ("Recovery", 10),
            ("L0", 20), ("Recovery", 30),
            ("L0", 40), ("Recovery", 50),
        )
        graph = build_state_graph(entries)

        l0_to_recovery = [
            t for t in graph.transitions
            if t.from_state == "L0" and t.to_state == "Recovery"
        ]
        assert len(l0_to_recovery) == 1
        assert l0_to_recovery[0].count == 3

    def test_self_transitions_excluded(self):
        entries = _make_entries(
            ("L0", 0), ("L0", 10), ("L0", 20), ("Recovery", 30),
        )
        graph = build_state_graph(entries)

        self_transitions = [
            t for t in graph.transitions
            if t.from_state == t.to_state
        ]
        assert len(self_transitions) == 0

    def test_empty_entries(self):
        graph = build_state_graph([])
        assert graph.states == []
        assert graph.transitions == []
        assert graph.state_counts == {}

    def test_state_counts_accuracy(self):
        entries = _make_entries(
            ("Detect", 0), ("Polling", 10),
            ("Detect", 20), ("Polling", 30),
            ("L0", 40),
        )
        graph = build_state_graph(entries)

        assert graph.state_counts["Detect"] == 2
        assert graph.state_counts["Polling"] == 2
        assert graph.state_counts["L0"] == 1

    def test_avg_duration_calculation(self):
        entries = _make_entries(
            ("L0", 0), ("Recovery", 10),   # L0->Recovery duration ~10
            ("L0", 20), ("Recovery", 40),  # L0->Recovery duration ~20
        )
        graph = build_state_graph(entries)

        l0_to_recovery = [
            t for t in graph.transitions
            if t.from_state == "L0" and t.to_state == "Recovery"
        ]
        assert len(l0_to_recovery) == 1
        # Average of 10 and 20 = 15.0
        assert l0_to_recovery[0].avg_duration == 15.0
