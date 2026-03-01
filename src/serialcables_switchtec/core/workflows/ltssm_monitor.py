"""LTSSM State Monitor recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.core.device import SwitchtecDevice
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

_DEFAULT_DURATION = 30
_POLL_INTERVAL = 1.0


class LtssmMonitor(Recipe):
    name = "LTSSM State Monitor"
    description = (
        "Clear the LTSSM log, monitor for state transitions over a "
        "configurable duration, and report any detected transitions."
    )
    category = RecipeCategory.LINK_HEALTH
    duration_label = "30s"

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
                max_val=300,
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

        # Step 1: Clear LTSSM log
        yield self._make_result(
            "Clear LTSSM log",
            0,
            total_steps,
            StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=True,
            )

        try:
            dev.diagnostics.ltssm_clear(port_id)
            r = self._make_result(
                "Clear LTSSM log",
                0,
                total_steps,
                StepStatus.PASS,
                detail=f"LTSSM log cleared for port {port_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Clear LTSSM log",
                0,
                total_steps,
                StepStatus.FAIL,
                detail=str(exc),
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        # Step 2: Monitor
        yield self._make_result(
            "Monitor LTSSM",
            1,
            total_steps,
            StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=True,
            )

        monitor_start = time.monotonic()
        max_transitions = 0

        while True:
            elapsed = time.monotonic() - monitor_start
            remaining = duration_s - elapsed
            if remaining <= 0:
                break
            if cancel.is_set():
                break

            try:
                entries = dev.diagnostics.ltssm_log(port_id)
                max_transitions = max(max_transitions, len(entries))
            except SwitchtecError:
                pass

            sleep_time = max(0.0, min(_POLL_INTERVAL, remaining))
            time.sleep(sleep_time)

        status = StepStatus.PASS if max_transitions == 0 else StepStatus.WARN
        r = self._make_result(
            "Monitor LTSSM",
            1,
            total_steps,
            status,
            detail=(f"Monitored for {duration_s}s — {max_transitions} transitions detected"),
            data={
                "duration_s": duration_s,
                "transitions_detected": max_transitions,
            },
        )
        results.append(r)
        yield r

        # Step 3: Final analysis
        yield self._make_result(
            "Final analysis",
            2,
            total_steps,
            StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=True,
            )

        try:
            final_entries = dev.diagnostics.ltssm_log(port_id)
            total_transitions = len(final_entries)
        except SwitchtecError as exc:
            r = self._make_result(
                "Final analysis",
                2,
                total_steps,
                StepStatus.WARN,
                detail=f"Could not read final LTSSM log: {exc}",
            )
            results.append(r)
            yield r
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=cancel.is_set(),
            )

        if total_transitions == 0:
            status = StepStatus.PASS
            detail = "No LTSSM transitions detected — link is stable"
        else:
            status = StepStatus.WARN
            detail = f"{total_transitions} LTSSM transitions detected — link may be unstable"

        r = self._make_result(
            "Final analysis",
            2,
            total_steps,
            status,
            detail=detail,
            data={
                "total_transitions": total_transitions,
                "entries": [
                    {
                        "state": e.link_state_str,
                        "rate": e.link_rate,
                        "width": e.link_width,
                    }
                    for e in final_entries[:10]
                ],
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
