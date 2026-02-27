"""Tests for api/dependencies.py -- device lookup helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from serialcables_switchtec.api.dependencies import get_device


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_device(name: str = "switchtec0") -> MagicMock:
    """Create a minimal mock SwitchtecDevice."""
    dev = MagicMock()
    dev.name = name
    return dev


# ===========================================================================
# get_device -- success
# ===========================================================================


class TestGetDeviceSuccess:
    """Test get_device returns the correct device from the registry."""

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_returns_device_when_found(self, mock_registry_fn) -> None:
        mock_dev = _make_mock_device("dev0")
        mock_registry_fn.return_value = {
            "dev0": (mock_dev, "/dev/switchtec0"),
        }

        result = get_device("dev0")

        assert result is mock_dev

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_returns_correct_device_among_multiple(
        self, mock_registry_fn
    ) -> None:
        dev_a = _make_mock_device("alpha")
        dev_b = _make_mock_device("beta")
        dev_c = _make_mock_device("gamma")
        mock_registry_fn.return_value = {
            "alpha": (dev_a, "/dev/switchtec0"),
            "beta": (dev_b, "/dev/switchtec1"),
            "gamma": (dev_c, "/dev/switchtec2"),
        }

        assert get_device("alpha") is dev_a
        assert get_device("beta") is dev_b
        assert get_device("gamma") is dev_c

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_returns_device_object_not_path(self, mock_registry_fn) -> None:
        """get_device should return only the device, not the (device, path) tuple."""
        mock_dev = _make_mock_device()
        mock_registry_fn.return_value = {
            "mydev": (mock_dev, "/dev/switchtec0"),
        }

        result = get_device("mydev")

        # Must be the device, not the tuple
        assert not isinstance(result, tuple)
        assert result is mock_dev


# ===========================================================================
# get_device -- not found
# ===========================================================================


class TestGetDeviceNotFound:
    """Test get_device raises HTTPException 404 when device is missing."""

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_raises_404_when_not_found(self, mock_registry_fn) -> None:
        mock_registry_fn.return_value = {}

        with pytest.raises(HTTPException) as exc_info:
            get_device("nonexistent")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Device not found"

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_raises_404_with_populated_registry(
        self, mock_registry_fn
    ) -> None:
        """Even with other devices present, a missing ID should 404."""
        mock_dev = _make_mock_device()
        mock_registry_fn.return_value = {
            "existing_dev": (mock_dev, "/dev/switchtec0"),
        }

        with pytest.raises(HTTPException) as exc_info:
            get_device("wrong_id")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Device not found"

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_detail_message_does_not_leak_device_id(
        self, mock_registry_fn
    ) -> None:
        """The error detail should not contain the device ID."""
        mock_registry_fn.return_value = {}

        with pytest.raises(HTTPException) as exc_info:
            get_device("my-special-device")

        assert "my-special-device" not in exc_info.value.detail
        assert exc_info.value.detail == "Device not found"

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_empty_string_device_id(self, mock_registry_fn) -> None:
        mock_registry_fn.return_value = {}

        with pytest.raises(HTTPException) as exc_info:
            get_device("")

        assert exc_info.value.status_code == 404


# ===========================================================================
# Edge cases
# ===========================================================================


class TestGetDeviceEdgeCases:
    """Edge case and boundary tests for get_device."""

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_device_id_with_special_characters(
        self, mock_registry_fn
    ) -> None:
        """Device IDs may contain hyphens and underscores per the API pattern."""
        mock_dev = _make_mock_device()
        mock_registry_fn.return_value = {
            "dev-with_chars-01": (mock_dev, "/dev/switchtec0"),
        }

        result = get_device("dev-with_chars-01")
        assert result is mock_dev

    @patch("serialcables_switchtec.api.dependencies.get_device_registry")
    def test_case_sensitive_lookup(self, mock_registry_fn) -> None:
        """Device IDs should be case-sensitive."""
        mock_dev = _make_mock_device()
        mock_registry_fn.return_value = {
            "DevA": (mock_dev, "/dev/switchtec0"),
        }

        # Exact match works
        assert get_device("DevA") is mock_dev

        # Wrong case fails
        with pytest.raises(HTTPException) as exc_info:
            get_device("deva")

        assert exc_info.value.status_code == 404
