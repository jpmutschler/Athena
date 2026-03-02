"""Tests for workflow storage (save/load/list/delete)."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStep,
)
from serialcables_switchtec.core.workflows.workflow_storage import WorkflowStorage


@pytest.fixture()
def storage(tmp_path):
    """Create a WorkflowStorage with a temporary base directory."""
    return WorkflowStorage(base_dir=tmp_path)


@pytest.fixture()
def sample_definition():
    """Return a sample WorkflowDefinition for testing."""
    return WorkflowDefinition(
        name="Morning Checkout",
        description="Daily port validation sequence",
        steps=[
            WorkflowStep(recipe_key="link_health_check", params={"port_id": 0}),
            WorkflowStep(recipe_key="thermal_profile", params={"duration_s": 10}),
        ],
        abort_on_critical_fail=True,
    )


class TestSluggify:
    def test_simple_name(self):
        assert WorkflowStorage._slugify("Morning Checkout") == "morning_checkout"

    def test_special_characters(self):
        assert WorkflowStorage._slugify("Test #1 (BER)") == "test_1_ber"

    def test_mixed_case(self):
        assert WorkflowStorage._slugify("MyTest") == "mytest"

    def test_trailing_underscores(self):
        assert WorkflowStorage._slugify("test---") == "test"

    def test_leading_underscores(self):
        assert WorkflowStorage._slugify("---test") == "test"

    def test_empty_name(self):
        assert WorkflowStorage._slugify("") == "unnamed"

    def test_all_special_chars(self):
        assert WorkflowStorage._slugify("@#$%") == "unnamed"


class TestSave:
    def test_save_creates_file(self, storage, tmp_path, sample_definition):
        path = storage.save(sample_definition)
        assert path.exists()
        assert path.name == "morning_checkout.json"
        assert path.parent == tmp_path

    def test_save_creates_parent_directories(self, tmp_path, sample_definition):
        nested = tmp_path / "deep" / "nested" / "dir"
        storage = WorkflowStorage(base_dir=nested)
        path = storage.save(sample_definition)
        assert path.exists()

    def test_save_sets_timestamps(self, storage, sample_definition):
        storage.save(sample_definition)
        loaded = storage.load("Morning Checkout")
        assert loaded.created_at != ""
        assert loaded.updated_at != ""

    def test_save_preserves_created_at_on_update(self, storage, sample_definition):
        storage.save(sample_definition)
        first = storage.load("Morning Checkout")

        # Save again (update)
        updated = sample_definition.model_copy(
            update={"description": "Updated description", "created_at": first.created_at},
        )
        storage.save(updated)
        second = storage.load("Morning Checkout")

        assert second.created_at == first.created_at
        assert second.description == "Updated description"

    def test_save_overwrites_existing(self, storage, sample_definition):
        storage.save(sample_definition)
        updated = sample_definition.model_copy(update={"description": "v2"})
        storage.save(updated)
        loaded = storage.load("Morning Checkout")
        assert loaded.description == "v2"


class TestLoad:
    def test_load_returns_correct_definition(self, storage, sample_definition):
        storage.save(sample_definition)
        loaded = storage.load("Morning Checkout")
        assert loaded.name == "Morning Checkout"
        assert len(loaded.steps) == 2
        assert loaded.steps[0].recipe_key == "link_health_check"
        assert loaded.steps[1].params["duration_s"] == 10

    def test_load_missing_raises_file_not_found(self, storage):
        with pytest.raises(FileNotFoundError):
            storage.load("nonexistent_workflow")

    def test_load_by_slug(self, storage, sample_definition):
        storage.save(sample_definition)
        loaded = storage.load("morning_checkout")
        assert loaded.name == "Morning Checkout"

    def test_load_corrupted_json_raises(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        path = tmp_path / "broken.json"
        path.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(Exception):
            storage.load("broken")

    def test_load_wrong_schema_raises(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path)
        path = tmp_path / "bad_schema.json"
        path.write_text('{"foo": "bar"}', encoding="utf-8")
        with pytest.raises(Exception):
            storage.load("bad_schema")


class TestListWorkflows:
    def test_list_empty(self, storage):
        assert storage.list_workflows() == []

    def test_list_returns_sorted_stems(self, storage):
        storage.save(WorkflowDefinition(name="Zebra", steps=[]))
        storage.save(WorkflowDefinition(name="Alpha", steps=[]))
        storage.save(WorkflowDefinition(name="Middle", steps=[]))
        result = storage.list_workflows()
        assert result == ["alpha", "middle", "zebra"]

    def test_list_with_no_directory(self, tmp_path):
        storage = WorkflowStorage(base_dir=tmp_path / "does_not_exist")
        assert storage.list_workflows() == []


class TestDelete:
    def test_delete_removes_file(self, storage, sample_definition):
        storage.save(sample_definition)
        assert len(storage.list_workflows()) == 1
        storage.delete("Morning Checkout")
        assert len(storage.list_workflows()) == 0

    def test_delete_missing_is_noop(self, storage):
        # Should not raise
        storage.delete("nonexistent")

    def test_delete_by_slug(self, storage, sample_definition):
        storage.save(sample_definition)
        storage.delete("morning_checkout")
        assert len(storage.list_workflows()) == 0
