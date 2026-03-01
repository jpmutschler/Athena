"""Tests for recipe result export (JSON and CSV)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from serialcables_switchtec.core.workflows.export import (
    DeviceContext,
    RecipeRunExporter,
    _make_device_context,
)
from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepCriticality,
    StepStatus,
)


def _make_test_summary() -> RecipeSummary:
    """Create a minimal RecipeSummary for testing."""
    results = [
        RecipeResult(
            recipe_name="Test Recipe",
            step="Step 1",
            step_index=0,
            total_steps=2,
            status=StepStatus.PASS,
            criticality=StepCriticality.NON_CRITICAL,
            detail="OK",
            data={"key": "value"},
        ),
        RecipeResult(
            recipe_name="Test Recipe",
            step="Step 2",
            step_index=1,
            total_steps=2,
            status=StepStatus.WARN,
            criticality=StepCriticality.NON_CRITICAL,
            detail="Minor issue",
            data=None,
        ),
    ]
    return RecipeSummary(
        recipe_name="Test Recipe",
        total_steps=2,
        passed=1,
        failed=0,
        warnings=1,
        skipped=0,
        aborted=False,
        elapsed_s=1.5,
        results=results,
    )


def _make_test_context() -> DeviceContext:
    return DeviceContext(
        device_path="/dev/switchtec0",
        name="PSX 48XG6",
        device_id=0x4000,
        generation="GEN6",
        fw_version="4.20",
        timestamp="2026-03-01T00:00:00+00:00",
    )


class TestDeviceContext:
    def test_frozen_dataclass(self):
        ctx = _make_test_context()
        assert ctx.name == "PSX 48XG6"
        try:
            ctx.name = "other"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised

    def test_make_device_context_has_timestamp(self):
        ctx = _make_device_context(name="test", generation="GEN4")
        assert ctx.timestamp
        assert "T" in ctx.timestamp


class TestRecipeRunExporterJson:
    def test_export_json_creates_file(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_json(summary, context)
        assert path.exists()
        assert path.suffix == ".json"

    def test_export_json_content_structure(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_json(summary, context)
        doc = json.loads(path.read_text(encoding="utf-8"))

        assert "device" in doc
        assert doc["device"]["name"] == "PSX 48XG6"
        assert doc["device"]["generation"] == "GEN6"
        assert doc["recipe"] == "test_recipe"
        assert "summary" in doc
        assert doc["summary"]["passed"] == 1
        assert doc["summary"]["warnings"] == 1
        assert doc["summary"]["elapsed_s"] == 1.5
        assert "results" in doc
        assert len(doc["results"]) == 2
        assert doc["results"][0]["step"] == "Step 1"
        assert doc["results"][0]["status"] == "PASS"
        assert doc["results"][1]["status"] == "WARN"

    def test_export_json_creates_output_dir(self, tmp_path: Path):
        nested = tmp_path / "sub" / "dir"
        exporter = RecipeRunExporter(nested)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_json(summary, context)
        assert nested.exists()
        assert path.exists()

    def test_export_json_filename_contains_recipe_slug(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_json(summary, context)
        assert "test_recipe" in path.name

    def test_export_json_result_data_field(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_json(summary, context)
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["results"][0]["data"] == {"key": "value"}
        assert doc["results"][1]["data"] is None


class TestRecipeRunExporterCsv:
    def test_export_csv_creates_file(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_csv(summary, context)
        assert path.exists()
        assert path.suffix == ".csv"

    def test_export_csv_has_header_and_rows(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_csv(summary, context)
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["step"] == "Step 1"
        assert rows[0]["status"] == "PASS"
        assert rows[0]["device_name"] == "PSX 48XG6"
        assert rows[1]["step"] == "Step 2"
        assert rows[1]["status"] == "WARN"

    def test_export_csv_creates_output_dir(self, tmp_path: Path):
        nested = tmp_path / "nested"
        exporter = RecipeRunExporter(nested)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_csv(summary, context)
        assert nested.exists()
        assert path.exists()

    def test_export_csv_filename_contains_recipe_slug(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_csv(summary, context)
        assert "test_recipe" in path.name

    def test_export_csv_fieldnames(self, tmp_path: Path):
        exporter = RecipeRunExporter(tmp_path)
        summary = _make_test_summary()
        context = _make_test_context()

        path = exporter.export_csv(summary, context)
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        assert "recipe_name" in fieldnames
        assert "step" in fieldnames
        assert "status" in fieldnames
        assert "device_name" in fieldnames
        assert "generation" in fieldnames
        assert "fw_version" in fieldnames
        assert "timestamp" in fieldnames
