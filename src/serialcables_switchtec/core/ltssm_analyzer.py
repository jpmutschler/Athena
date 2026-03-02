"""LTSSM recovery-path analysis for Switchtec link-training diagnostics.

Scans a sequence of LTSSM log entries for problematic patterns such as
recovery loops, detect-polling oscillations, and equalization stalls.
Produces a histogram of state durations and an overall pass/warn/fail verdict.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from serialcables_switchtec.bindings.constants import SwitchtecGen


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


@dataclass(frozen=True)
class DegradationInfo:
    """Detected link parameter degradation.

    Attributes:
        degradation_type: ``"speed"`` or ``"width"``.
        configured: Configured/max capability (e.g. ``"Gen5"`` or ``"x16"``).
        negotiated: Actual negotiated value (e.g. ``"Gen4"`` or ``"x8"``).
        severity: ``"warning"`` or ``"critical"``.
        description: Human-readable explanation.
    """

    degradation_type: str
    configured: str
    negotiated: str
    severity: str
    description: str


@dataclass(frozen=True)
class LtssmContextualAnalysis:
    """LTSSM analysis combined with link degradation context.

    Attributes:
        analysis: Base LTSSM pattern analysis.
        degradations: Detected speed/width degradations.
        overall_verdict: Combined verdict from patterns + degradation.
        overall_summary: Combined human-readable summary.
    """

    analysis: LtssmAnalysis
    degradations: list[DegradationInfo]
    overall_verdict: str
    overall_summary: str


# ---- Gen number extraction -----------------------------------------------


_GEN_PATTERN = re.compile(r"Gen(\d+)", re.IGNORECASE)


def _extract_gen_number(gen_str: str) -> int:
    """Extract generation number from a string like 'Gen5' or 'Gen4'."""
    match = _GEN_PATTERN.search(gen_str)
    return int(match.group(1)) if match else 0


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


def _is_l0s(state_str: str) -> bool:
    """Match L0s / TxL0s states."""
    return "L0s" in state_str or "TxL0s" in state_str


def _is_l1(state_str: str) -> bool:
    """Match L1 states, excluding combined L1/L2/L3 strings."""
    if "L1/L2" in state_str or "L1/L3" in state_str:
        return False
    return "L1" in state_str


def _is_compliance(state_str: str) -> bool:
    return "Compliance" in state_str


def _is_hot_reset(state_str: str) -> bool:
    return "Hot Reset" in state_str


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


def _detect_l1_exit_issues(
    entries: list[Any],
    min_cycles: int = 3,
) -> list[LtssmPattern]:
    """Detect L1->Recovery->L1 cycles without sustained L0.

    Counts transitions where the link leaves L1, enters Recovery, and returns
    to L1 (or never reaches sustained L0).  3+ such cycles indicate the link
    is unable to cleanly exit L1.
    """
    patterns: list[LtssmPattern] = []
    cycle_count = 0
    tracking_entries: list[Any] = []
    in_l1_phase = False

    for entry in entries:
        state_str = entry.link_state_str

        if _is_l1(state_str):
            if not in_l1_phase:
                cycle_count += 1
                in_l1_phase = True
            tracking_entries.append(entry)
        elif _is_recovery(state_str):
            in_l1_phase = False
            tracking_entries.append(entry)
        elif _is_l0(state_str):
            # Sustained L0 resets the cycle counter
            in_l1_phase = False
            if cycle_count >= min_cycles:
                patterns.append(LtssmPattern(
                    name="l1_exit_issues",
                    severity="warning",
                    occurrences=cycle_count,
                    description=(
                        f"L1 exit issues: {cycle_count} L1->Recovery->L1 "
                        f"cycles without sustained L0"
                    ),
                    entries=list(tracking_entries),
                ))
            cycle_count = 0
            tracking_entries = []
        else:
            in_l1_phase = False
            if cycle_count >= min_cycles:
                patterns.append(LtssmPattern(
                    name="l1_exit_issues",
                    severity="warning",
                    occurrences=cycle_count,
                    description=(
                        f"L1 exit issues: {cycle_count} L1->Recovery->L1 "
                        f"cycles without sustained L0"
                    ),
                    entries=list(tracking_entries),
                ))
            cycle_count = 0
            tracking_entries = []

    # Flush trailing
    if cycle_count >= min_cycles:
        patterns.append(LtssmPattern(
            name="l1_exit_issues",
            severity="warning",
            occurrences=cycle_count,
            description=(
                f"L1 exit issues: {cycle_count} L1->Recovery->L1 "
                f"cycles without sustained L0"
            ),
            entries=list(tracking_entries),
        ))

    return patterns


def _detect_l0s_oscillation(
    entries: list[Any],
    min_transitions: int = 10,
) -> list[LtssmPattern]:
    """Detect excessive L0<->L0s round-trips.

    Counts transitions between L0 and L0s.  10+ round-trips without
    leaving the L0/L0s pair suggest ASPM instability.
    """
    patterns: list[LtssmPattern] = []
    round_trips = 0
    tracking_entries: list[Any] = []
    last_was_l0 = False
    last_was_l0s = False

    for entry in entries:
        state_str = entry.link_state_str

        if _is_l0(state_str):
            if last_was_l0s:
                round_trips += 1
            tracking_entries.append(entry)
            last_was_l0 = True
            last_was_l0s = False
        elif _is_l0s(state_str):
            if last_was_l0:
                round_trips += 1
            tracking_entries.append(entry)
            last_was_l0 = False
            last_was_l0s = True
        else:
            if round_trips >= min_transitions:
                patterns.append(LtssmPattern(
                    name="l0s_oscillation",
                    severity="warning",
                    occurrences=round_trips,
                    description=(
                        f"L0s oscillation: {round_trips} L0<->L0s "
                        f"round-trips detected"
                    ),
                    entries=list(tracking_entries),
                ))
            round_trips = 0
            tracking_entries = []
            last_was_l0 = False
            last_was_l0s = False

    # Flush trailing
    if round_trips >= min_transitions:
        patterns.append(LtssmPattern(
            name="l0s_oscillation",
            severity="warning",
            occurrences=round_trips,
            description=(
                f"L0s oscillation: {round_trips} L0<->L0s "
                f"round-trips detected"
            ),
            entries=list(tracking_entries),
        ))

    return patterns


def _detect_compliance_mode(entries: list[Any]) -> list[LtssmPattern]:
    """Detect entries in Compliance mode.

    Any Compliance entry is flagged as warning; 2+ entries are critical
    (indicates link training fell back to compliance repeatedly).
    """
    compliance_entries = [e for e in entries if _is_compliance(e.link_state_str)]
    if not compliance_entries:
        return []

    count = len(compliance_entries)
    severity = "critical" if count >= 2 else "warning"
    return [LtssmPattern(
        name="compliance_mode",
        severity=severity,
        occurrences=count,
        description=(
            f"Compliance mode: {count} Compliance state "
            f"{'entries' if count > 1 else 'entry'} detected"
        ),
        entries=compliance_entries,
    )]


def _detect_hot_reset_storm(
    entries: list[Any],
    min_resets: int = 2,
) -> list[LtssmPattern]:
    """Detect Hot Reset storms.

    Counts distinct Hot Reset sequences.  2 resets -> warning, 3+ -> critical.
    """
    reset_entries = [e for e in entries if _is_hot_reset(e.link_state_str)]
    if len(reset_entries) < min_resets:
        return []

    count = len(reset_entries)
    severity = "critical" if count >= 3 else "warning"
    return [LtssmPattern(
        name="hot_reset_storm",
        severity=severity,
        occurrences=count,
        description=(
            f"Hot Reset storm: {count} Hot Reset sequences detected"
        ),
        entries=reset_entries,
    )]


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
            generation: Optional PCIe generation value (``SwitchtecGen``).
                When ``SwitchtecGen.GEN6``, an informational pattern about
                FLIT encoding is appended.

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
        patterns.extend(_detect_l1_exit_issues(entries))
        patterns.extend(_detect_l0s_oscillation(entries))
        patterns.extend(_detect_compliance_mode(entries))
        patterns.extend(_detect_hot_reset_storm(entries))

        # Gen6 FLIT encoding informational note
        if generation == SwitchtecGen.GEN6:
            patterns.append(LtssmPattern(
                name="gen6_flit_encoding",
                severity="info",
                occurrences=1,
                description=(
                    "Gen6 link uses FLIT encoding (68B mandatory). "
                    "Recovery EQ phases differ from Gen3-5 TLP framing — "
                    "longer EQ sequences may be expected during FLIT negotiation."
                ),
            ))

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

    def analyze_with_context(
        self,
        entries: list[Any],
        port_ctx: Any,
        generation: int | None = None,
    ) -> LtssmContextualAnalysis:
        """Analyze LTSSM entries with port context for degradation detection.

        Args:
            entries: LTSSM log entries.
            port_ctx: Object with ``link_up``, ``link_rate``,
                ``max_link_rate``, ``neg_lnk_width``, ``cfg_lnk_width``.
            generation: Optional PCIe generation for Gen6 FLIT note.

        Returns:
            ``LtssmContextualAnalysis`` with patterns, degradations, and
            combined verdict.
        """
        analysis = self.analyze(entries, generation=generation)
        degradations = _detect_degradations(port_ctx)

        # Combine verdict: worst of pattern verdict + degradation severity
        combined_verdict = analysis.verdict
        for deg in degradations:
            if deg.severity == "critical":
                combined_verdict = "FAIL"
                break
            if deg.severity == "warning" and combined_verdict == "CLEAN":
                combined_verdict = "WARN"

        # Build combined summary
        parts = [analysis.summary]
        if degradations:
            deg_strs = [
                f"{d.degradation_type}: {d.configured}->{d.negotiated}"
                for d in degradations
            ]
            parts.append(f"Degradation: {', '.join(deg_strs)}")
        overall_summary = "; ".join(parts)

        return LtssmContextualAnalysis(
            analysis=analysis,
            degradations=degradations,
            overall_verdict=combined_verdict,
            overall_summary=overall_summary,
        )


def _detect_degradations(port_ctx: Any) -> list[DegradationInfo]:
    """Compare negotiated vs configured link parameters.

    Args:
        port_ctx: Object with ``link_up``, ``link_rate``,
            ``max_link_rate``, ``neg_lnk_width``, ``cfg_lnk_width``.

    Returns:
        List of detected degradation issues.
    """
    if not port_ctx.link_up:
        return []

    degradations: list[DegradationInfo] = []

    # Speed degradation
    neg_gen = _extract_gen_number(str(port_ctx.link_rate))
    max_gen = _extract_gen_number(str(port_ctx.max_link_rate))

    if neg_gen > 0 and max_gen > 0 and neg_gen < max_gen:
        gen_drop = max_gen - neg_gen
        severity = "critical" if gen_drop >= 2 else "warning"
        degradations.append(DegradationInfo(
            degradation_type="speed",
            configured=str(port_ctx.max_link_rate),
            negotiated=str(port_ctx.link_rate),
            severity=severity,
            description=(
                f"Speed degradation: negotiated {port_ctx.link_rate} "
                f"vs configured {port_ctx.max_link_rate} "
                f"({gen_drop} gen drop)"
            ),
        ))

    # Width degradation
    neg_width = port_ctx.neg_lnk_width
    cfg_width = port_ctx.cfg_lnk_width

    if cfg_width > 0 and neg_width < cfg_width:
        utilization = neg_width / cfg_width
        # x4/x16 (25%) or worse is critical — severe bandwidth constraint
        severity = "critical" if utilization <= 0.25 else "warning"
        degradations.append(DegradationInfo(
            degradation_type="width",
            configured=f"x{cfg_width}",
            negotiated=f"x{neg_width}",
            severity=severity,
            description=(
                f"Width degradation: negotiated x{neg_width} "
                f"vs configured x{cfg_width} "
                f"({utilization:.0%} utilization)"
            ),
        ))

    return degradations


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
