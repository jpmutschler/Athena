"""Link Health Check recipe."""

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

_TEMP_WARN_THRESHOLD = 85.0


class LinkHealthCheck(Recipe):
    name = "Link Health Check"
    description = (
        "Check a single port's link status, negotiated width and rate, and read die temperature."
    )
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~2s"

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
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return 2.0

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

        # Step 1: Read port status
        yield self._make_result(
            "Read port status",
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
            port_status_list = dev.get_status()
        except SwitchtecError as exc:
            r = self._make_result(
                "Read port status",
                0,
                total_steps,
                StepStatus.FAIL,
                detail=str(exc),
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Read port status",
            0,
            total_steps,
            StepStatus.PASS,
            detail=f"Retrieved status for {len(port_status_list)} ports",
            data={"port_count": len(port_status_list)},
        )
        results.append(r)
        yield r

        # Step 2: Check link state
        yield self._make_result(
            "Check link state",
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

        target_port = None
        for p in port_status_list:
            if p.port.phys_id == port_id:
                target_port = p
                break

        if target_port is None:
            r = self._make_result(
                "Check link state",
                1,
                total_steps,
                StepStatus.FAIL,
                detail=f"Port {port_id} not found",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        if target_port.link_up:
            status = StepStatus.PASS
            detail = (
                f"Port {port_id} UP — rate={target_port.link_rate}, "
                f"width=x{target_port.neg_lnk_width}"
            )
        else:
            status = StepStatus.WARN
            detail = f"Port {port_id} DOWN — LTSSM={target_port.ltssm_str}"

        r = self._make_result(
            "Check link state",
            1,
            total_steps,
            status,
            detail=detail,
            data={
                "link_up": target_port.link_up,
                "link_rate": target_port.link_rate,
                "neg_lnk_width": target_port.neg_lnk_width,
                "ltssm": target_port.ltssm_str,
            },
        )
        results.append(r)
        yield r

        # Step 3: Read temperature
        yield self._make_result(
            "Read temperature",
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
            temps = dev.get_die_temperatures(1)
            temp = temps[0]
            if temp >= _TEMP_WARN_THRESHOLD:
                status = StepStatus.WARN
                detail = f"Die temperature {temp:.1f} C >= {_TEMP_WARN_THRESHOLD} C"
            else:
                status = StepStatus.PASS
                detail = f"Die temperature {temp:.1f} C"
            r = self._make_result(
                "Read temperature",
                2,
                total_steps,
                status,
                detail=detail,
                data={"temperature": temp},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read temperature",
                2,
                total_steps,
                StepStatus.WARN,
                detail=f"Could not read temperature: {exc}",
            )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
