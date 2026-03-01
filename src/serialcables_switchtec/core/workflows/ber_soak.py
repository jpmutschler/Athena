"""BER Soak Test recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.bindings.constants import (
    DiagPattern,
    DiagPatternGen5,
    DiagPatternGen6,
    DiagPatternLinkRate,
)
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

_DEFAULT_DURATION = 60
_POLL_INTERVAL = 2.0

_DISABLED_BY_SPEED: dict[str, int] = {
    "GEN1": DiagPattern.DISABLED,
    "GEN2": DiagPattern.DISABLED,
    "GEN3": DiagPattern.DISABLED,
    "GEN4": DiagPattern.DISABLED,
    "GEN5": DiagPatternGen5.DISABLED,
    "GEN6": DiagPatternGen6.DISABLED,
}


class BerSoak(Recipe):
    name = "BER Soak Test"
    description = (
        "Run a pattern generator for a configurable duration and measure "
        "bit error rate. Checks for link retraining during the soak."
    )
    category = RecipeCategory.ERROR_TESTING
    duration_label = "60s (configurable)"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id", display_name="Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="pattern", display_name="Pattern Value",
                param_type="int", default=3, min_val=0, max_val=255,
            ),
            RecipeParameter(
                name="link_speed", display_name="Link Speed",
                param_type="select", default="GEN4",
                choices=["GEN1", "GEN2", "GEN3", "GEN4", "GEN5", "GEN6"],
            ),
            RecipeParameter(
                name="duration_s", display_name="Duration (s)",
                param_type="int", default=_DEFAULT_DURATION, min_val=5, max_val=3600,
            ),
            RecipeParameter(
                name="lane_count", display_name="Lanes to Monitor",
                param_type="int", default=4, min_val=1, max_val=16,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return float(kwargs.get("duration_s", _DEFAULT_DURATION)) + 5

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        speed_name = str(kwargs.get("link_speed", "GEN4"))
        port_id = int(kwargs.get("port_id", 0))
        _cleanup_patgen(dev, port_id, speed_name)

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 6

        port_id = int(kwargs.get("port_id", 0))
        pattern = int(kwargs.get("pattern", 3))
        speed_name = str(kwargs.get("link_speed", "GEN4"))
        speed = DiagPatternLinkRate[speed_name]
        duration_s = int(kwargs.get("duration_s", _DEFAULT_DURATION))
        lane_count = int(kwargs.get("lane_count", 4))

        # Step 1: Verify link up
        yield self._make_result("Verify link up", 0, total_steps, StepStatus.RUNNING)
        try:
            ports = dev.get_status()
            link_up = any(p.port.phys_id == port_id and p.link_up for p in ports)
        except SwitchtecError as exc:
            r = self._make_result(
                "Verify link up", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        status = StepStatus.PASS if link_up else StepStatus.WARN
        r = self._make_result(
            "Verify link up", 0, total_steps, status,
            detail=f"Port {port_id} link {'UP' if link_up else 'DOWN'}",
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Step 2: Configure pattern generator
        yield self._make_result("Configure pattern generator", 1, total_steps, StepStatus.RUNNING)
        try:
            dev.diagnostics.pattern_gen_set(port_id, pattern, speed)
            r = self._make_result(
                "Configure pattern generator", 1, total_steps, StepStatus.PASS,
                detail=f"Pattern {pattern} at {speed_name}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Configure pattern generator", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            _cleanup_patgen(dev, port_id, speed_name)
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Step 3: Configure pattern monitor
        yield self._make_result("Configure pattern monitor", 2, total_steps, StepStatus.RUNNING)
        try:
            dev.diagnostics.pattern_mon_set(port_id, pattern)
            r = self._make_result(
                "Configure pattern monitor", 2, total_steps, StepStatus.PASS,
                detail=f"Monitoring pattern {pattern}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Configure pattern monitor", 2, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            _cleanup_patgen(dev, port_id, speed_name)
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Step 4: Soak — poll error counts
        yield self._make_result("BER soak", 3, total_steps, StepStatus.RUNNING)

        # Read baseline error counts before soak
        baseline: dict[int, int] = {}
        for lane in range(lane_count):
            try:
                mon = dev.diagnostics.pattern_mon_get(port_id, lane)
                baseline[lane] = mon.error_count
            except SwitchtecError:
                baseline[lane] = 0

        soak_start = time.monotonic()
        final_errors: dict[int, int] = {}
        total_errors = 0

        while time.monotonic() - soak_start < duration_s:
            if cancel.is_set():
                break
            for lane in range(lane_count):
                try:
                    mon = dev.diagnostics.pattern_mon_get(port_id, lane)
                    final_errors[lane] = mon.error_count
                except SwitchtecError:
                    pass
            time.sleep(max(0, min(_POLL_INTERVAL, duration_s - (time.monotonic() - soak_start))))

        # Compute delta from baseline
        total_errors = sum(
            max(0, final_errors.get(lane, 0) - baseline.get(lane, 0))
            for lane in range(lane_count)
        )
        per_lane_delta = {
            lane: max(0, final_errors.get(lane, 0) - baseline.get(lane, 0))
            for lane in range(lane_count)
        }
        status = StepStatus.PASS if total_errors == 0 else StepStatus.WARN
        r = self._make_result(
            "BER soak", 3, total_steps, status,
            detail=f"Total errors across {lane_count} lanes: {total_errors}",
            data={"per_lane_errors": per_lane_delta, "total_errors": total_errors},
        )
        results.append(r)
        yield r

        if cancel.is_set():
            _cleanup_patgen(dev, port_id, speed_name)
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Step 5: Check LTSSM for retraining
        yield self._make_result("Check LTSSM", 4, total_steps, StepStatus.RUNNING)
        try:
            ltssm_entries = dev.diagnostics.ltssm_log(port_id)
            transition_count = len(ltssm_entries)
            status = StepStatus.PASS if transition_count == 0 else StepStatus.WARN
            r = self._make_result(
                "Check LTSSM", 4, total_steps, status,
                detail=f"{transition_count} LTSSM transitions during soak",
                data={"transition_count": transition_count},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Check LTSSM", 4, total_steps, StepStatus.WARN,
                detail=f"Could not read LTSSM: {exc}",
            )
        results.append(r)
        yield r

        # Step 6: Cleanup
        yield self._make_result("Cleanup", 5, total_steps, StepStatus.RUNNING)
        try:
            disabled_val = _DISABLED_BY_SPEED.get(speed_name, DiagPattern.DISABLED)
            dev.diagnostics.pattern_gen_set(port_id, disabled_val, DiagPatternLinkRate.DISABLED)
            r = self._make_result(
                "Cleanup", 5, total_steps, StepStatus.PASS,
                detail="Pattern generator disabled",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Cleanup", 5, total_steps, StepStatus.WARN,
                detail=f"Cleanup warning: {exc}",
            )
        results.append(r)
        yield r

        return self._make_summary(results, time.monotonic() - start)


def _cleanup_patgen(dev: SwitchtecDevice, port_id: int, speed_name: str) -> None:
    """Best-effort cleanup: disable pattern generator after cancel."""
    try:
        disabled_val = _DISABLED_BY_SPEED.get(speed_name, DiagPattern.DISABLED)
        dev.diagnostics.pattern_gen_set(port_id, disabled_val, DiagPatternLinkRate.DISABLED)
    except SwitchtecError:
        pass
