"""Tests for exception hierarchy and error checking."""

from __future__ import annotations

import pytest

from serialcables_switchtec.exceptions import (
    MrpcError,
    SwitchtecError,
    SwitchtecPermissionError,
    SwitchtecTimeoutError,
    check_error,
)


class TestSwitchtecError:
    def test_base_error(self):
        err = SwitchtecError("test error", error_code=42)
        assert str(err) == "test error"
        assert err.error_code == 42

    def test_base_error_no_code(self):
        err = SwitchtecError("simple")
        assert err.error_code is None


class TestRenamedExceptions:
    def test_timeout_error_exists(self):
        err = SwitchtecTimeoutError("timed out")
        assert isinstance(err, SwitchtecError)
        assert str(err) == "timed out"

    def test_permission_error_exists(self):
        err = SwitchtecPermissionError("denied")
        assert isinstance(err, SwitchtecError)
        assert str(err) == "denied"

    def test_timeout_error_subclass(self):
        assert issubclass(SwitchtecTimeoutError, SwitchtecError)

    def test_permission_error_subclass(self):
        assert issubclass(SwitchtecPermissionError, SwitchtecError)


class TestCheckError:
    def test_success_returns_none(self):
        assert check_error(0) is None

    def test_positive_returns_none(self):
        assert check_error(5) is None

    def test_negative_raises(self):
        # With errno=0, we get a generic error
        with pytest.raises(SwitchtecError):
            check_error(-1)

    def test_operation_in_message(self):
        with pytest.raises(SwitchtecError, match="open_device"):
            check_error(-1, "open_device")

    def test_errno_zero_operation_failed_message(self):
        """When errno==0, check_error raises with 'operation failed' message."""
        with pytest.raises(SwitchtecError, match="Operation failed with unknown error"):
            check_error(-1)

    def test_errno_zero_with_operation_name(self):
        """When errno==0 and operation is given, message includes both."""
        with pytest.raises(SwitchtecError, match="my_op: operation failed"):
            check_error(-1, "my_op")
