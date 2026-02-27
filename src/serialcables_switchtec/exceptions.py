"""Exception hierarchy for Switchtec library errors.

Maps errno-based error codes and MRPC return codes to Python exceptions.
"""

from __future__ import annotations

import ctypes
import errno

# MRPC error flag bits from errors.h
SWITCHTEC_ERRNO_GENERAL_FLAG_BIT = 1 << 29
SWITCHTEC_ERRNO_MRPC_FLAG_BIT = 1 << 30


class SwitchtecError(Exception):
    """Base exception for all Switchtec errors."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


class LibraryLoadError(SwitchtecError):
    """Failed to load the Switchtec shared library."""


class DeviceNotFoundError(SwitchtecError):
    """No matching Switchtec device was found."""


class DeviceOpenError(SwitchtecError):
    """Failed to open a Switchtec device."""


class InvalidPortError(SwitchtecError):
    """Invalid port specified."""


class InvalidLaneError(SwitchtecError):
    """Invalid lane specified."""


class MrpcError(SwitchtecError):
    """MRPC command returned an error."""


class SwitchtecTimeoutError(SwitchtecError):
    """Operation timed out."""


class SwitchtecPermissionError(SwitchtecError):
    """Access refused or denied."""


class UnsupportedError(SwitchtecError):
    """Operation not supported on this device or firmware."""


class InvalidParameterError(SwitchtecError):
    """Invalid parameter passed to the library."""


# Map MRPC error codes from errors.h to exception classes
_MRPC_ERROR_MAP: dict[int, tuple[type[SwitchtecError], str]] = {
    0x00000001: (MrpcError, "Physical port already bound"),
    0x00000002: (MrpcError, "Logical port already bound"),
    0x00000003: (MrpcError, "Bind partition does not exist"),
    0x00000004: (InvalidPortError, "Physical port does not exist"),
    0x00000005: (InvalidPortError, "Physical port disabled"),
    0x00000006: (MrpcError, "No logical port available"),
    0x00000007: (MrpcError, "Bind in progress"),
    0x00000009: (InvalidParameterError, "Bind sub-command invalid"),
    0x0000000a: (MrpcError, "Physical port link active"),
    0x0000000b: (MrpcError, "Logical port not bound to physical port"),
    0x0000000c: (InvalidParameterError, "Unbind option invalid"),
    0x0000004a: (UnsupportedError, "MRPC unsupported"),
    0x64001: (MrpcError, "No available MRPC thread"),
    0x64004: (InvalidParameterError, "Sub-command invalid"),
    0x64005: (InvalidParameterError, "Command invalid"),
    0x64006: (InvalidParameterError, "Parameter invalid"),
    0x64007: (MrpcError, "Bad firmware state"),
    0x64010: (SwitchtecPermissionError, "MRPC denied"),
    0x70b02: (MrpcError, "Pattern monitor is disabled"),
    0x100001: (InvalidParameterError, "Stack invalid"),
    0x100002: (InvalidPortError, "Port invalid"),
    0x100003: (InvalidParameterError, "Event invalid"),
    0xFFFF0001: (SwitchtecPermissionError, "Access refused"),
}

# General error codes from errors.h
_GENERAL_ERROR_MAP: dict[int, tuple[type[SwitchtecError], str]] = {
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT: (SwitchtecError, "Log definition read error"),
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 1: (SwitchtecError, "Binary log read error"),
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 2: (SwitchtecError, "Parsed log write error"),
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 3: (SwitchtecError, "Log definition data invalid"),
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 4: (InvalidPortError, "Invalid port"),
    SWITCHTEC_ERRNO_GENERAL_FLAG_BIT + 5: (InvalidLaneError, "Invalid lane"),
}

# Map common errno values to exception classes
_ERRNO_MAP: dict[int, tuple[type[SwitchtecError], str]] = {
    errno.ENODEV: (DeviceNotFoundError, "Device not found"),
    errno.EACCES: (SwitchtecPermissionError, "Permission denied"),
    errno.ETIMEDOUT: (SwitchtecTimeoutError, "Operation timed out"),
    errno.EINVAL: (InvalidParameterError, "Invalid argument"),
    errno.ENOENT: (DeviceNotFoundError, "No such device"),
}


def check_error(ret: int, operation: str = "") -> None:
    """Check a return code from a Switchtec library function.

    Most functions return 0 on success, -1 on error with errno set.

    Args:
        ret: Return code from library function.
        operation: Description of the operation for error messages.

    Raises:
        SwitchtecError: If ret indicates an error.
    """
    if ret >= 0:
        return

    err = ctypes.get_errno()

    if err == 0:
        msg = f"{operation}: operation failed" if operation else "Operation failed with unknown error"
        raise SwitchtecError(msg)

    if err & SWITCHTEC_ERRNO_MRPC_FLAG_BIT:
        mrpc_code = err & ~SWITCHTEC_ERRNO_MRPC_FLAG_BIT
        exc_class, desc = _MRPC_ERROR_MAP.get(
            mrpc_code, (MrpcError, f"MRPC error 0x{mrpc_code:x}")
        )
        msg = f"{operation}: {desc}" if operation else desc
        raise exc_class(msg, error_code=err)

    if err & SWITCHTEC_ERRNO_GENERAL_FLAG_BIT:
        exc_class, desc = _GENERAL_ERROR_MAP.get(
            err, (SwitchtecError, f"General error 0x{err:x}")
        )
        msg = f"{operation}: {desc}" if operation else desc
        raise exc_class(msg, error_code=err)

    exc_class, desc = _ERRNO_MAP.get(err, (SwitchtecError, f"errno {err}"))
    msg = f"{operation}: {desc}" if operation else desc
    raise exc_class(msg, error_code=err)


def check_null(ptr: int | None, operation: str = "") -> None:
    """Check a pointer return from a Switchtec library function.

    Functions returning pointers return NULL on error with errno set.

    Args:
        ptr: Pointer value (c_void_p value).
        operation: Description of the operation for error messages.

    Raises:
        SwitchtecError: If ptr is NULL.
    """
    if ptr is not None and ptr != 0:
        return

    err = ctypes.get_errno()
    if err == 0:
        msg = f"{operation}: returned NULL" if operation else "returned NULL"
        raise SwitchtecError(msg)

    check_error(-1, operation)
