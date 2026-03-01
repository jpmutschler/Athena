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

        width, height, area = _compute_eye_metrics(
            eye_data.pixels,
            _X_COUNT,
            _Y_COUNT,
        )

        r = self._make_result(
            "Compute metrics",
            2,
            total_steps,
            StepStatus.PASS,
            detail=(f"Eye width={width}, height={height}, area={area:.1%}"),
            data={"width": width, "height": height, "area": area},
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


def _compute_eye_metrics(
    pixels: list[float],
    x_count: int,
    y_count: int,
) -> tuple[int, int, float]:
    """Compute eye width, height, and open area fraction.

    The pixel grid is stored row-major: pixels[y * x_count + x].
    Threshold is 10% of the max pixel value.

    Returns:
        Tuple of (width, height, area_fraction).
    """
    if not pixels:
        return 0, 0, 0.0

    max_val = max(pixels)
    if max_val <= 0:
        return 0, 0, 0.0  # All-zero capture: no signal detected

    threshold = max_val * 0.1

    # Eye width: contiguous open columns in center row
    center_y = y_count // 2
    center_row_start = center_y * x_count
    width = 0
    best_width = 0
    for x in range(x_count):
        if pixels[center_row_start + x] < threshold:
            width += 1
            best_width = max(best_width, width)
        else:
            width = 0

    # Eye height: contiguous open rows in center column
    center_x = x_count // 2
    height = 0
    best_height = 0
    for y in range(y_count):
        if pixels[y * x_count + center_x] < threshold:
            height += 1
            best_height = max(best_height, height)
        else:
            height = 0

    # Area: fraction of pixels below threshold
    open_count = sum(1 for p in pixels if p < threshold)
    area = open_count / len(pixels) if pixels else 0.0

    return best_width, best_height, area
