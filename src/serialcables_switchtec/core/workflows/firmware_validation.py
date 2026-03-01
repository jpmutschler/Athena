"""Firmware Validation recipe."""

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

_CRITICAL_PARTITIONS = ("boot", "img", "cfg")


class FirmwareValidation(Recipe):
    name = "Firmware Validation"
    description = (
        "Validate firmware version, partition integrity, and "
        "boot read-only status."
    )
    category = RecipeCategory.CONFIGURATION
    duration_label = "~2s"

    def parameters(self) -> list[RecipeParameter]:
        return []

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

        # Step 1: Read firmware version
        yield self._make_result(
            "Read firmware version", 0, total_steps, StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        try:
            fw_version = dev.firmware.get_fw_version()
            r = self._make_result(
                "Read firmware version", 0, total_steps, StepStatus.PASS,
                detail=f"Firmware version: {fw_version}",
                data={"fw_version": fw_version},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read firmware version", 0, total_steps, StepStatus.FAIL,
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

        # Step 2: Check partition summary
        yield self._make_result(
            "Check partitions", 1, total_steps, StepStatus.RUNNING,
        )
        try:
            part_summary = dev.firmware.get_part_summary()
        except SwitchtecError as exc:
            r = self._make_result(
                "Check partitions", 1, total_steps, StepStatus.FAIL,
                detail=str(exc), criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        invalid_parts: list[str] = []
        part_data: dict[str, object] = {}
        for part_name in _CRITICAL_PARTITIONS:
            part_info = getattr(part_summary, part_name, None)
            if part_info is None:
                invalid_parts.append(part_name)
                part_data[part_name] = {"valid": False, "reason": "missing"}
                continue
            active = part_info.active
            if active is None or not active.valid:
                invalid_parts.append(part_name)
                reason = "no active image" if active is None else "invalid"
                part_data[part_name] = {"valid": False, "reason": reason}
            else:
                part_data[part_name] = {
                    "valid": True,
                    "version": active.version,
                    "read_only": active.read_only,
                }

        if invalid_parts:
            status = StepStatus.WARN
            detail = (
                f"Invalid partitions: {', '.join(invalid_parts)}"
            )
        else:
            status = StepStatus.PASS
            detail = "All critical partitions valid"

        r = self._make_result(
            "Check partitions", 1, total_steps, status,
            detail=detail, data={"partitions": part_data},
        )
        results.append(r)
        yield r

        if cancel.is_set():
            return self._make_summary(
                results, time.monotonic() - start, aborted=True,
            )

        # Step 3: Check boot read-only
        yield self._make_result(
            "Check boot RO", 2, total_steps, StepStatus.RUNNING,
        )
        try:
            boot_ro = dev.firmware.is_boot_ro()
            if boot_ro:
                status = StepStatus.PASS
                detail = "Boot partition is read-only (production)"
            else:
                status = StepStatus.INFO
                detail = "Boot partition is writable (development)"
            r = self._make_result(
                "Check boot RO", 2, total_steps, status,
                detail=detail,
                data={"is_boot_ro": boot_ro},
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Check boot RO", 2, total_steps, StepStatus.WARN,
                detail=f"Could not check boot RO: {exc}",
            )
        results.append(r)
        yield r

        return self._make_summary(
            results, time.monotonic() - start, aborted=cancel.is_set(),
        )
