"""LTSSM Continuous Capture recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.core.ltssm_analyzer import LtssmPathAnalyzer
from serialcables_switchtec.core.ltssm_capture import LtssmCaptureBuffer
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

_DEFAULT_DURATION = 60
_DEFAULT_POLL_INTERVAL = 0.5
_DEFAULT_MAX_ENTRIES = 4096


class LtssmContinuousCapture(Recipe):
    name = "LTSSM Continuous Capture"
    description = (
        "Poll firmware LTSSM log on a fast interval, deduplicating "
        "entries to build a complete history that survives hardware "
        "buffer wrap."
    )
    category = RecipeCategory.DEBUG
    duration_label = "60s"

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
                min_val=5,
                max_val=3600,
            ),
            RecipeParameter(
                name="poll_interval_s",
                display_name="Poll Interval (s)",
                param_type="float",
                default=_DEFAULT_POLL_INTERVAL,
                min_val=0.1,
                max_val=5.0,
            ),
            RecipeParameter(
                name="max_entries",
                display_name="Max Buffer Entries",
                param_type="int",
                default=_DEFAULT_MAX_ENTRIES,
                min_val=256,
                max_val=16384,
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
        poll_interval_s = float(kwargs.get("poll_interval_s", _DEFAULT_POLL_INTERVAL))
        max_entries = int(kwargs.get("max_entries", _DEFAULT_MAX_ENTRIES))

        # Step 1: Clear LTSSM log
        yield self._make_result(
            "Clear LTSSM log", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        try:
            dev.diagnostics.ltssm_clear(port_id)
            r = self._make_result(
                "Clear LTSSM log", 0, total_steps, StepStatus.PASS,
                detail=f"LTSSM log cleared for port {port_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Clear LTSSM log", 0, total_steps, StepStatus.FAIL,
                detail=str(exc),
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        # Step 2: Continuous polling loop
        yield self._make_result(
            "Continuous capture", 1, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        buf = LtssmCaptureBuffer(max_entries=max_entries)
        poll_start = time.monotonic()

        while True:
            elapsed = time.monotonic() - poll_start
            remaining = duration_s - elapsed
            if remaining <= 0:
                break
            if cancel.is_set():
                break

            try:
                entries = dev.diagnostics.ltssm_log(port_id)
                buf.ingest(entries)
            except SwitchtecError:
                pass

            sleep_time = max(0.0, min(poll_interval_s, remaining))
            time.sleep(sleep_time)

        wrap_note = f", {buf.wrap_count} wrap(s)" if buf.wrap_count > 0 else ""
        status = StepStatus.PASS if buf.total_entries == 0 else StepStatus.WARN
        r = self._make_result(
            "Continuous capture", 1, total_steps, status,
            detail=(
                f"Captured {buf.total_entries} entries over {duration_s}s"
                f"{wrap_note}"
            ),
            data={
                "total_entries": buf.total_entries,
                "wrap_count": buf.wrap_count,
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

        snapshot = buf.snapshot()
        analyzer = LtssmPathAnalyzer()
        analysis = analyzer.analyze(snapshot)

        if not snapshot:
            status = StepStatus.PASS
            detail = "No LTSSM transitions captured — link is stable"
        elif analysis.verdict == "FAIL":
            status = StepStatus.FAIL
            detail = f"{len(snapshot)} entries — {analysis.summary}"
        elif analysis.verdict == "WARN":
            status = StepStatus.WARN
            detail = f"{len(snapshot)} entries — {analysis.summary}"
        else:
            status = StepStatus.WARN
            detail = f"{len(snapshot)} entries captured — link showed activity"

        r = self._make_result(
            "Final analysis", 2, total_steps, status,
            detail=detail,
            data={
                "total_entries": len(snapshot),
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
