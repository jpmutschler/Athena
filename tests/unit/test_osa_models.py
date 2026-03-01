"""Tests for OSA capture result models."""

from __future__ import annotations

import dataclasses

import pytest

from serialcables_switchtec.models.osa import (
    OsaCaptureStatus,
    interpret_osa_result,
)


class TestOsaCaptureStatusEnum:
    def test_status_enum_values(self):
        assert OsaCaptureStatus.SUCCESS == 0
        assert OsaCaptureStatus.TIMEOUT == 1
        assert OsaCaptureStatus.BUSY == 2
        assert OsaCaptureStatus.ERROR == 3
        assert OsaCaptureStatus.NOT_SUPPORTED == 4


class TestInterpretOsaResult:
    def test_success_result(self):
        result = interpret_osa_result(0)
        assert result.success is True
        assert result.status == OsaCaptureStatus.SUCCESS
        assert result.status_name == "SUCCESS"

    def test_timeout_result(self):
        result = interpret_osa_result(1)
        assert result.success is False
        assert result.status == OsaCaptureStatus.TIMEOUT

    def test_busy_result(self):
        result = interpret_osa_result(2)
        assert result.success is False
        assert result.status == OsaCaptureStatus.BUSY

    def test_error_result(self):
        result = interpret_osa_result(3)
        assert result.success is False
        assert result.status == OsaCaptureStatus.ERROR

    def test_not_supported_result(self):
        result = interpret_osa_result(4)
        assert result.success is False
        assert result.status == OsaCaptureStatus.NOT_SUPPORTED

    def test_unknown_code(self):
        result = interpret_osa_result(99)
        assert result.success is False
        assert "UNKNOWN" in result.status_name


class TestOsaCaptureResultFrozen:
    def test_result_is_frozen(self):
        result = interpret_osa_result(0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.success = False  # type: ignore[misc]
