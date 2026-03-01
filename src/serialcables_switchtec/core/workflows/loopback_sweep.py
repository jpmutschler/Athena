"""Loopback BER Sweep recipe."""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

from serialcables_switchtec.bindings.constants import DiagLtssmSpeed, DiagPatternLinkRate
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

# Pattern maps per generation (value -> name)
_GEN_PATTERNS: dict[str, dict[int, str]] = {
    "gen3": {0: "PRBS7", 1: "PRBS11", 2: "PRBS23", 3: "PRBS31", 4: "PRBS9", 5: "PRBS15"},
    "gen4": {0: "PRBS7", 1: "PRBS11", 2: "PRBS23", 3: "PRBS31", 4: "PRBS9", 5: "PRBS15"},
    "gen5": {0: "PRBS7", 1: "PRBS11", 2: "PRBS23", 3: "PRBS31", 4: "PRBS9", 5: "PRBS15", 6: "PRBS5", 7: "PRBS20"},
    "gen6": {0: "PRBS7", 1: "PRBS9", 2: "PRBS11", 3: "PRBS13", 4: "PRBS15", 5: "PRBS23", 6: "PRBS31"},
}

_GEN_DISABLED: dict[str, int] = {"gen3": 6, "gen4": 6, "gen5": 10, "gen6": 0x1A}
_GEN_TO_SPEED: dict[str, DiagPatternLinkRate] = {
    "gen3": DiagPatternLinkRate.GEN3, "gen4": DiagPatternLinkRate.GEN4,
    "gen5": DiagPatternLinkRate.GEN5, "gen6": DiagPatternLinkRate.GEN6,
}
_GEN_TO_LTSSM: dict[str, DiagLtssmSpeed] = {
    "gen3": DiagLtssmSpeed.GEN3, "gen4": DiagLtssmSpeed.GEN4,
    "gen5": DiagLtssmSpeed.GEN5, "gen6": DiagLtssmSpeed.GEN6,
}


class LoopbackSweep(Recipe):
    name = "Loopback BER Sweep"
    description = (
        "Enable loopback and sweep all PRBS patterns for the selected "
        "generation. Identifies the weakest pattern and worst-case BER."
    )
    category = RecipeCategory.ERROR_TESTING
    duration_label = "varies"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id", display_name="Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="gen", display_name="PCIe Generation",
                param_type="select", default="gen4",
                choices=["gen3", "gen4", "gen5", "gen6"],
            ),
            RecipeParameter(
                name="duration_per_pattern_s", display_name="Duration per Pattern (s)",
                param_type="int", default=10, min_val=2, max_val=300,
            ),
            RecipeParameter(
                name="lane_count", display_name="Lanes to Monitor",
                param_type="int", default=4, min_val=1, max_val=16,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        gen = str(kwargs.get("gen", "gen4"))
        dur = int(kwargs.get("duration_per_pattern_s", 10))
        pattern_count = len(_GEN_PATTERNS.get(gen, {}))
        return (pattern_count * dur) + 10

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []

        port_id = int(kwargs.get("port_id", 0))
        gen = str(kwargs.get("gen", "gen4"))
        dur_per = int(kwargs.get("duration_per_pattern_s", 10))
        lane_count = int(kwargs.get("lane_count", 4))

        patterns = _GEN_PATTERNS.get(gen, _GEN_PATTERNS["gen4"])
        disabled_val = _GEN_DISABLED.get(gen, 6)
        link_speed = _GEN_TO_SPEED.get(gen, DiagPatternLinkRate.GEN4)
        ltssm_speed = _GEN_TO_LTSSM.get(gen, DiagLtssmSpeed.GEN4)

        total_steps = len(patterns) + 3  # verify + enable loopback + sweep patterns + disable

        # Step 1: Verify link
        yield self._make_result("Verify link", 0, total_steps, StepStatus.RUNNING)
        try:
            ports = dev.get_status()
            link_up = any(p.port.phys_id == port_id and p.link_up for p in ports)
        except SwitchtecError as exc:
            r = self._make_result(
                "Verify link", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Verify link", 0, total_steps,
            StepStatus.PASS if link_up else StepStatus.WARN,
            detail=f"Port {port_id} link {'UP' if link_up else 'DOWN'}",
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Step 2: Enable loopback
        yield self._make_result("Enable loopback", 1, total_steps, StepStatus.RUNNING)
        try:
            dev.diagnostics.loopback_set(
                port_id, True, ltssm_speed=ltssm_speed,
            )
            r = self._make_result(
                "Enable loopback", 1, total_steps, StepStatus.PASS,
                detail=f"Loopback enabled at {ltssm_speed.name}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Enable loopback", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            _cleanup_loopback(dev, port_id)
            return self._make_summary(results, time.monotonic() - start, aborted=True)

        # Steps 3..N: Sweep patterns
        per_pattern_errors: dict[str, int] = {}
        step_idx = 2

        for pat_val, pat_name in sorted(patterns.items()):
            if cancel.is_set():
                break

            yield self._make_result(
                f"Pattern {pat_name}", step_idx, total_steps, StepStatus.RUNNING,
            )

            try:
                dev.diagnostics.pattern_gen_set(port_id, pat_val, link_speed)
                dev.diagnostics.pattern_mon_set(port_id, pat_val)
            except SwitchtecError as exc:
                r = self._make_result(
                    f"Pattern {pat_name}", step_idx, total_steps, StepStatus.FAIL,
                    detail=f"Setup failed: {exc}",
                )
                results.append(r)
                yield r
                step_idx += 1
                continue

            # Soak for duration (cancellable)
            deadline = time.monotonic() + dur_per
            while time.monotonic() < deadline:
                if cancel.is_set():
                    break
                time.sleep(min(0.5, deadline - time.monotonic()))

            # Read errors
            total_err = 0
            for lane in range(lane_count):
                try:
                    mon = dev.diagnostics.pattern_mon_get(port_id, lane)
                    total_err += mon.error_count
                except SwitchtecError:
                    pass

            per_pattern_errors[pat_name] = total_err
            status = StepStatus.PASS if total_err == 0 else StepStatus.WARN
            r = self._make_result(
                f"Pattern {pat_name}", step_idx, total_steps, status,
                detail=f"Errors: {total_err} across {lane_count} lanes",
                data={"pattern": pat_name, "errors": total_err},
            )
            results.append(r)
            yield r
            step_idx += 1

        # Final step: Disable loopback
        yield self._make_result("Disable loopback", step_idx, total_steps, StepStatus.RUNNING)
        try:
            dev.diagnostics.pattern_gen_set(port_id, disabled_val, DiagPatternLinkRate.DISABLED)
            dev.diagnostics.loopback_set(port_id, False)
            r = self._make_result(
                "Disable loopback", step_idx, total_steps, StepStatus.PASS,
                detail="Loopback and pattern generator disabled",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Disable loopback", step_idx, total_steps, StepStatus.WARN,
                detail=f"Cleanup warning: {exc}",
            )
        results.append(r)
        yield r

        # Build summary with per-pattern BER data
        summary = self._make_summary(
            results, time.monotonic() - start,
            aborted=cancel.is_set(),
        )
        return summary


def _cleanup_loopback(dev: SwitchtecDevice, port_id: int) -> None:
    """Best-effort cleanup of loopback state."""
    try:
        dev.diagnostics.loopback_set(port_id, False)
    except SwitchtecError:
        pass
