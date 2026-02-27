"""Tests for library loader."""

from __future__ import annotations

import pytest

from serialcables_switchtec.bindings.library import (
    LibraryLoadError,
    get_library,
    reset_library,
)


class TestGetLibrary:
    def test_not_loaded_raises(self):
        reset_library()
        with pytest.raises(LibraryLoadError, match="not loaded"):
            get_library()

    def test_returns_loaded_lib(self, mock_library):
        lib = get_library()
        assert lib is mock_library
