"""Config Space Dump recipe."""

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


class ConfigDump(Recipe):
    name = "Config Space Dump"
    description = (
        "Dump device summary and port configuration for a single port."
    )
    category = RecipeCategory.CONFIGURATION
    duration_label = "~2s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id", display_name="Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
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

        # Step 1: Get device summary
        yield self._make_result(
            "Device summary", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            summary = dev.get_summary()
            summary_data = {
                "name": summary.name,
                "device_id": summary.device_id,
                "generation": summary.generation,
                "variant": summary.variant,
                "boot_phase": summary.boot_phase,
                "partition": summary.partition,
                "fw_version": summary.fw_version,
                "die_temperature": summary.die_temperature,
                "port_count": summary.port_count,
                "supports_flit": summary.supports_flit,
            }
            r = self._make_result(
                "Device summary", 0, total_steps, StepStatus.PASS,
                detail=(
                    f"{summary.name} (gen={summary.generation}, "
                    f"fw={summary.fw_version})"
                ),
                data=summary_data,
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Device summary", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Get port status
        yield self._make_result(
            "Port status", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            port_list = dev.get_status()
        except SwitchtecError as exc:
            r = self._make_result(
                "Port status", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        target = None
        for p in port_list:
            if p.port.phys_id == port_id:
                target = p
                break

        if target is None:
            r = self._make_result(
                "Port status", 1, total_steps, StepStatus.FAIL,
                detail=f"Port {port_id} not found",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        port_data = {
            "link_up": target.link_up,
            "link_rate": target.link_rate,
            "neg_lnk_width": target.neg_lnk_width,
            "ltssm_str": target.ltssm_str,
            "pci_bdf": target.pci_bdf,
            "vendor_id": target.vendor_id,
            "device_id": target.device_id,
            "cfg_lnk_width": target.cfg_lnk_width,
            "flit_mode": target.flit_mode,
        }
        status = StepStatus.PASS if target.link_up else StepStatus.WARN
        detail = (
            f"Port {port_id} {'UP' if target.link_up else 'DOWN'} "
            f"rate={target.link_rate} width=x{target.neg_lnk_width}"
        )
        if target.flit_mode and target.flit_mode != "OFF":
            detail += f" FLIT={target.flit_mode}"
        r = self._make_result(
            "Port status", 1, total_steps, status,
            detail=detail, data=port_data,
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Report config
        yield self._make_result(
            "Report config", 2, total_steps, StepStatus.RUNNING,
        )
        combined_data = {**summary_data, "port": port_data}
        status = StepStatus.PASS if target.link_up else StepStatus.WARN
        detail = "Config dump complete"
        if not target.link_up:
            detail += f" (port {port_id} link is DOWN)"

        r = self._make_result(
            "Report config", 2, total_steps, status,
            detail=detail, data=combined_data,
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
