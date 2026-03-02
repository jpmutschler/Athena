"""Save/load/list/delete workflow definitions as JSON files."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from serialcables_switchtec.core.workflows.workflow_models import WorkflowDefinition

_MAX_NAME_LENGTH = 200


class WorkflowStorage:
    """Manages workflow definition persistence in ``~/.switchtec/workflows/``."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path.home() / ".switchtec" / "workflows"

    def save(self, definition: WorkflowDefinition) -> Path:
        """Write *definition* to disk, setting timestamps.

        Returns the path of the saved JSON file.
        """
        self._base_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(tz=timezone.utc).isoformat()

        updated = definition.model_copy(
            update={
                "created_at": definition.created_at or now,
                "updated_at": now,
            },
        )

        path = self._safe_path(self._slugify(definition.name))
        path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, name: str) -> WorkflowDefinition:
        """Load a workflow by name.

        Raises ``FileNotFoundError`` if the workflow does not exist.
        """
        path = self._safe_path(self._slugify(name))
        if not path.exists():
            msg = f"Workflow not found: {name!r}"
            raise FileNotFoundError(msg)
        return WorkflowDefinition.model_validate_json(
            path.read_text(encoding="utf-8"),
        )

    def list_workflows(self) -> list[str]:
        """Return sorted stem names of all saved workflows."""
        if not self._base_dir.exists():
            return []
        return sorted(p.stem for p in self._base_dir.glob("*.json"))

    def delete(self, name: str) -> None:
        """Delete a saved workflow by name (no-op if missing)."""
        path = self._safe_path(self._slugify(name))
        if path.exists():
            path.unlink()

    def _safe_path(self, slug: str) -> Path:
        """Build a path confined to ``_base_dir``, raising on escape."""
        path = (self._base_dir / f"{slug}.json").resolve()
        base = self._base_dir.resolve()
        if not path.is_relative_to(base):
            msg = f"Path escapes workflow directory: {path}"
            raise ValueError(msg)
        return path

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert a workflow name to a filesystem-safe slug."""
        truncated = name[:_MAX_NAME_LENGTH]
        slug = truncated.lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")
        return slug or "unnamed"
