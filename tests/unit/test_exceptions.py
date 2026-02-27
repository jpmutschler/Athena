"""Tests for exception hierarchy and error checking."""

from __future__ import annotations

import ctypes
import errno

import pytest

from serialcables_switchtec.exceptions import (
    DeviceNotFoundError,
    DeviceOpenError,
    InvalidLaneError,
    InvalidParameterError,
    InvalidPortError,
    MrpcError,
    SwitchtecError,
    SwitchtecPermissionError,
    SwitchtecTimeoutError,
    UnsupportedError,
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT,
    SWITCHTEC_ERRNO_MRPC_FLAG_BIT,
    check_error,
    check_null,
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


class TestExceptionSubclasses:
    def test_device_not_found_is_switchtec_error(self):
        err = DeviceNotFoundError("no device")
        assert isinstance(err, SwitchtecError)

    def test_device_open_error_is_switchtec_error(self):
        err = DeviceOpenError("cannot open")
        assert isinstance(err, SwitchtecError)

    def test_invalid_port_error_is_switchtec_error(self):
        err = InvalidPortError("bad port")
        assert isinstance(err, SwitchtecError)

    def test_invalid_lane_error_is_switchtec_error(self):
        err = InvalidLaneError("bad lane")
        assert isinstance(err, SwitchtecError)

    def test_mrpc_error_is_switchtec_error(self):
        err = MrpcError("mrpc failed")
        assert isinstance(err, SwitchtecError)

    def test_unsupported_error_is_switchtec_error(self):
        err = UnsupportedError("not supported")
        assert isinstance(err, SwitchtecError)

    def test_invalid_parameter_error_is_switchtec_error(self):
        err = InvalidParameterError("bad param")
        assert isinstance(err, SwitchtecError)


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
        with pytest.raises(
            SwitchtecError, match="Operation failed with unknown error"
        ):
            check_error(-1)

    def test_errno_zero_with_operation_name(self):
        """When errno==0 and operation is given, message includes both."""
        with pytest.raises(SwitchtecError, match="my_op: operation failed"):
            check_error(-1, "my_op")


class TestCheckErrorMrpcPath:
    """Tests for the MRPC error code path in check_error."""

    def test_mrpc_known_error(self, monkeypatch):
        """Known MRPC code raises the mapped exception."""
        mrpc_code = 0x00000001  # Physical port already bound
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError, match="Physical port already bound"):
            check_error(-1, "test_op")

    def test_mrpc_known_error_has_error_code(self, monkeypatch):
        mrpc_code = 0x00000001
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError) as exc_info:
            check_error(-1)
        assert exc_info.value.error_code == err_value

    def test_mrpc_unsupported_error(self, monkeypatch):
        mrpc_code = 0x0000004a  # MRPC unsupported
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(UnsupportedError, match="MRPC unsupported"):
            check_error(-1)

    def test_mrpc_permission_denied(self, monkeypatch):
        mrpc_code = 0x64010  # MRPC denied
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecPermissionError, match="MRPC denied"):
            check_error(-1)

    def test_mrpc_invalid_parameter(self, monkeypatch):
        mrpc_code = 0x64006  # Parameter invalid
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(InvalidParameterError, match="Parameter invalid"):
            check_error(-1)

    def test_mrpc_unknown_code_raises_mrpc_error(self, monkeypatch):
        mrpc_code = 0xDEAD  # Not in the map
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError, match="MRPC error 0xdead"):
            check_error(-1)

    def test_mrpc_error_includes_operation(self, monkeypatch):
        mrpc_code = 0x00000001
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError, match="my_operation"):
            check_error(-1, "my_operation")

    def test_mrpc_pattern_monitor_disabled(self, monkeypatch):
        mrpc_code = 0x70b02  # Pattern monitor is disabled
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError, match="Pattern monitor is disabled"):
            check_error(-1)

    def test_mrpc_invalid_port(self, monkeypatch):
        mrpc_code = 0x00000004  # Physical port does not exist
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(InvalidPortError):
            check_error(-1)


