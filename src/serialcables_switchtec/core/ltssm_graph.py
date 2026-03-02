"""LTSSM state graph builder.

Constructs a directed graph of LTSSM state transitions from log entries.
Nodes are states, edges are transitions with counts and average durations.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StateTransition:
    """A directed edge in the LTSSM state graph.

    Attributes:
        from_state: Source LTSSM state.
        to_state: Destination LTSSM state.
        count: Number of times this transition occurred.
        avg_duration: Average timestamp delta for this transition.
    """

    from_state: str
    to_state: str
    count: int
    avg_duration: float


@dataclass(frozen=True)
class LtssmStateGraph:
    """Complete LTSSM state transition graph.

    Attributes:
        states: Unique states observed (sorted).
        transitions: Directed edges with counts and durations.
        state_counts: Number of visits per state.
    """

    states: list[str]
    transitions: list[StateTransition]
    state_counts: dict[str, int] = field(default_factory=dict)


def build_state_graph(entries: list[Any]) -> LtssmStateGraph:
    """Build a directed state graph from LTSSM log entries.

    Args:
        entries: List of LTSSM log entries.  Each must have
            ``link_state_str`` (str) and ``timestamp`` (int) attributes.

    Returns:
        ``LtssmStateGraph`` with states, transitions, and visit counts.
    """
    if not entries:
        return LtssmStateGraph(states=[], transitions=[], state_counts={})

    state_counts: Counter[str] = Counter()
    transition_counts: Counter[tuple[str, str]] = Counter()
    transition_durations: dict[tuple[str, str], list[float]] = {}

    for idx, entry in enumerate(entries):
        state_str = entry.link_state_str
        state_counts[state_str] += 1

        if idx + 1 < len(entries):
            next_entry = entries[idx + 1]
            next_state = next_entry.link_state_str

            # Exclude self-transitions
            if state_str != next_state:
                pair = (state_str, next_state)
                transition_counts[pair] += 1

                delta = max(0.0, float(next_entry.timestamp - entry.timestamp))
                if pair not in transition_durations:
                    transition_durations[pair] = []
                transition_durations[pair].append(delta)

    transitions = [
        StateTransition(
            from_state=pair[0],
            to_state=pair[1],
            count=count,
            avg_duration=(
                sum(transition_durations[pair]) / len(transition_durations[pair])
                if pair in transition_durations and transition_durations[pair]
                else 0.0
            ),
        )
        for pair, count in transition_counts.most_common()
    ]

    states = sorted(state_counts.keys())

    return LtssmStateGraph(
        states=states,
        transitions=transitions,
        state_counts=dict(state_counts),
    )
