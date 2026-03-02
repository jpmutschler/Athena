"""LTSSM Event-Triggered Capture recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.ltssm_analyzer import LtssmPathAnalyzer
from serialcables_switchtec.core.ltssm_capture import EventTriggeredCapture
from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.models import (
    RecipeCategory,
    RecipeParameter,
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)
from serialcables_switchtec.exceptions import SwitchtecError

_DEFAULT_DURATION = 120
_DEFAULT_EVENT_TIMEOUT = 5000


class LtssmEventCapture(Recipe):
    name = "LTSSM Event-Triggered Capture"
    description = (
        "Arm a hardware event (PFF_LINK_STATE) and capture the LTSSM "
        "log immediately when the event fires."
    )
    category = RecipeCategory.DEBUG
    duration_label = "120s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id",
                display_name="Port ID",
                param_type="int",
                default=0,
                min_val=0,
                max_val=59,
            ),
            RecipeParameter(
                name="duration_s",
                display_name="Duration (s)",
                param_type="int",
                default=_DEFAULT_DURATION,
                min_val=10,
                max_val=3600,
            ),
            RecipeParameter(
                name="event_timeout_ms",
                display_name="Event Timeout (ms)",
                param_type="int",
                default=_DEFAULT_EVENT_TIMEOUT,
                min_val=500,
                max_val=30000,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return float(kwargs.get("duration_s", _DEFAULT_DURATION)) + 2

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 3
        port_id = int(kwargs.get("port_id", 0))
        duration_s = int(kwargs.get("duration_s", _DEFAULT_DURATION))
        event_timeout_ms = int(kwargs.get("event_timeout_ms", _DEFAULT_EVENT_TIMEOUT))

        # Step 1: Arm event
        yield self._make_result(
            "Arm event", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        try:
            capture = EventTriggeredCapture(dev, port_id=port_id)
            capture.arm()
            r = self._make_result(
                "Arm event", 0, total_steps, StepStatus.PASS,
                detail=f"PFF_LINK_STATE event armed for port {port_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Arm event", 0, total_steps, StepStatus.FAIL,
                detail=str(exc),
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        # Step 2: Wait loop
        yield self._make_result(
            "Wait for events", 1, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        wait_start = time.monotonic()

        while True:
            elapsed = time.monotonic() - wait_start
            remaining = duration_s - elapsed
            if remaining <= 0:
                break
            if cancel.is_set():
                break

            new_count = capture.wait_and_capture(timeout_ms=event_timeout_ms)
            if new_count > 0:
                # Re-arm for next event
                try:
                    capture.arm()
                except SwitchtecError:
                    break

        trigger_count = capture.trigger_count
        total_entries = capture.buffer.total_entries
        status = StepStatus.PASS if trigger_count == 0 else StepStatus.WARN
        r = self._make_result(
            "Wait for events", 1, total_steps, status,
            detail=(
                f"{trigger_count} event(s) captured, "
                f"{total_entries} total LTSSM entries"
            ),
            data={
                "trigger_count": trigger_count,
                "total_entries": total_entries,
                "duration_s": duration_s,
            },
        )
        results.append(r)
        yield r

        # Step 3: Final analysis
        yield self._make_result(
            "Final analysis", 2, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        snapshot = capture.buffer.snapshot()
        analyzer = LtssmPathAnalyzer()
        analysis = analyzer.analyze(snapshot)

        if not snapshot:
            status = StepStatus.PASS
            detail = "No events triggered — link is stable"
        elif analysis.verdict == "FAIL":
            status = StepStatus.FAIL
            detail = f"{len(snapshot)} entries from {trigger_count} events — {analysis.summary}"
        elif analysis.verdict == "WARN":
            status = StepStatus.WARN
            detail = f"{len(snapshot)} entries from {trigger_count} events — {analysis.summary}"
        else:
            status = StepStatus.WARN
            detail = f"{len(snapshot)} entries from {trigger_count} events"

        r = self._make_result(
            "Final analysis", 2, total_steps, status,
            detail=detail,
            data={
                "total_entries": len(snapshot),
                "trigger_count": trigger_count,
                "ltssm_verdict": analysis.verdict,
                "ltssm_patterns": [
                    {"name": p.name, "severity": p.severity, "description": p.description}
                    for p in analysis.patterns
                ],
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
