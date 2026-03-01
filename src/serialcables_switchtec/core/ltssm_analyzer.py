"""LTSSM recovery-path analysis for Switchtec link-training diagnostics.

Scans a sequence of LTSSM log entries for problematic patterns such as
recovery loops, detect-polling oscillations, and equalization stalls.
Produces a histogram of state durations and an overall pass/warn/fail verdict.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


# ---- Result data classes ------------------------------------------------


@dataclass(frozen=True)
class LtssmHistogramEntry:
    """Aggregated time spent in a given LTSSM state."""

    state: str
    count: int
    total_duration_estimate: float


@dataclass(frozen=True)
class LtssmPattern:
    """A detected problematic LTSSM state-machine pattern.

    Attributes:
        name: Machine identifier (``"recovery_loop"``, etc.).
        severity: ``"critical"``, ``"warning"``, or ``"info"``.
        occurrences: How many times the pattern appeared.
        description: Human-readable explanation.
        entries: The log entries that constitute the pattern instance.
    """

    name: str
    severity: str
    occurrences: int
    description: str
    entries: list[Any] = field(default_factory=list)


@dataclass(frozen=True)
class LtssmAnalysis:
    """Complete LTSSM analysis result.

    Attributes:
        total_transitions: Number of log entries processed.
        histogram: Per-state transition counts and estimated durations.
        patterns: Detected problematic patterns.
        verdict: ``"CLEAN"``, ``"WARN"``, or ``"FAIL"``.
        summary: Human-readable one-line summary.
    """

    total_transitions: int
    histogram: list[LtssmHistogramEntry]
    patterns: list[LtssmPattern]
    verdict: str
    summary: str


# ---- State classification helpers ----------------------------------------


def _is_recovery(state_str: str) -> bool:
    return "Recovery" in state_str


def _is_detect(state_str: str) -> bool:
    return "Detect" in state_str


def _is_polling(state_str: str) -> bool:
    return "Polling" in state_str


def _is_l0(state_str: str) -> bool:
    """Match L0 but not L0s (TxL0s, L0s)."""
    # Positive: "L0 (L0)", "L0 (ACTIVE)", "L0"
    # Negative: "TxL0s", "L0s"
    if "L0s" in state_str or "TxL0s" in state_str:
        return False
    return "L0" in state_str


def _is_eq(state_str: str) -> bool:
    return "EQ" in state_str or "Equalization" in state_str


# ---- Pattern detectors ---------------------------------------------------


def _detect_recovery_loops(
    entries: list[Any],
    min_consecutive: int = 3,
) -> list[LtssmPattern]:
    """Detect 3+ consecutive Recovery-state transitions without reaching L0."""
    patterns: list[LtssmPattern] = []
    run: list[Any] = []

    for entry in entries:
        state_str = entry.link_state_str
        if _is_recovery(state_str):
            run.append(entry)
        elif _is_l0(state_str):
            if len(run) >= min_consecutive:
                patterns.append(LtssmPattern(
                    name="recovery_loop",
                    severity="critical",
                    occurrences=1,
                    description=(
                        f"Recovery loop: {len(run)} consecutive Recovery "
                        f"transitions without reaching L0"
                    ),
                    entries=list(run),
                ))
            run = []
        else:
            # Non-Recovery, non-L0 state breaks the run
            if len(run) >= min_consecutive:
                patterns.append(LtssmPattern(
                    name="recovery_loop",
                    severity="critical",
                    occurrences=1,
                    description=(
                        f"Recovery loop: {len(run)} consecutive Recovery "
                        f"transitions without reaching L0"
                    ),
                    entries=list(run),
                ))
            run = []

    # Flush trailing run
    if len(run) >= min_consecutive:
        patterns.append(LtssmPattern(
            name="recovery_loop",
            severity="critical",
            occurrences=1,
            description=(
                f"Recovery loop: {len(run)} consecutive Recovery "
                f"transitions without reaching L0"
            ),
            entries=list(run),
        ))

    return patterns


def _detect_detect_polling_oscillation(
    entries: list[Any],
    min_cycles: int = 5,
) -> list[LtssmPattern]:
    """Detect Detect<->Polling oscillation without reaching L0.

    Counts alternations between Detect and Polling states.  If the number of
    alternation cycles exceeds *min_cycles* before an L0 is seen, the
    sequence is flagged.
    """
    patterns: list[LtssmPattern] = []
    alternation_entries: list[Any] = []
    cycle_count = 0
    last_group: str | None = None  # "detect" or "polling"

    for entry in entries:
        state_str = entry.link_state_str

        if _is_l0(state_str):
            if cycle_count >= min_cycles:
                patterns.append(LtssmPattern(
                    name="detect_polling_oscillation",
                    severity="warning",
                    occurrences=1,
                    description=(
                        f"Detect-Polling oscillation: {cycle_count} cycles "
                        f"before reaching L0"
                    ),
                    entries=list(alternation_entries),
                ))
            alternation_entries = []
            cycle_count = 0
            last_group = None
            continue

        current_group: str | None = None
        if _is_detect(state_str):
            current_group = "detect"
        elif _is_polling(state_str):
            current_group = "polling"
        else:
            # Non Detect/Polling/L0 state resets tracking
            if cycle_count >= min_cycles:
                patterns.append(LtssmPattern(
                    name="detect_polling_oscillation",
                    severity="warning",
                    occurrences=1,
                    description=(
                        f"Detect-Polling oscillation: {cycle_count} cycles "
                        f"without reaching L0"
                    ),
                    entries=list(alternation_entries),
                ))
            alternation_entries = []
            cycle_count = 0
            last_group = None
            continue

        alternation_entries.append(entry)
        if current_group != last_group and last_group is not None:
            cycle_count += 1
        last_group = current_group

    # Flush trailing sequence
    if cycle_count >= min_cycles:
        patterns.append(LtssmPattern(
            name="detect_polling_oscillation",
            severity="warning",
            occurrences=1,
            description=(
                f"Detect-Polling oscillation: {cycle_count} cycles "
                f"without reaching L0"
            ),
            entries=list(alternation_entries),
        ))

    return patterns


def _detect_eq_stuck(
    entries: list[Any],
    min_transitions: int = 10,
) -> list[LtssmPattern]:
    """Detect equalization stuck: >10 EQ transitions without reaching L0."""
    patterns: list[LtssmPattern] = []
    run: list[Any] = []

    for entry in entries:
        state_str = entry.link_state_str
        if _is_eq(state_str) or _is_recovery(state_str):
            # Both EQ and adjacent Recovery states are part of the same training
            run.append(entry)
        elif _is_l0(state_str):
            eq_only = [e for e in run if _is_eq(e.link_state_str)]
            if len(eq_only) > min_transitions:
                patterns.append(LtssmPattern(
                    name="eq_stuck",
                    severity="critical",
                    occurrences=1,
                    description=(
                        f"Equalization stuck: {len(eq_only)} EQ transitions "
                        f"without reaching L0"
                    ),
                    entries=list(run),
                ))
            run = []
        else:
            eq_only = [e for e in run if _is_eq(e.link_state_str)]
            if len(eq_only) > min_transitions:
                patterns.append(LtssmPattern(
                    name="eq_stuck",
                    severity="critical",
                    occurrences=1,
                    description=(
                        f"Equalization stuck: {len(eq_only)} EQ transitions "
                        f"without reaching L0"
                    ),
                    entries=list(run),
                ))
            run = []

    # Flush trailing run
    eq_only = [e for e in run if _is_eq(e.link_state_str)]
    if len(eq_only) > min_transitions:
        patterns.append(LtssmPattern(
            name="eq_stuck",
            severity="critical",
            occurrences=1,
            description=(
                f"Equalization stuck: {len(eq_only)} EQ transitions "
                f"without reaching L0"
            ),
            entries=list(run),
        ))

    return patterns


# ---- Histogram builder ---------------------------------------------------


def _build_histogram(entries: list[Any]) -> list[LtssmHistogramEntry]:
    """Build a histogram of state transitions with estimated durations.

    Duration is estimated from consecutive timestamp deltas.  The last entry
    in a run has no successor, so its duration contribution is zero.
    """
    state_counts: Counter[str] = Counter()
    state_durations: Counter[str] = Counter()

    for idx, entry in enumerate(entries):
        state_str = entry.link_state_str
        state_counts[state_str] += 1

        if idx + 1 < len(entries):
            next_ts = entries[idx + 1].timestamp
            delta = max(0.0, float(next_ts - entry.timestamp))
            state_durations[state_str] += delta

    histogram = [
        LtssmHistogramEntry(
            state=state,
            count=count,
            total_duration_estimate=float(state_durations.get(state, 0.0)),
        )
        for state, count in state_counts.most_common()
    ]
    return histogram


# ---- Main analyzer -------------------------------------------------------


class LtssmPathAnalyzer:
    """Stateless LTSSM log analyzer.

    Scans a list of LTSSM log entries for problematic link-training patterns
    and produces a histogram plus an overall verdict.

    Usage::

        analyzer = LtssmPathAnalyzer()
        result = analyzer.analyze(ltssm_entries)
        print(result.verdict, result.summary)
    """

    def analyze(
        self,
        entries: list[Any],
        generation: int | None = None,
    ) -> LtssmAnalysis:
        """Analyze LTSSM log entries for problematic patterns.

        Args:
            entries: List of LTSSM log entries.  Each entry must have
                ``link_state_str`` (str), ``link_rate``, ``link_width`` (int),
                and ``timestamp`` (int) attributes.
            generation: Optional PCIe generation hint (unused today, reserved
                for future generation-specific heuristics).

        Returns:
            An ``LtssmAnalysis`` containing histogram, detected patterns,
            verdict, and summary.
        """
        if not entries:
            return LtssmAnalysis(
                total_transitions=0,
                histogram=[],
                patterns=[],
                verdict="CLEAN",
                summary="No LTSSM log entries to analyze",
            )

        histogram = _build_histogram(entries)

        # Run all pattern detectors
        patterns: list[LtssmPattern] = []
        patterns.extend(_detect_recovery_loops(entries))
        patterns.extend(_detect_detect_polling_oscillation(entries))
        patterns.extend(_detect_eq_stuck(entries))

        # Determine verdict from highest severity
        verdict = _compute_verdict(patterns)

        # Build summary
        summary = _build_summary(entries, patterns, verdict)

        return LtssmAnalysis(
            total_transitions=len(entries),
            histogram=histogram,
            patterns=patterns,
            verdict=verdict,
            summary=summary,
        )


def _compute_verdict(patterns: list[LtssmPattern]) -> str:
    """Derive overall verdict from the highest-severity pattern found."""
    if not patterns:
        return "CLEAN"

    severities = {p.severity for p in patterns}
    if "critical" in severities:
        return "FAIL"
    if "warning" in severities:
        return "WARN"
    return "CLEAN"


def _build_summary(
    entries: list[Any],
    patterns: list[LtssmPattern],
    verdict: str,
) -> str:
    """Build a one-line human-readable summary."""
    total = len(entries)
    pattern_count = len(patterns)

    if verdict == "CLEAN":
        return f"{total} transitions analyzed, no problematic patterns detected"

    pattern_names = sorted({p.name for p in patterns})
    names_str = ", ".join(pattern_names)
    return (
        f"{total} transitions analyzed, {pattern_count} pattern(s) "
        f"detected ({names_str}), verdict: {verdict}"
    )