class TestCheckErrorGeneralPath:
    """Tests for the general error code path in check_error."""

    def test_general_log_def_read_error(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError, match="Log definition read error"):
            check_error(-1)

    def test_general_log_def_read_error_has_error_code(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError) as exc_info:
            check_error(-1)
        assert exc_info.value.error_code == err_value

    def test_general_binary_log_read_error(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 1
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError, match="Binary log read error"):
            check_error(-1)

    def test_general_parsed_log_write_error(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 2
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError, match="Parsed log write error"):
            check_error(-1)

    def test_general_log_def_data_invalid(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 3
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(
            SwitchtecError, match="Log definition data invalid"
        ):
            check_error(-1)

    def test_general_invalid_port(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 4
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(InvalidPortError, match="Invalid port"):
            check_error(-1)

    def test_general_invalid_lane(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 5
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(InvalidLaneError, match="Invalid lane"):
            check_error(-1)

    def test_general_unknown_code_raises_generic(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 999
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError, match="General error"):
            check_error(-1)

    def test_general_error_includes_operation(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(SwitchtecError, match="my_op"):
            check_error(-1, "my_op")


class TestCheckErrorStandardErrno:
    """Tests for the standard errno path in check_error."""

    def test_enodev_raises_device_not_found(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENODEV)
        with pytest.raises(DeviceNotFoundError, match="Device not found"):
            check_error(-1)

    def test_eacces_raises_permission_error(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EACCES)
        with pytest.raises(SwitchtecPermissionError, match="Permission denied"):
            check_error(-1)

    def test_etimedout_raises_timeout_error(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ETIMEDOUT)
        with pytest.raises(SwitchtecTimeoutError, match="Operation timed out"):
            check_error(-1)

    def test_einval_raises_invalid_parameter(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EINVAL)
        with pytest.raises(InvalidParameterError, match="Invalid argument"):
            check_error(-1)

    def test_enoent_raises_device_not_found(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENOENT)
        with pytest.raises(DeviceNotFoundError, match="No such device"):
            check_error(-1)

    def test_unknown_errno_raises_generic_error(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: 9999)
        with pytest.raises(SwitchtecError, match="errno 9999"):
            check_error(-1)

    def test_errno_error_has_error_code(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENODEV)
        with pytest.raises(DeviceNotFoundError) as exc_info:
            check_error(-1)
        assert exc_info.value.error_code == errno.ENODEV

    def test_errno_error_includes_operation(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENODEV)
        with pytest.raises(
            DeviceNotFoundError, match="open_dev: Device not found"
        ):
            check_error(-1, "open_dev")


class TestCheckNull:
    def test_non_null_returns_none(self):
        assert check_null(0xDEADBEEF) is None

    def test_non_null_int_returns_none(self):
        assert check_null(1) is None

    def test_null_pointer_raises(self):
        with pytest.raises(SwitchtecError):
            check_null(None)

    def test_zero_pointer_raises(self):
        with pytest.raises(SwitchtecError):
            check_null(0)

    def test_null_with_errno_zero_raises_generic(self):
        with pytest.raises(SwitchtecError, match="returned NULL"):
            check_null(None, "test_op")

    def test_null_with_errno_set_raises_mapped_error(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENODEV)
        with pytest.raises(DeviceNotFoundError, match="Device not found"):
            check_null(None, "open_device")

    def test_null_with_eacces_raises_permission(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EACCES)
        with pytest.raises(SwitchtecPermissionError):
            check_null(None, "open_device")

    def test_null_with_etimedout_raises_timeout(self, monkeypatch):
        monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ETIMEDOUT)
        with pytest.raises(SwitchtecTimeoutError):
            check_null(None)

    def test_null_with_mrpc_errno_raises_mrpc(self, monkeypatch):
        mrpc_code = 0x00000001
        err_value = SWITCHTEC_ERRNO_MRPC_FLAG_BIT | mrpc_code
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(MrpcError):
            check_null(None)

    def test_null_with_general_errno_raises_general(self, monkeypatch):
        err_value = SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 4
        monkeypatch.setattr(ctypes, "get_errno", lambda: err_value)
        with pytest.raises(InvalidPortError):
            check_null(None)

    def test_null_operation_included_in_message(self):
        with pytest.raises(SwitchtecError, match="my_operation"):
            check_null(None, "my_operation")
