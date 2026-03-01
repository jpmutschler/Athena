"""Eye Diagram Quick Scan recipe."""

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
from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.core.eye_metrics import analyze_eye, compute_eye_metrics
from serialcables_switchtec.exceptions import SwitchtecError

_FETCH_TIMEOUT = 60.0
_FETCH_RETRY_INTERVAL = 0.5
_AREA_WARN_THRESHOLD = 0.20

# Default eye diagram grid dimensions
_X_START, _X_END, _X_STEP = -64, 64, 1
_Y_START, _Y_END, _Y_STEP = -255, 255, 2
_X_COUNT = (_X_END - _X_START) // _X_STEP + 1  # 129
_Y_COUNT = (_Y_END - _Y_START) // _Y_STEP + 1  # 256
_PIXEL_COUNT = _X_COUNT * _Y_COUNT


class EyeQuickScan(Recipe):
    name = "Eye Diagram Quick Scan"
    description = (
        "Capture a quick eye diagram for a single lane, compute eye "
        "width, height, and open area metrics."
    )
    category = RecipeCategory.SIGNAL_INTEGRITY
    duration_label = "~30s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="lane_id",
                display_name="Lane ID",
                param_type="int",
                default=0,
                min_val=0,
                max_val=143,
            ),
            RecipeParameter(
                name="step_interval",
                display_name="Step Interval",
                param_type="int",
                default=10,
                min_val=1,
                max_val=100,
            ),
            RecipeParameter(
                name="generation",
                display_name="PCIe Generation",
                param_type="select",
                choices=["GEN3", "GEN4", "GEN5", "GEN6"],
                default=None,
                required=False,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return 30.0

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        try:
            dev.diagnostics.eye_cancel()
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
        lane_id = int(kwargs.get("lane_id", 0))
        step_interval = int(kwargs.get("step_interval", 10))

        # Resolve generation for PAM4-aware analysis
        gen_str = kwargs.get("generation")
        gen: SwitchtecGen | None = None
        if gen_str is not None:
            gen_map = {
                "GEN3": SwitchtecGen.GEN3,
                "GEN4": SwitchtecGen.GEN4,
                "GEN5": SwitchtecGen.GEN5,
                "GEN6": SwitchtecGen.GEN6,
            }
            gen = gen_map.get(str(gen_str))

        # Step 1: Start eye capture
        yield self._make_result(
            "Start eye capture",
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

        # lane_mask is a 4-element list for the C API's c_int[4] array.
        # Each element covers 32 lanes: [0-31], [32-63], [64-95], [96-127+].
        lane_mask = [0, 0, 0, 0]
        lane_mask[lane_id // 32] = 1 << (lane_id % 32)
        try:
            dev.diagnostics.eye_start(
                lane_mask=lane_mask,
                x_start=_X_START,
                x_end=_X_END,
                x_step=_X_STEP,
                y_start=_Y_START,
                y_end=_Y_END,
                y_step=_Y_STEP,
                step_interval=step_interval,
            )
            r = self._make_result(
                "Start eye capture",
                0,
                total_steps,
                StepStatus.PASS,
                detail=f"Eye capture started for lane {lane_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Start eye capture",
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

        # Step 2: Wait for capture
        yield self._make_result(
            "Wait for capture",
            1,
            total_steps,
            StepStatus.RUNNING,
        )

        eye_data = None
        fetch_start = time.monotonic()

        while time.monotonic() - fetch_start < _FETCH_TIMEOUT:
            if cancel.is_set():
                self.cleanup(dev)
                return self._make_summary(
                    results,
                    time.monotonic() - start,
                    aborted=True,
                )
            try:
                eye_data = dev.diagnostics.eye_fetch(_PIXEL_COUNT)
                break
            except SwitchtecError:
                time.sleep(_FETCH_RETRY_INTERVAL)

        if eye_data is None:
            r = self._make_result(
                "Wait for capture",
                1,
                total_steps,
                StepStatus.FAIL,
                detail=f"Eye capture timed out after {_FETCH_TIMEOUT:.0f}s",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            self.cleanup(dev)
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Wait for capture",
            1,
            total_steps,
            StepStatus.PASS,
            detail=f"Captured {len(eye_data.pixels)} pixels",
            data={"pixel_count": len(eye_data.pixels)},
        )
        results.append(r)
        yield r

        # Step 3: Compute metrics
        yield self._make_result(
            "Compute metrics",
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

        metrics = compute_eye_metrics(eye_data.pixels, _X_COUNT, _Y_COUNT)
        width, height, area = metrics.width, metrics.height, metrics.area_fraction

        # Run generation-aware analysis if generation is specified
        eye_analysis_data: dict[str, object] = {
            "width": width,
            "height": height,
            "area": area,
        }
        if gen is not None:
            eye_result = analyze_eye(eye_data.pixels, _X_COUNT, _Y_COUNT, gen)
            eye_analysis_data["signaling"] = eye_result.signaling
            eye_analysis_data["eye_count"] = len(eye_result.eyes)
            eye_analysis_data["overall_area"] = eye_result.overall_area
            eye_analysis_data["gen_verdict"] = eye_result.verdict

        r = self._make_result(
            "Compute metrics",
            2,
            total_steps,
            StepStatus.PASS,
            detail=(f"Eye width={width}, height={height}, area={area:.1%}"),
            data=eye_analysis_data,
        )
        results.append(r)
        yield r

        # Step 4: Summary
        yield self._make_result(
            "Summary",
            3,
            total_steps,
            StepStatus.RUNNING,
        )

        if area < _AREA_WARN_THRESHOLD:
            status = StepStatus.WARN
            detail = (
                f"Eye area {area:.1%} < {_AREA_WARN_THRESHOLD:.0%} — signal quality may be degraded"
            )
        else:
            status = StepStatus.PASS
            detail = f"Eye width={width}, height={height}, area={area:.1%}"

        r = self._make_result(
            "Summary",
            3,
            total_steps,
            status,
            detail=detail,
            data={
                "lane_id": lane_id,
                "width": width,
                "height": height,
                "area": area,
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
