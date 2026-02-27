"""Tests for library loader."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from serialcables_switchtec.bindings.library import (
    _find_library_paths,
    get_library,
    load_library,
    reset_library,
)
from serialcables_switchtec.exceptions import LibraryLoadError
import serialcables_switchtec.bindings.library as lib_module


@pytest.fixture(autouse=True)
def _reset_lib():
    """Ensure library state is clean before and after each test."""
    reset_library()
    yield
    reset_library()


class TestGetLibrary:
    def test_not_loaded_raises(self) -> None:
        with pytest.raises(LibraryLoadError, match="not loaded"):
            get_library()

    def test_returns_loaded_lib(self, mock_library) -> None:
        lib = get_library()
        assert lib is mock_library


class TestFindLibraryPaths:
    def test_includes_vendor_dir(self) -> None:
        """Verify the vendor/switchtec path is among the candidates."""
        candidates = _find_library_paths()
        vendor_strs = [str(c) for c in candidates]
        assert any("vendor" in s and "switchtec" in s for s in vendor_strs), (
            f"Expected vendor/switchtec path in candidates, got: {vendor_strs}"
        )

    def test_includes_native_dir(self) -> None:
        """Verify the _native/ path is among the candidates."""
        candidates = _find_library_paths()
        candidate_strs = [str(c) for c in candidates]
        assert any("_native" in s for s in candidate_strs), (
            f"Expected _native path in candidates, got: {candidate_strs}"
        )

    def test_native_before_vendor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify _native/ path comes before vendor path in search order."""
        monkeypatch.delenv("SWITCHTEC_LIB_DIR", raising=False)
        candidates = _find_library_paths()
        candidate_strs = [str(c) for c in candidates]

        native_idx = next(
            (i for i, s in enumerate(candidate_strs) if "_native" in s), None
        )
        vendor_idx = next(
            (i for i, s in enumerate(candidate_strs) if "vendor" in s), None
        )
        assert native_idx is not None, "No _native path found in candidates"
        assert vendor_idx is not None, "No vendor path found in candidates"
        assert native_idx < vendor_idx, (
            f"_native (index {native_idx}) should come before vendor "
            f"(index {vendor_idx}) in search order"
        )

    def test_env_var_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When SWITCHTEC_LIB_DIR is set, its path appears in candidates."""
        fake_dir = "/opt/custom/switchtec"
        monkeypatch.setenv("SWITCHTEC_LIB_DIR", fake_dir)
        candidates = _find_library_paths()
        # Path normalizes separators on Windows, so compare using Path
        normalized = str(Path(fake_dir))
        candidate_strs = [str(c) for c in candidates]
        assert any(normalized in s for s in candidate_strs), (
            f"Expected {normalized} in candidates, got: {candidate_strs}"
        )

    def test_env_var_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When SWITCHTEC_LIB_DIR is not set, no env-based path appears."""
        monkeypatch.delenv("SWITCHTEC_LIB_DIR", raising=False)
        candidates = _find_library_paths()
        # The env var sentinel directory should not be present.
        # We verify by checking no candidate contains a path that would
        # only appear if the env var contributed something unique.
        # Since vendor and system paths are always present, we just
        # confirm the function completes and returns a list.
        assert isinstance(candidates, list)
        # All candidates should be from vendor or system paths, not env.
        # Re-run with env set to see the difference.
        monkeypatch.setenv("SWITCHTEC_LIB_DIR", "/unique_test_sentinel_path")
        candidates_with_env = _find_library_paths()
        sentinel_candidates = [
            c for c in candidates_with_env
            if "unique_test_sentinel_path" in str(c)
        ]
        assert len(sentinel_candidates) > 0
        # Original candidates should not have the sentinel
        assert not any(
            "unique_test_sentinel_path" in str(c) for c in candidates
        )


class TestLoadLibrary:
    def test_explicit_path_not_found(self) -> None:
        """Loading from a nonexistent explicit path raises LibraryLoadError."""
        with pytest.raises(LibraryLoadError, match="not found"):
            load_library(path="/nonexistent/path.so")

    def test_cached_returns_same_instance(self, mock_library) -> None:
        """Once loaded, subsequent calls return the same cached instance."""
        # mock_library fixture sets _lib_instance via monkeypatch
        first = load_library()
        second = load_library()
        assert first is second
        assert first is mock_library

    def test_no_candidates_raises(self) -> None:
        """When no candidate paths exist, raises LibraryLoadError."""
        with patch.object(lib_module, "_find_library_paths", return_value=[]):
            # Also need to patch ctypes.CDLL to prevent system fallback
            with patch("ctypes.CDLL", side_effect=OSError("not found")):
                with pytest.raises(LibraryLoadError, match="not found"):
                    load_library()


class TestResetLibrary:
    def test_resets_instance_to_none(self, mock_library) -> None:
        """reset_library() clears the cached instance."""
        # Confirm it's loaded
        assert get_library() is mock_library
        reset_library()
        assert lib_module._lib_instance is None
        # get_library should now fail
        with pytest.raises(LibraryLoadError, match="not loaded"):
            get_library()
