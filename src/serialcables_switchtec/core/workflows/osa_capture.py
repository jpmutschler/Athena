"""OSA Link Training Capture recipe."""

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
from serialcables_switchtec.models.osa import interpret_osa_result

_DEFAULT_DURATION = 10


class OsaCapture(Recipe):
    name = "OSA Link Training Capture"
    description = (
        "Configure and run an OSA (Ordered Set Analyzer) capture "
        "to record link training ordered sets."
    )
    category = RecipeCategory.DEBUG
    duration_label = "~10s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="stack_id", display_name="Stack ID",
                param_type="int", default=0, min_val=0, max_val=7,
            ),
            RecipeParameter(
                name="lane_mask", display_name="Lane Mask",
                param_type="int", default=0x1,
                min_val=0, max_val=0xFFFF,
            ),
            RecipeParameter(
                name="duration_s", display_name="Duration (s)",
                param_type="int", default=_DEFAULT_DURATION,
                min_val=1, max_val=60,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return float(kwargs.get("duration_s", _DEFAULT_DURATION)) + 3

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        stack_id = int(kwargs.get("stack_id", 0))
        try:
            dev.osa.stop(stack_id)
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

        stack_id = int(kwargs.get("stack_id", 0))
        lane_mask = int(kwargs.get("lane_mask", 0x1))
        duration_s = int(kwargs.get("duration_s", _DEFAULT_DURATION))

        # Step 1: Configure OSA
        yield self._make_result(
            "Configure OSA", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            dev.osa.configure_type(
                stack_id,
                direction=0,
                lane_mask=lane_mask,
                link_rate=0,
                os_types=0xFFFF,
            )
            r = self._make_result(
                "Configure OSA", 0, total_steps, StepStatus.PASS,
                detail=(
                    f"OSA configured on stack {stack_id}, "
                    f"lane_mask=0x{lane_mask:X}"
                ),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Configure OSA", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Start capture
        yield self._make_result(
            "Start capture", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            dev.osa.start(stack_id)
            r = self._make_result(
                "Start capture", 1, total_steps, StepStatus.PASS,
                detail=f"OSA capture started on stack {stack_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Start capture", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            try:
                dev.osa.stop(stack_id)
            except SwitchtecError:
                pass
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Wait
        yield self._make_result(
            "Wait for capture", 2, total_steps, StepStatus.RUNNING,
        )
        wait_start = time.monotonic()
        while time.monotonic() - wait_start < duration_s:
            if cancel.is_set():
                break
            remaining = duration_s - (time.monotonic() - wait_start)
            time.sleep(max(0, min(1.0, remaining)))

        actual_wait = time.monotonic() - wait_start
        r = self._make_result(
            "Wait for capture", 2, total_steps, StepStatus.PASS,
            detail=f"Waited {actual_wait:.1f}s",
        )
        results.append(r)
        yield r

        if cancel.is_set():
            try:
                dev.osa.stop(stack_id)
            except SwitchtecError:
                pass
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 4: Stop + read
        yield self._make_result(
            "Stop and read", 3, total_steps, StepStatus.RUNNING,
        )
        try:
            dev.osa.stop(stack_id)
            # Read capture from the first lane set in the mask
            first_lane = (lane_mask & -lane_mask).bit_length() - 1 if lane_mask else 0
            result_code = dev.osa.capture_data(
                stack_id, lane=first_lane, direction=0,
            )
            capture_result = interpret_osa_result(result_code)
            status = StepStatus.PASS if capture_result.success else StepStatus.WARN
            r = self._make_result(
                "Stop and read", 3, total_steps, status,
                detail=(
                    f"Capture complete: {capture_result.message} "
                    f"(status={capture_result.status_name})"
                ),
                data={
                    "stack_id": stack_id,
                    "result_code": result_code,
                    "osa_status": capture_result.status_name,
                    "osa_success": capture_result.success,
                    "duration_s": actual_wait,
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Stop and read", 3, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
