"""Port Equalization Report recipe."""

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


class EqReport(Recipe):
    name = "Port Equalization Report"
    description = (
        "Read TX equalization coefficients, EQ table, and FS/LF values for a port's lanes."
    )
    category = RecipeCategory.SIGNAL_INTEGRITY
    duration_label = "~3s"

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
                name="num_lanes",
                display_name="Number of Lanes",
                param_type="int",
                default=4,
                min_val=1,
                max_val=16,
            ),
        ]

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
        port_id = int(kwargs.get("port_id", 0))
        num_lanes = int(kwargs.get("num_lanes", 4))

        # Step 1: Read TX coefficients
        yield self._make_result(
            "Read TX coefficients",
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
            coeff = dev.diagnostics.port_eq_tx_coeff(port_id)
            cursor_data = [
                {"lane": i, "pre": c.pre, "post": c.post} for i, c in enumerate(coeff.cursors)
            ]
            r = self._make_result(
                "Read TX coefficients",
                0,
                total_steps,
                StepStatus.PASS,
                detail=(f"Read coefficients for {coeff.lane_count} lane(s) on port {port_id}"),
                data={"lane_count": coeff.lane_count, "cursors": cursor_data},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read TX coefficients",
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

        # Step 2: Read FOM table
        yield self._make_result(
            "Read FOM table",
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

        try:
            table = dev.diagnostics.port_eq_tx_table(port_id)
            active_count = sum(1 for s in table.steps if s.active_status != 0)
            r = self._make_result(
                "Read FOM table",
                1,
                total_steps,
                StepStatus.PASS,
                detail=(f"EQ table: {table.step_count} steps, {active_count} active"),
                data={
                    "step_count": table.step_count,
                    "active_count": active_count,
                    "lane_id": table.lane_id,
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read FOM table",
                1,
                total_steps,
                StepStatus.WARN,
                detail=f"Could not read EQ table: {exc}",
            )
        results.append(r)
        yield r

        # Step 3: Read FS/LF per lane
        yield self._make_result(
            "Read FS/LF",
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

        fslf_data: list[dict[str, int]] = []
        warnings: list[str] = []

        for lane in range(num_lanes):
            try:
                fslf = dev.diagnostics.port_eq_tx_fslf(
                    port_id,
                    lane_id=lane,
                )
                fslf_data.append(
                    {
                        "lane": lane,
                        "fs": fslf.fs,
                        "lf": fslf.lf,
                    }
                )
                if fslf.fs == 0:
                    warnings.append(f"Lane {lane} FS=0")
                if fslf.lf == 0:
                    warnings.append(f"Lane {lane} LF=0")
            except SwitchtecError as exc:
                fslf_data.append({"lane": lane, "fs": -1, "lf": -1})
                warnings.append(f"Lane {lane} read failed: {exc}")

        if warnings:
            status = StepStatus.WARN
            detail = f"{len(warnings)} warning(s): {'; '.join(warnings)}"
        else:
            status = StepStatus.PASS
            detail = f"FS/LF values read for {num_lanes} lane(s)"

        r = self._make_result(
            "Read FS/LF",
            2,
            total_steps,
            status,
            detail=detail,
            data={"fslf": fslf_data},
        )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
