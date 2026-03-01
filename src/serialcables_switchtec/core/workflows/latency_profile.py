"""Latency Measurement Profile recipe."""

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

_SAMPLE_DELAY = 0.25


class LatencyProfile(Recipe):
    name = "Latency Measurement Profile"
    description = (
        "Measure switch latency between egress and ingress ports, "
        "collecting multiple samples to compute min/max/avg."
    )
    category = RecipeCategory.PERFORMANCE
    duration_label = "~5s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="egress_port_id", display_name="Egress Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="ingress_port_id", display_name="Ingress Port ID",
                param_type="int", default=1, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="sample_count", display_name="Sample Count",
                param_type="int", default=10, min_val=1, max_val=100,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        count = int(kwargs.get("sample_count", 10))
        return (count * _SAMPLE_DELAY) + 2

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 3

        egress_port_id = int(kwargs.get("egress_port_id", 0))
        ingress_port_id = int(kwargs.get("ingress_port_id", 1))
        sample_count = int(kwargs.get("sample_count", 10))

        # Step 1: Setup latency measurement
        yield self._make_result(
            "Setup latency", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            dev.performance.lat_setup(
                egress_port_id, ingress_port_id, clear=True,
            )
            r = self._make_result(
                "Setup latency", 0, total_steps, StepStatus.PASS,
                detail=(
                    f"Latency measurement configured: "
                    f"egress={egress_port_id}, ingress={ingress_port_id}"
                ),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Setup latency", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Collect samples
        yield self._make_result(
            "Collect samples", 1, total_steps, StepStatus.RUNNING,
        )
        current_ns_samples: list[int] = []
        max_ns_values: list[int] = []

        for i in range(sample_count):
            if cancel.is_set():
                break
            try:
                lat = dev.performance.lat_get(
                    egress_port_id, clear=True,
                )
                current_ns_samples.append(lat.current_ns)
                max_ns_values.append(lat.max_ns)
            except SwitchtecError:
                pass
            if i < sample_count - 1:
                time.sleep(max(0, _SAMPLE_DELAY))

        collected = len(current_ns_samples)
        r = self._make_result(
            "Collect samples", 1, total_steps, StepStatus.PASS,
            detail=f"Collected {collected}/{sample_count} samples",
            data={"collected": collected, "requested": sample_count},
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Analyze
        yield self._make_result(
            "Analyze", 2, total_steps, StepStatus.RUNNING,
        )

        if collected == 0:
            r = self._make_result(
                "Analyze", 2, total_steps, StepStatus.WARN,
                detail="No latency samples collected",
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        stats = {
            "min_ns": min(current_ns_samples),
            "max_ns": max(current_ns_samples),
            "avg_ns": sum(current_ns_samples) / collected,
            "max_observed_ns": max(max_ns_values),
            "sample_count": collected,
        }
        r = self._make_result(
            "Analyze", 2, total_steps, StepStatus.PASS,
            detail=(
                f"Latency min={stats['min_ns']}ns, "
                f"max={stats['max_ns']}ns, "
                f"avg={stats['avg_ns']:.0f}ns"
            ),
            data=stats,
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
