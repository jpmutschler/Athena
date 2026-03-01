"""Bandwidth Baseline recipe."""

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

_DEFAULT_DURATION = 10


class BandwidthBaseline(Recipe):
    name = "Bandwidth Baseline"
    description = (
        "Sample bandwidth counters on a port over a configurable "
        "duration and compute min/max/avg statistics."
    )
    category = RecipeCategory.PERFORMANCE
    duration_label = "10s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id", display_name="Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="duration_s", display_name="Duration (s)",
                param_type="int", default=_DEFAULT_DURATION,
                min_val=5, max_val=120,
            ),
            RecipeParameter(
                name="interval_s", display_name="Interval (s)",
                param_type="int", default=1, min_val=1, max_val=10,
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
        interval_s = int(kwargs.get("interval_s", 1))

        # Step 1: Verify port exists
        yield self._make_result(
            "Verify port", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            ports = dev.get_status()
        except SwitchtecError as exc:
            r = self._make_result(
                "Verify port", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        target = None
        for p in ports:
            if p.port.phys_id == port_id:
                target = p
                break

        if target is None:
            r = self._make_result(
                "Verify port", 0, total_steps, StepStatus.FAIL,
                detail=f"Port {port_id} not found",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Verify port", 0, total_steps, StepStatus.PASS,
            detail=f"Port {port_id} found, link_up={target.link_up}",
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 2: Sample bandwidth
        yield self._make_result(
            "Sample bandwidth", 1, total_steps, StepStatus.RUNNING,
        )
        egress_samples: list[int] = []
        ingress_samples: list[int] = []
        poll_start = time.monotonic()

        while time.monotonic() - poll_start < duration_s:
            if cancel.is_set():
                break
            try:
                bw = dev.performance.bw_get([port_id], clear=True)
                if bw:
                    egress_samples.append(bw[0].egress.total)
                    ingress_samples.append(bw[0].ingress.total)
            except SwitchtecError:
                pass
            remaining = duration_s - (time.monotonic() - poll_start)
            time.sleep(max(0, min(interval_s, remaining)))

        sample_count = len(egress_samples)
        r = self._make_result(
            "Sample bandwidth", 1, total_steps, StepStatus.PASS,
            detail=f"Collected {sample_count} samples over {duration_s}s",
            data={"sample_count": sample_count},
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Compute stats
        yield self._make_result(
            "Compute stats", 2, total_steps, StepStatus.RUNNING,
        )

        if sample_count == 0:
            r = self._make_result(
                "Compute stats", 2, total_steps, StepStatus.WARN,
                detail="No samples collected",
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        stats = {
            "egress_min": min(egress_samples),
            "egress_max": max(egress_samples),
            "egress_avg": sum(egress_samples) / sample_count,
            "ingress_min": min(ingress_samples),
            "ingress_max": max(ingress_samples),
            "ingress_avg": sum(ingress_samples) / sample_count,
            "sample_count": sample_count,
        }
        r = self._make_result(
            "Compute stats", 2, total_steps, StepStatus.PASS,
            detail=(
                f"Egress avg={stats['egress_avg']:.0f}, "
                f"Ingress avg={stats['ingress_avg']:.0f}"
            ),
            data=stats,
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
