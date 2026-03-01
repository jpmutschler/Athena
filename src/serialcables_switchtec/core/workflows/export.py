"""Structured result export from recipe runs.

Supports JSON and CSV export formats for recipe results
with device context metadata.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.workflows.models import RecipeSummary


@dataclass(frozen=True)
class DeviceContext:
    """Device metadata captured at export time."""

    device_path: str
    name: str
    device_id: int
    generation: str
    fw_version: str
    timestamp: str


def _make_device_context(
    device_path: str = "",
    name: str = "",
    device_id: int = 0,
    generation: str = "",
    fw_version: str = "",
) -> DeviceContext:
    """Create a DeviceContext with current timestamp."""
    return DeviceContext(
        device_path=device_path,
        name=name,
        device_id=device_id,
        generation=generation,
        fw_version=fw_version,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )


class RecipeRunExporter:
    """Exports recipe run results to JSON and CSV files."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def export_json(
        self, summary: RecipeSummary, context: DeviceContext,
    ) -> Path:
        """Export recipe results as JSON.

        Args:
            summary: Completed recipe summary.
            context: Device context metadata.

        Returns:
            Path to the written JSON file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        recipe_slug = summary.recipe_name.lower().replace(" ", "_")
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{recipe_slug}_{ts}.json"
        path = self._output_dir / filename

        results_data = []
        for r in summary.results:
            results_data.append({
                "step": r.step,
                "step_index": r.step_index,
                "total_steps": r.total_steps,
                "status": r.status.name,
                "criticality": r.criticality.value,
                "detail": r.detail,
                "data": r.data,
            })

        doc = {
            "device": asdict(context),
            "recipe": recipe_slug,
            "summary": {
                "recipe_name": summary.recipe_name,
                "total_steps": summary.total_steps,
                "passed": summary.passed,
                "failed": summary.failed,
                "warnings": summary.warnings,
                "skipped": summary.skipped,
                "aborted": summary.aborted,
                "elapsed_s": summary.elapsed_s,
            },
            "results": results_data,
            "timestamp": context.timestamp,
        }

        path.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
        return path

    def export_csv(
        self, summary: RecipeSummary, context: DeviceContext,
    ) -> Path:
        """Export recipe results as CSV with one row per step.

        Args:
            summary: Completed recipe summary.
            context: Device context metadata.

        Returns:
            Path to the written CSV file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        recipe_slug = summary.recipe_name.lower().replace(" ", "_")
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"{recipe_slug}_{ts}.csv"
        path = self._output_dir / filename

        fieldnames = [
            "recipe_name",
            "step",
            "step_index",
            "total_steps",
            "status",
            "criticality",
            "detail",
            "device_name",
            "generation",
            "fw_version",
            "timestamp",
        ]

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in summary.results:
                writer.writerow({
                    "recipe_name": summary.recipe_name,
                    "step": r.step,
                    "step_index": r.step_index,
                    "total_steps": r.total_steps,
                    "status": r.status.name,
                    "criticality": r.criticality.value,
                    "detail": r.detail,
                    "device_name": context.name,
                    "generation": context.generation,
                    "fw_version": context.fw_version,
                    "timestamp": context.timestamp,
                })

        return path
