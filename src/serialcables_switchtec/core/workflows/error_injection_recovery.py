"""Error Injection + Recovery recipe."""

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

_POLL_INTERVAL = 0.5


class ErrorInjectionRecovery(Recipe):
    name = "Error Injection + Recovery"
    description = (
        "Inject a PCIe error on a port and monitor link recovery "
        "and LTSSM transitions."
    )
    category = RecipeCategory.ERROR_TESTING
    duration_label = "~5s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id", display_name="Port ID",
                param_type="int", default=0, min_val=0, max_val=59,
            ),
            RecipeParameter(
                name="injection_type", display_name="Injection Type",
                param_type="select", default="dllp_crc",
                choices=["dllp_crc", "tlp_lcrc", "tlp_seq_num", "cto"],
            ),
            RecipeParameter(
                name="verify_duration_s",
                display_name="Verify Duration (s)",
                param_type="int", default=5, min_val=1, max_val=30,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return float(kwargs.get("verify_duration_s", 5)) + 2

    def cleanup(self, dev: SwitchtecDevice, **kwargs: object) -> None:
        port_id = int(kwargs.get("port_id", 0))
        injection_type = str(kwargs.get("injection_type", "dllp_crc"))
        _disable_injection(dev, port_id, injection_type)

    def run(
        self,
        dev: SwitchtecDevice,
        cancel: threading.Event,
        **kwargs: object,
    ) -> Generator[RecipeResult, None, RecipeSummary]:
        start = time.monotonic()
        results: list[RecipeResult] = []
        total_steps = 4

        port_id = int(kwargs.get("port_id", 0))
        injection_type = str(kwargs.get("injection_type", "dllp_crc"))
        verify_duration_s = int(kwargs.get("verify_duration_s", 5))

        # Step 1: Verify link up
        yield self._make_result(
            "Verify link up", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            ports = dev.get_status()
        except SwitchtecError as exc:
            r = self._make_result(
                "Verify link up", 0, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        target = None
        for p in ports:
            if p.port.phys_id == port_id:
                target = p
                break

        if target is None or not target.link_up:
            detail = (
                f"Port {port_id} not found"
                if target is None
                else f"Port {port_id} is DOWN"
            )
            r = self._make_result(
                "Verify link up", 0, total_steps, StepStatus.FAIL,
                detail=detail, criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Verify link up", 0, total_steps, StepStatus.PASS,
            detail=f"Port {port_id} UP",
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 2: Clear LTSSM + inject error
        yield self._make_result(
            "Inject error", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            dev.diagnostics.ltssm_clear(port_id)
            _perform_injection(dev, port_id, injection_type)
            r = self._make_result(
                "Inject error", 1, total_steps, StepStatus.PASS,
                detail=f"Injected {injection_type} on port {port_id}",
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Inject error", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)
        results.append(r)
        yield r

        if cancel.is_set():
            _disable_injection(dev, port_id, injection_type)
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Monitor link recovery
        yield self._make_result(
            "Monitor recovery", 2, total_steps, StepStatus.RUNNING,
        )
        link_went_down = False
        link_recovered = False
        poll_start = time.monotonic()

        while time.monotonic() - poll_start < verify_duration_s:
            if cancel.is_set():
                break
            try:
                status_list = dev.get_status()
                current_up = any(
                    p.port.phys_id == port_id and p.link_up
                    for p in status_list
                )
                if not current_up:
                    link_went_down = True
                elif link_went_down:
                    link_recovered = True
            except SwitchtecError:
                pass
            remaining = verify_duration_s - (time.monotonic() - poll_start)
            time.sleep(max(0, min(_POLL_INTERVAL, remaining)))

        detail_parts = []
        if link_went_down:
            detail_parts.append("link went down")
        if link_recovered:
            detail_parts.append("link recovered")
        if not link_went_down:
            detail_parts.append("link stayed up")

        if link_went_down and not link_recovered:
            monitor_status = StepStatus.FAIL
        elif link_went_down and link_recovered:
            monitor_status = StepStatus.WARN
        else:
            monitor_status = StepStatus.PASS

        r = self._make_result(
            "Monitor recovery", 2, total_steps, monitor_status,
            detail=", ".join(detail_parts),
            data={
                "link_went_down": link_went_down,
                "link_recovered": link_recovered,
            },
        )
        results.append(r)
        yield r

        if cancel.is_set():
            _disable_injection(dev, port_id, injection_type)
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 4: Check LTSSM transitions
        yield self._make_result(
            "Check LTSSM", 3, total_steps, StepStatus.RUNNING,
        )
        try:
            ltssm_entries = dev.diagnostics.ltssm_log(port_id)
            transition_count = len(ltssm_entries)
        except SwitchtecError as exc:
            r = self._make_result(
                "Check LTSSM", 3, total_steps, StepStatus.WARN,
                detail=f"Could not read LTSSM: {exc}",
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        # Final link check
        try:
            final_ports = dev.get_status()
            final_up = any(
                p.port.phys_id == port_id and p.link_up
                for p in final_ports
            )
        except SwitchtecError:
            final_up = False

        if final_up and not link_went_down and transition_count == 0:
            status = StepStatus.PASS
            detail = "Link stayed up, no LTSSM activity"
        elif final_up and (link_recovered or transition_count > 0):
            status = StepStatus.WARN
            detail = (
                f"Link recovered with {transition_count} "
                f"LTSSM transitions"
            )
        else:
            status = StepStatus.FAIL
            detail = (
                f"Link still down after {transition_count} "
                f"LTSSM transitions"
            )

        r = self._make_result(
            "Check LTSSM", 3, total_steps, status,
            detail=detail,
            data={
                "transition_count": transition_count,
                "link_up_final": final_up,
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )


def _perform_injection(
    dev: SwitchtecDevice, port_id: int, injection_type: str,
) -> None:
    """Perform error injection based on type."""
    if injection_type == "dllp_crc":
        dev.injector.inject_dllp_crc(port_id, True, 1)
        time.sleep(0.05)  # Allow injection to take effect before disabling
        dev.injector.inject_dllp_crc(port_id, False, 0)
    elif injection_type == "tlp_lcrc":
        dev.injector.inject_tlp_lcrc(port_id, True, 1)
        time.sleep(0.05)  # Allow injection to take effect before disabling
        dev.injector.inject_tlp_lcrc(port_id, False, 0)
    elif injection_type == "tlp_seq_num":
        dev.injector.inject_tlp_seq_num(port_id)
    elif injection_type == "cto":
        dev.injector.inject_cto(port_id)


def _disable_injection(
    dev: SwitchtecDevice, port_id: int, injection_type: str,
) -> None:
    """Best-effort cleanup: disable error injection."""
    try:
        if injection_type == "dllp_crc":
            dev.injector.inject_dllp_crc(port_id, False, 0)
        elif injection_type == "tlp_lcrc":
            dev.injector.inject_tlp_lcrc(port_id, False, 0)
    except SwitchtecError:
        pass
