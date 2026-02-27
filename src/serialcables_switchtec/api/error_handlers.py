"""Centralized exception-to-HTTP mapping for the API layer."""

from __future__ import annotations

from fastapi import HTTPException

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
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)

# Map exception classes to HTTP status codes
_STATUS_MAP: dict[type[SwitchtecError], int] = {
    DeviceNotFoundError: 404,
    InvalidPortError: 400,
    InvalidLaneError: 400,
    InvalidParameterError: 400,
    SwitchtecPermissionError: 403,
    SwitchtecTimeoutError: 504,
    UnsupportedError: 501,
    DeviceOpenError: 502,
    MrpcError: 502,
}


def raise_on_error(e: Exception, operation: str = "") -> None:
    """Convert a SwitchtecError to an appropriate HTTPException.

    Logs full details server-side, returns sanitized message to client.
    """
    if isinstance(e, SwitchtecError):
        status = _STATUS_MAP.get(type(e), 500)
        logger.error(
            "api_error",
            operation=operation,
            error=str(e),
            error_code=e.error_code,
            status=status,
        )
        raise HTTPException(status_code=status, detail=str(e))

    logger.exception("unexpected_error", operation=operation)
    raise HTTPException(status_code=500, detail="Internal server error")
