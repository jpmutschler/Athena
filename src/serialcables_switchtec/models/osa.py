"""OSA (Ordered Set Analyzer) capture result models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class OsaCaptureStatus(IntEnum):
    """Status codes returned by the OSA capture_data C API."""

    SUCCESS = 0
    TIMEOUT = 1
    BUSY = 2
    ERROR = 3
    NOT_SUPPORTED = 4


_STATUS_MESSAGES: dict[OsaCaptureStatus, str] = {
    OsaCaptureStatus.SUCCESS: "Capture completed successfully",
    OsaCaptureStatus.TIMEOUT: "Capture timed out before completion",
    OsaCaptureStatus.BUSY: "OSA hardware is busy with another operation",
    OsaCaptureStatus.ERROR: "Capture encountered a hardware error",
    OsaCaptureStatus.NOT_SUPPORTED: "OSA capture not supported on this device",
}


@dataclass(frozen=True)
class OsaCaptureResult:
    """Structured interpretation of an OSA capture result code.

    The C API `switchtec_diag_rcvr_osa_capture_data()` returns only an
    integer result code. No pixel or waveform data is exposed in the
    current libswitchtec API.
    """

    status: OsaCaptureStatus
    status_name: str
    success: bool
    message: str


def interpret_osa_result(result_code: int) -> OsaCaptureResult:
    """Interpret a raw OSA capture result code.

    Args:
        result_code: Integer result code from the C API.

    Returns:
        Structured OsaCaptureResult.
    """
    try:
        status = OsaCaptureStatus(result_code)
    except ValueError:
        return OsaCaptureResult(
            status=OsaCaptureStatus.ERROR,
            status_name=f"UNKNOWN({result_code})",
            success=False,
            message=f"Unknown OSA capture status code: {result_code}",
        )

    return OsaCaptureResult(
        status=status,
        status_name=status.name,
        success=status == OsaCaptureStatus.SUCCESS,
        message=_STATUS_MESSAGES.get(status, f"Unknown status: {status}"),
    )
