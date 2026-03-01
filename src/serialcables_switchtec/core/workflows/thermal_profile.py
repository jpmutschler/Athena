"""Switch Thermal Profile recipe."""

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

_DEFAULT_DURATION = 60
_TEMP_WARN_THRESHOLD = 100.0


class ThermalProfile(Recipe):
    name = "Switch Thermal Profile"
    description = (
        "Monitor die temperature sensors over time and report "
        "per-sensor min/max/avg statistics."
    )
    category = RecipeCategory.DEBUG
    duration_label = "60s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="duration_s", display_name="Duration (s)",
                param_type="int", default=_DEFAULT_DURATION,
                min_val=10, max_val=600,
            ),
            RecipeParameter(
                name="interval_s", display_name="Interval (s)",
                param_type="int", default=2, min_val=1, max_val=30,
            ),
            RecipeParameter(
                name="num_sensors", display_name="Number of Sensors",
                param_type="int", default=5, min_val=1, max_val=10,
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

        duration_s = int(kwargs.get("duration_s", _DEFAULT_DURATION))
        interval_s = int(kwargs.get("interval_s", 2))
        num_sensors = int(kwargs.get("num_sensors", 5))

        # Step 1: Initial temperature read
        yield self._make_result(
            "Initial read", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            temps = dev.get_die_temperatures(num_sensors)
            baseline_str = ", ".join(
                f"S{i}={t:.1f}C" for i, t in enumerate(temps)
            )
            r = self._make_result(
                "Initial read", 0, total_steps, StepStatus.PASS,
                detail=f"Baseline: {baseline_str}",
                data={
                    "baseline": [
                        {"sensor": i, "temp_c": t}
                        for i, t in enumerate(temps)
                    ],
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Initial read", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Monitor
        yield self._make_result(
            "Monitor", 1, total_steps, StepStatus.RUNNING,
        )

        # Initialize per-sensor accumulators
        sensor_mins: list[float] = list(temps)
        sensor_maxs: list[float] = list(temps)
        sensor_sums: list[float] = list(temps)
        sample_count = 1

        poll_start = time.monotonic()
        while time.monotonic() - poll_start < duration_s:
            if cancel.is_set():
                break
            remaining = duration_s - (time.monotonic() - poll_start)
            time.sleep(max(0, min(interval_s, remaining)))
            if cancel.is_set():
                break
            try:
                temps = dev.get_die_temperatures(num_sensors)
                sample_count += 1
                for i, t in enumerate(temps):
                    if i < len(sensor_mins):
                        sensor_mins[i] = min(sensor_mins[i], t)
                        sensor_maxs[i] = max(sensor_maxs[i], t)
                        sensor_sums[i] += t
            except SwitchtecError:
                pass

        r = self._make_result(
            "Monitor", 1, total_steps, StepStatus.PASS,
            detail=f"Collected {sample_count} samples",
            data={"sample_count": sample_count},
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Report
        yield self._make_result(
            "Report", 2, total_steps, StepStatus.RUNNING,
        )

        per_sensor: list[dict[str, object]] = []
        any_warn = False
        for i in range(len(sensor_mins)):
            avg = sensor_sums[i] / sample_count if sample_count > 0 else 0
            if sensor_maxs[i] >= _TEMP_WARN_THRESHOLD:
                any_warn = True
            per_sensor.append({
                "sensor": i,
                "min_c": sensor_mins[i],
                "max_c": sensor_maxs[i],
                "avg_c": round(avg, 2),
            })

        status = StepStatus.WARN if any_warn else StepStatus.PASS
        detail_parts = [
            f"S{s['sensor']}: {s['min_c']:.1f}-{s['max_c']:.1f}C"
            for s in per_sensor
        ]
        detail = "; ".join(detail_parts)
        if any_warn:
            detail += f" (sensor >= {_TEMP_WARN_THRESHOLD:.0f}C)"

        r = self._make_result(
            "Report", 2, total_steps, status,
            detail=detail,
            data={
                "sensors": per_sensor,
                "sample_count": sample_count,
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
