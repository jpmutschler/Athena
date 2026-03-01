"""Shared test fixtures with FakeLibrary mock."""

from __future__ import annotations

import pytest

from serialcables_switchtec.bindings import library as library_module
from serialcables_switchtec.testing import FakeLibrary, reset_rate_limiters


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Clear all API rate limiter state between tests."""
    reset_rate_limiters()


@pytest.fixture
def fake_lib():
    """Provide a FakeLibrary instance."""
    return FakeLibrary()


@pytest.fixture
def mock_library(fake_lib, monkeypatch):
    """Patch the library module to use FakeLibrary."""
    monkeypatch.setattr(library_module, "_lib_instance", fake_lib)
    yield fake_lib
    monkeypatch.setattr(library_module, "_lib_instance", None)


@pytest.fixture
def device(mock_library):
    """Provide a SwitchtecDevice using the mock library."""
    from serialcables_switchtec.core.device import SwitchtecDevice

    return SwitchtecDevice(handle=0xDEADBEEF, lib=mock_library)
