"""Event Counter Stress Baseline recipe."""

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
from serialcables_switchtec.core.evcntr_presets import PRESETS
from serialcables_switchtec.exceptions import SwitchtecError

_DEFAULT_DURATION = 30
_POLL_INTERVAL = 2.0


class EventCounterBaseline(Recipe):
    name = "Event Counter Stress Baseline"
    description = (
        "Configure an event counter, soak for a duration, and "
        "report total events and event rate."
    )
    category = RecipeCategory.PERFORMANCE
    duration_label = "30s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="stack_id", display_name="Stack ID",
                param_type="int", default=0, min_val=0, max_val=7,
            ),
            RecipeParameter(
                name="counter_id", display_name="Counter ID",
                param_type="int", default=0, min_val=0, max_val=63,
            ),
            RecipeParameter(
                name="port_mask", display_name="Port Mask",
                param_type="int", default=0xFFFFFFFF,
                min_val=0, max_val=0xFFFFFFFF,
            ),
            RecipeParameter(
                name="type_mask", display_name="Type Mask",
                param_type="int", default=0xFFFFFFFF,
                min_val=0, max_val=0xFFFFFFFF,
            ),
            RecipeParameter(
                name="counter_preset", display_name="Counter Preset",
                param_type="select",
                choices=sorted(PRESETS.keys()),
                default=None,
                required=False,
            ),
            RecipeParameter(
                name="duration_s", display_name="Duration (s)",
                param_type="int", default=_DEFAULT_DURATION,
                min_val=5, max_val=300,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return float(kwargs.get("duration_s", _DEFAULT_DURATION)) + 5

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 4

        stack_id = int(kwargs.get("stack_id", 0))
        counter_id = int(kwargs.get("counter_id", 0))
        port_mask = int(kwargs.get("port_mask", 0xFFFFFFFF))
        type_mask = int(kwargs.get("type_mask", 0xFFFFFFFF))
        duration_s = int(kwargs.get("duration_s", _DEFAULT_DURATION))

        # Apply preset if specified (overrides type_mask)
        counter_preset = kwargs.get("counter_preset")
        if counter_preset is not None and str(counter_preset) in PRESETS:
            preset = PRESETS[str(counter_preset)]
            type_mask = preset.type_mask

        # Step 1: Configure counter
        yield self._make_result(
            "Configure counter", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            dev.evcntr.setup(stack_id, counter_id, port_mask, type_mask)
            r = self._make_result(
                "Configure counter", 0, total_steps, StepStatus.PASS,
                detail=(
                    f"Counter {counter_id} on stack {stack_id} configured"
                ),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Configure counter", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 2: Read baseline
        yield self._make_result(
            "Read baseline", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            baseline_counts = dev.evcntr.get_counts(
                stack_id, counter_id, clear=True,
            )
            baseline = baseline_counts[0] if baseline_counts else 0
            r = self._make_result(
                "Read baseline", 1, total_steps, StepStatus.PASS,
                detail=f"Baseline count: {baseline}",
                data={"baseline": baseline},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read baseline", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Soak
        yield self._make_result(
            "Soak", 2, total_steps, StepStatus.RUNNING,
        )
        total_events = 0
        poll_start = time.monotonic()

        while time.monotonic() - poll_start < duration_s:
            if cancel.is_set():
                break
            try:
                counts = dev.evcntr.get_counts(
                    stack_id, counter_id, clear=True,
                )
                if counts:
                    total_events += counts[0]
            except SwitchtecError:
                pass
            remaining = duration_s - (time.monotonic() - poll_start)
            time.sleep(max(0, min(_POLL_INTERVAL, remaining)))

        actual_duration = time.monotonic() - poll_start
        r = self._make_result(
            "Soak", 2, total_steps, StepStatus.PASS,
            detail=(
                f"Soaked for {actual_duration:.1f}s, "
                f"accumulated {total_events} events"
            ),
            data={
                "total_events": total_events,
                "soak_duration_s": actual_duration,
            },
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 4: Report
        yield self._make_result(
            "Report", 3, total_steps, StepStatus.RUNNING,
        )
        rate = total_events / actual_duration if actual_duration > 0 else 0
        status = StepStatus.PASS if total_events == 0 else StepStatus.WARN
        detail = f"Total events: {total_events}, rate: {rate:.2f} events/s"
        if total_events > 0:
            detail += " (unexpected activity during stress)"

        r = self._make_result(
            "Report", 3, total_steps, status,
            detail=detail,
            data={
                "total_events": total_events,
                "events_per_second": rate,
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
