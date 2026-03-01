"""All-Port Status Sweep recipe."""

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


class AllPortSweep(Recipe):
    name = "All-Port Status Sweep"
    description = (
        "Scan every port on the switch for link status, width, rate, "
        "LTSSM state, and die temperature."
    )
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~3s"

    def parameters(self) -> list[RecipeParameter]:
        return []

    def estimated_duration_s(self, **kwargs: object) -> float:
        return 3.0

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 3

        # Step 1: Enumerate ports
        yield self._make_result(
            "Enumerating ports", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            results.append(self._make_result(
                "Enumerating ports", 0, total_steps, StepStatus.SKIP,
                detail="Cancelled",
            ))
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        try:
            port_status = dev.get_status()
        except SwitchtecError as exc:
            result = self._make_result(
                "Enumerating ports", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(result)
            yield result
            return self._make_summary(results, time.monotonic() - start)

        up_count = sum(1 for p in port_status if p.link_up)
        down_count = len(port_status) - up_count
        result = self._make_result(
            "Enumerating ports", 0, total_steps, StepStatus.PASS,
            detail=f"Found {len(port_status)} ports: {up_count} UP, {down_count} DOWN",
            data={"total": len(port_status), "up": up_count, "down": down_count},
        )
        results.append(result)
        yield result

        # Step 2: Per-port status
        if cancel.is_set():
            results.append(self._make_result(
                "Per-port status", 1, total_steps, StepStatus.SKIP, detail="Cancelled",
            ))
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        port_data = []
        for p in port_status:
            port_data.append({
                "phys_id": p.port.phys_id,
                "link_up": p.link_up,
                "link_rate": getattr(p, "link_rate", ""),
                "neg_link_width": getattr(p, "neg_link_width", 0),
            })

        result = self._make_result(
            "Per-port status", 1, total_steps, StepStatus.PASS,
            detail=f"Collected status for {len(port_status)} ports",
            data={"ports": port_data},
        )
        results.append(result)
        yield result

        # Step 3: Read temperature
        if cancel.is_set():
            results.append(self._make_result(
                "Die temperature", 2, total_steps, StepStatus.SKIP, detail="Cancelled",
            ))
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        try:
            summary = dev.identify()
            temp = summary.die_temperature
            status = StepStatus.PASS if temp < 100 else StepStatus.WARN
            result = self._make_result(
                "Die temperature", 2, total_steps, status,
                detail=f"Die temperature: {temp:.1f} C",
                data={"temperature": temp},
            )
        except SwitchtecError as exc:
            result = self._make_result(
                "Die temperature", 2, total_steps, StepStatus.WARN,
                detail=f"Could not read temperature: {exc}",
            )
        results.append(result)
        yield result

        return self._make_summary(results, time.monotonic() - start)
