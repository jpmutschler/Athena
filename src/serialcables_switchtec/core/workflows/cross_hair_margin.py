"""Cross-Hair Margin Analysis recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.bindings.constants import SwitchtecGen
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

_POLL_INTERVAL = 0.5
_TIMEOUT_PER_LANE = 15.0

# Legacy defaults (used when no generation is specified)
_H_MARGIN_WARN = 20
_V_MARGIN_WARN = 30

# Generation-aware thresholds: PAM4 (Gen6) has ~1/3 the margin of NRZ
_MARGIN_THRESHOLDS: dict[SwitchtecGen, dict[str, int]] = {
    SwitchtecGen.GEN3: {"h_warn": 30, "v_warn": 40},
    SwitchtecGen.GEN4: {"h_warn": 25, "v_warn": 35},
    SwitchtecGen.GEN5: {"h_warn": 20, "v_warn": 30},
    SwitchtecGen.GEN6: {"h_warn": 7, "v_warn": 10},
}


class CrossHairMargin(Recipe):
    name = "Cross-Hair Margin Analysis"
    description = (
        "Enable cross-hair measurement on one or more lanes, poll until "
        "complete, and report horizontal and vertical eye margins."
    )
    category = RecipeCategory.SIGNAL_INTEGRITY
    duration_label = "~10s/lane"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="start_lane_id",
                display_name="Start Lane ID",
                param_type="int",
                default=0,
                min_val=0,
                max_val=143,
            ),
            RecipeParameter(
                name="num_lanes",
                display_name="Number of Lanes",
                param_type="int",
                default=1,
                min_val=1,
                max_val=16,
            ),
            RecipeParameter(
                name="h_margin_warn",
                display_name="H-Margin Warning Threshold",
                param_type="int",
                required=False,
                default=None,
                min_val=0,
                max_val=200,
                depends_on="generation",
            ),
            RecipeParameter(
                name="v_margin_warn",
                display_name="V-Margin Warning Threshold",
                param_type="int",
                required=False,
                default=None,
                min_val=0,
                max_val=200,
                depends_on="generation",
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        num_lanes = int(kwargs.get("num_lanes", 1))
        return num_lanes * 10.0

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        try:
            dev.diagnostics.cross_hair_disable()
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
        total_steps = 3
        start_lane_id = int(kwargs.get("start_lane_id", 0))
        num_lanes = int(kwargs.get("num_lanes", 1))

        # Resolve generation-aware margin thresholds
        gen_val = kwargs.get("generation")
        if gen_val is not None:
            gen = SwitchtecGen(int(gen_val))
            gen_thresholds = _MARGIN_THRESHOLDS.get(gen, {})
        else:
            gen_thresholds = {}

        h_warn_raw = kwargs.get("h_margin_warn")
        v_warn_raw = kwargs.get("v_margin_warn")
        h_margin_warn = (
            int(h_warn_raw)
            if h_warn_raw is not None
            else gen_thresholds.get("h_warn", _H_MARGIN_WARN)
        )
        v_margin_warn = (
            int(v_warn_raw)
            if v_warn_raw is not None
            else gen_thresholds.get("v_warn", _V_MARGIN_WARN)
        )

        # Step 1: Enable measurement
        yield self._make_result(
            "Enable measurement",
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
            dev.diagnostics.cross_hair_enable(start_lane_id)
            r = self._make_result(
                "Enable measurement",
                0,
                total_steps,
                StepStatus.PASS,
                detail=(f"Cross-hair enabled on lane {start_lane_id} ({num_lanes} lane(s))"),
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Enable measurement",
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

        # Step 2: Poll results
        yield self._make_result(
            "Poll results",
            1,
            total_steps,
            StepStatus.RUNNING,
        )

        timeout = num_lanes * _TIMEOUT_PER_LANE
        poll_start = time.monotonic()
        ch_results = None

        while time.monotonic() - poll_start < timeout:
            if cancel.is_set():
                self.cleanup(dev)
                return self._make_summary(
                    results,
                    time.monotonic() - start,
                    aborted=True,
                )
            try:
                ch_results = dev.diagnostics.cross_hair_get(
                    start_lane_id,
                    num_lanes,
                )
                all_done = all(
                    "DONE" in ch.state_name or "COMPLETE" in ch.state_name for ch in ch_results
                )
                if all_done:
                    break
            except SwitchtecError:
                pass
            time.sleep(_POLL_INTERVAL)
        else:
            # Timed out — try one last fetch
            try:
                ch_results = dev.diagnostics.cross_hair_get(
                    start_lane_id,
                    num_lanes,
                )
            except SwitchtecError:
                pass

        if ch_results is None:
            r = self._make_result(
                "Poll results",
                1,
                total_steps,
                StepStatus.FAIL,
                detail="Cross-hair measurement failed — no results",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            self.cleanup(dev)
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Poll results",
            1,
            total_steps,
            StepStatus.PASS,
            detail=f"Collected results for {len(ch_results)} lane(s)",
        )
        results.append(r)
        yield r

        # Step 3: Disable + analyze
        yield self._make_result(
            "Disable + analyze",
            2,
            total_steps,
            StepStatus.RUNNING,
        )

        try:
            dev.diagnostics.cross_hair_disable()
        except SwitchtecError:
            pass

        warnings: list[str] = []
        lane_data: list[dict[str, object]] = []

        for ch in ch_results:
            h_margin = ch.eye_left_lim + ch.eye_right_lim
            v_top = min(ch.eye_top_left_lim, ch.eye_top_right_lim)
            v_bot = min(ch.eye_bot_left_lim, ch.eye_bot_right_lim)
            v_margin = v_top + v_bot

            lane_data.append(
                {
                    "lane_id": ch.lane_id,
                    "state": ch.state_name,
                    "h_margin": h_margin,
                    "v_margin": v_margin,
                    "eye_left": ch.eye_left_lim,
                    "eye_right": ch.eye_right_lim,
                }
            )

            if h_margin < h_margin_warn:
                warnings.append(f"Lane {ch.lane_id} h_margin={h_margin} < {h_margin_warn}")
            if v_margin < v_margin_warn:
                warnings.append(f"Lane {ch.lane_id} v_margin={v_margin} < {v_margin_warn}")

        if warnings:
            status = StepStatus.WARN
            detail = f"{len(warnings)} margin warning(s): {'; '.join(warnings)}"
        else:
            status = StepStatus.PASS
            detail = f"All {len(ch_results)} lane(s) within margin thresholds"

        r = self._make_result(
            "Disable + analyze",
            2,
            total_steps,
            status,
            detail=detail,
            data={"lanes": lane_data},
        )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
