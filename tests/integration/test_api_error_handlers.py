"""Error handler unit tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from serialcables_switchtec.api.error_handlers import _STATUS_MAP, raise_on_error
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
)


class TestErrorHandlers:
    """Tests for the raise_on_error function and _STATUS_MAP."""

    def test_raise_on_error_switchtec_error_base(self):
        """Base SwitchtecError should map to 500 with generic sanitized message."""
        exc = SwitchtecError("generic failure", error_code=99)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "test_op")
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Operation failed"

    def test_raise_on_error_device_not_found(self):
        """DeviceNotFoundError should map to 404 with sanitized message."""
        exc = DeviceNotFoundError("device missing", error_code=1)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "lookup")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Device not found"

    def test_raise_on_error_invalid_port(self):
        """InvalidPortError should map to 400 with sanitized message."""
        exc = InvalidPortError("bad port", error_code=2)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "port_check")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid port specified"

    def test_raise_on_error_invalid_lane(self):
        """InvalidLaneError should map to 400 with sanitized message."""
        exc = InvalidLaneError("bad lane", error_code=3)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "lane_check")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid lane specified"

    def test_raise_on_error_invalid_parameter(self):
        """InvalidParameterError should map to 400 with sanitized message."""
        exc = InvalidParameterError("bad param", error_code=4)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "param_check")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid parameter"

    def test_raise_on_error_permission(self):
        """SwitchtecPermissionError should map to 403 with sanitized message."""
        exc = SwitchtecPermissionError("denied", error_code=5)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "auth_check")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Permission denied"

    def test_raise_on_error_timeout(self):
        """SwitchtecTimeoutError should map to 504 with sanitized message."""
        exc = SwitchtecTimeoutError("timed out", error_code=6)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "timeout_op")
        assert exc_info.value.status_code == 504
        assert exc_info.value.detail == "Operation timed out"

    def test_raise_on_error_unsupported(self):
        """UnsupportedError should map to 501 with sanitized message."""
        exc = UnsupportedError("not supported", error_code=7)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "unsupported_op")
        assert exc_info.value.status_code == 501
        assert exc_info.value.detail == "Operation not supported by this device"

    def test_raise_on_error_device_open(self):
        """DeviceOpenError should map to 502 with sanitized message."""
        exc = DeviceOpenError("open failed", error_code=8)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "open_check")
        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "Failed to open device"

    def test_raise_on_error_mrpc(self):
        """MrpcError should map to 502 with sanitized message."""
        exc = MrpcError("mrpc failed", error_code=9)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "mrpc_op")
        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "Hardware communication error"

    def test_raise_on_error_unexpected_exception(self):
        """Non-SwitchtecError should map to 500 with generic message."""
        exc = RuntimeError("something broke")
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "unexpected_op")
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"

    def test_raise_on_error_no_operation_label(self):
        """raise_on_error works without an operation label."""
        exc = DeviceNotFoundError("missing")
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc)
        assert exc_info.value.status_code == 404

    def test_status_map_completeness(self):
        """All expected exception types should be present in _STATUS_MAP."""
        expected_types = {
            DeviceNotFoundError,
            InvalidPortError,
            InvalidLaneError,
            InvalidParameterError,
            SwitchtecPermissionError,
            SwitchtecTimeoutError,
            UnsupportedError,
            DeviceOpenError,
            MrpcError,
        }
        assert set(_STATUS_MAP.keys()) == expected_types
