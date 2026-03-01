"""Link Training Debug recipe."""

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
from serialcables_switchtec.core.ltssm_analyzer import LtssmPathAnalyzer
from serialcables_switchtec.exceptions import SwitchtecError


class LinkTrainingDebug(Recipe):
    name = "Link Training Debug"
    description = (
        "Debug link training issues by reading port status, LTSSM state, "
        "and LTSSM transition log for a single port."
    )
    category = RecipeCategory.LINK_HEALTH
    duration_label = "~5s"

    def parameters(self) -> list[RecipeParameter]:
        return [
            RecipeParameter(
                name="port_id",
                display_name="Port ID",
                param_type="int",
                default=0,
                min_val=0,
                max_val=59,
            ),
        ]

    def estimated_duration_s(self, **kwargs: object) -> float:
        return 5.0

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

        # Step 1: Read port status
        yield self._make_result(
            "Read port status",
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
            port_status_list = dev.get_status()
        except SwitchtecError as exc:
            r = self._make_result(
                "Read port status",
                0,
                total_steps,
                StepStatus.FAIL,
                detail=str(exc),
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        target_port = None
        for p in port_status_list:
            if p.port.phys_id == port_id:
                target_port = p
                break

        if target_port is None:
            r = self._make_result(
                "Read port status",
                0,
                total_steps,
                StepStatus.FAIL,
                detail=f"Port {port_id} not found",
                criticality=StepCriticality.CRITICAL,
            )
            results.append(r)
            yield r
            return self._make_summary(results, time.monotonic() - start)

        r = self._make_result(
            "Read port status",
            0,
            total_steps,
            StepStatus.PASS,
            detail=(
                f"Port {port_id} — link_up={target_port.link_up}, "
                f"rate={target_port.link_rate}, "
                f"width=x{target_port.neg_lnk_width}"
            ),
            data={
                "link_up": target_port.link_up,
                "link_rate": target_port.link_rate,
                "neg_lnk_width": target_port.neg_lnk_width,
            },
        )
        results.append(r)
        yield r

        # Step 2: Read LTSSM state
        yield self._make_result(
            "Read LTSSM state",
            1,
            total_steps,
            StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=True,
            )

        r = self._make_result(
            "Read LTSSM state",
            1,
            total_steps,
            StepStatus.PASS,
            detail=f"Current LTSSM state: {target_port.ltssm_str}",
            data={"ltssm": target_port.ltssm, "ltssm_str": target_port.ltssm_str},
        )
        results.append(r)
        yield r

        # Step 3: Read LTSSM log
        yield self._make_result(
            "Read LTSSM log",
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

        try:
            dev.diagnostics.ltssm_clear(port_id)
            ltssm_entries = dev.diagnostics.ltssm_log(port_id)
            transition_count = len(ltssm_entries)
            status = StepStatus.PASS if transition_count == 0 else StepStatus.WARN
            r = self._make_result(
                "Read LTSSM log",
                2,
                total_steps,
                status,
                detail=f"{transition_count} LTSSM transitions recorded",
                data={
                    "transition_count": transition_count,
                    "entries": [
                        {
                            "state": e.link_state_str,
                            "rate": e.link_rate,
                            "width": e.link_width,
                        }
                        for e in ltssm_entries[:10]
                    ],
                },
            )
        except SwitchtecError as exc:
            r = self._make_result(
                "Read LTSSM log",
                2,
                total_steps,
                StepStatus.WARN,
                detail=f"Could not read LTSSM log: {exc}",
            )
            results.append(r)
            yield r
            # Continue to analysis with no entries
            ltssm_entries = []
            transition_count = 0
        else:
            results.append(r)
            yield r

        # Step 4: Analyze
        yield self._make_result(
            "Analyze",
            3,
            total_steps,
            StepStatus.RUNNING,
        )
        if cancel.is_set():
            return self._make_summary(
                results,
                time.monotonic() - start,
                aborted=True,
            )

        # Run LTSSM path analysis
        analyzer = LtssmPathAnalyzer()
        analysis = analyzer.analyze(ltssm_entries)

        link_up = target_port.link_up
        if link_up:
            detail = "Link is UP — no training issue detected"
            status = StepStatus.PASS
        elif transition_count > 0:
            if analysis.verdict == "FAIL":
                detail = (
                    f"Link is DOWN with {transition_count} transitions — "
                    f"{analysis.summary}"
                )
                status = StepStatus.FAIL
            else:
                detail = f"Link is DOWN with {transition_count} transitions — likely training failure"
                status = StepStatus.WARN
        else:
            detail = "Link is DOWN with no transitions — port may be unused or disconnected"
            status = StepStatus.PASS

        r = self._make_result(
            "Analyze",
            3,
            total_steps,
            status,
            detail=detail,
            data={
                "link_up": link_up,
                "transition_count": transition_count,
                "ltssm_verdict": analysis.verdict,
                "ltssm_patterns": [
                    {"name": p.name, "severity": p.severity, "description": p.description}
                    for p in analysis.patterns
                ],
            },
        )
        results.append(r)
        yield r

        return self._make_summary(
            results,
            time.monotonic() - start,
            aborted=cancel.is_set(),
        )
