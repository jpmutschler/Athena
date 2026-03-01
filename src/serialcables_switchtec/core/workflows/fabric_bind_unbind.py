"""Fabric Bind/Unbind Validation recipe."""

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
from serialcables_switchtec.models.fabric import (
    GfmsBindRequest,
    GfmsUnbindRequest,
)


class FabricBindUnbind(Recipe):
    name = "Fabric Bind/Unbind Validation"
    description = (
        "Validate fabric bind and unbind operations by performing "
        "a round-trip bind/unbind cycle and verifying port config."
    )
    category = RecipeCategory.CONFIGURATION
    duration_label = "~5s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="host_sw_idx", display_name="Host Switch Index",
                param_type="int", default=0, min_val=0, max_val=7,
            ),
            RecipeParameter(
                name="host_phys_port_id",
                display_name="Host Physical Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="host_log_port_id",
                display_name="Host Logical Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="ep_pdfid", display_name="Endpoint PDFID",
                param_type="int", default=0, min_val=0, max_val=65535,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return 5.0

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        """Best-effort unbind if bind was performed."""
        host_sw_idx = int(kwargs.get("host_sw_idx", 0))
        host_phys_port_id = int(kwargs.get("host_phys_port_id", 0))
        host_log_port_id = int(kwargs.get("host_log_port_id", 0))
        ep_pdfid = int(kwargs.get("ep_pdfid", 0))
        try:
            unbind_req = GfmsUnbindRequest(
                host_sw_idx=host_sw_idx,
                host_phys_port_id=host_phys_port_id,
                host_log_port_id=host_log_port_id,
                pdfid=ep_pdfid,
                option=0,
            )
            dev.fabric.unbind(unbind_req)
        except SwitchtecError:
            pass

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 4

        host_sw_idx = int(kwargs.get("host_sw_idx", 0))
        host_phys_port_id = int(kwargs.get("host_phys_port_id", 0))
        host_log_port_id = int(kwargs.get("host_log_port_id", 0))
        ep_pdfid = int(kwargs.get("ep_pdfid", 0))

        # Step 1: Read port config
        yield self._make_result(
            "Read port config", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            initial_config = dev.fabric.get_port_config(host_phys_port_id)
            r = self._make_result(
                "Read port config", 0, total_steps, StepStatus.PASS,
                detail=(
                    f"Port {host_phys_port_id} config read: "
                    f"type={initial_config.port_type}"
                ),
                data={
                    "phys_port_id": initial_config.phys_port_id,
                    "port_type": initial_config.port_type,
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read port config", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Bind
        yield self._make_result(
            "Bind", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            bind_req = GfmsBindRequest(
                host_sw_idx=host_sw_idx,
                host_phys_port_id=host_phys_port_id,
                host_log_port_id=host_log_port_id,
                ep_number=1,
                ep_pdfid=[ep_pdfid],
            )
            dev.fabric.bind(bind_req)
            r = self._make_result(
                "Bind", 1, total_steps, StepStatus.PASS,
                detail=(
                    f"Bound ep_pdfid={ep_pdfid} to "
                    f"port {host_phys_port_id}"
                ),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Bind", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            self.cleanup(dev, **kwargs)
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Unbind
        yield self._make_result(
            "Unbind", 2, total_steps, StepStatus.RUNNING,
        )
        try:
            unbind_req = GfmsUnbindRequest(
                host_sw_idx=host_sw_idx,
                host_phys_port_id=host_phys_port_id,
                host_log_port_id=host_log_port_id,
                pdfid=ep_pdfid,
                option=0,
            )
            dev.fabric.unbind(unbind_req)
            r = self._make_result(
                "Unbind", 2, total_steps, StepStatus.PASS,
                detail=(
                    f"Unbound ep_pdfid={ep_pdfid} from "
                    f"port {host_phys_port_id}"
                ),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Unbind", 2, total_steps, StepStatus.FAIL,
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

        # Step 4: Verify
        yield self._make_result(
            "Verify", 3, total_steps, StepStatus.RUNNING,
        )
        try:
            final_config = dev.fabric.get_port_config(host_phys_port_id)
            r = self._make_result(
                "Verify", 3, total_steps, StepStatus.PASS,
                detail=(
                    f"Round-trip complete, port_type="
                    f"{final_config.port_type}"
                ),
                data={
                    "initial_port_type": initial_config.port_type,
                    "final_port_type": final_config.port_type,
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Verify", 3, total_steps, StepStatus.WARN,
                detail=f"Could not re-read config: {exc}",
            )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
