"""Raw MRPC command API route for firmware debugging.

MRPC (Management RPC) is the low-level command interface between the host
driver and the Switchtec firmware.  This endpoint exposes the raw command
interface for firmware debugging, undocumented command testing, and
development workflows where typed endpoints do not yet exist.

Payloads are hex-encoded strings (e.g. ``"deadbeef"`` for 4 bytes).  The
maximum payload size is 1024 bytes (2048 hex characters).  The maximum
response length is also 1024 bytes.

Rate limit: 10 calls per device per 60 seconds.

Most users should prefer the typed endpoints (firmware, fabric, events, etc.)
which provide validation, structured responses, and meaningful error messages.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field, field_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.rate_limit import mrpc_limiter

router = APIRouter()

_HEX_PATTERN = re.compile(r"^([0-9a-fA-F]{2})*$")


class MrpcRequest(BaseModel):
    """Request body for a raw MRPC command."""

    command: int = Field(
        ge=0, le=0xFFFFFFFF, description="MRPC command ID"
    )
    payload: str = Field(
        default="", description="Hex-encoded payload bytes"
    )
    resp_len: int = Field(
        default=0,
        ge=0,
        le=1024,
        description="Expected response length in bytes (max 1024)",
    )

    @field_validator("payload")
    @classmethod
    def validate_hex_payload(cls, v: str) -> str:
        if v and not _HEX_PATTERN.match(v):
            raise ValueError(
                "payload must be a hex-encoded string with an even"
                " number of characters (e.g. 'deadbeef')"
            )
        if len(v) > 2048:  # 1024 bytes = 2048 hex chars
            raise ValueError(
                f"payload exceeds 1024-byte MRPC maximum"
                f" ({len(v) // 2} bytes)"
            )
        return v


class MrpcResponse(BaseModel):
    """Response body for a raw MRPC command."""

    command: str = Field(description="MRPC command ID as hex string")
    response: str = Field(description="Hex-encoded response bytes")
    response_len: int = Field(description="Response length in bytes")


@router.post(
    "/{device_id}/mrpc",
    response_model=MrpcResponse,
)
def mrpc_command(
    request: MrpcRequest,
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> MrpcResponse:
    """Send a raw MRPC command to the Switchtec firmware and return the response.

    This is a low-level interface intended for firmware debugging, testing
    undocumented commands, and development of new features before typed
    endpoints are available.  Most users should prefer the typed endpoints
    (firmware, fabric, events, etc.) which provide input validation and
    structured responses.

    Rate limit: 10 calls per device per 60 seconds.

    Request body fields:

    - ``command`` -- the 32-bit MRPC command ID (0 to 0xFFFFFFFF).
    - ``payload`` -- hex-encoded byte string to send as the command payload.
      Must have an even number of hex characters.  Empty string for commands
      with no payload.  Maximum 1024 bytes (2048 hex characters).
    - ``resp_len`` -- expected response length in bytes (0-1024).  The
      firmware will return at most this many bytes.  Set to 0 for commands
      with no response data.

    Response format (``MrpcResponse``):

    - ``command`` -- the command ID echoed back as a hex string
      (e.g. ``"0x1"``).
    - ``response`` -- hex-encoded response bytes from the firmware.
    - ``response_len`` -- actual number of response bytes returned.

    Example response::

        {"command": "0x1", "response": "0100000048656c6c6f", "response_len": 9}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- invalid hex encoding, odd-length
      payload, or payload exceeds 1024-byte limit.
    - **429 Too Many Requests** -- rate limit exceeded.
    - **500 Internal Server Error** -- the MRPC command failed at the
      firmware level.
    """
    mrpc_limiter.check(device_id)
    dev = get_device(device_id)
    payload_bytes = bytes.fromhex(request.payload) if request.payload else b""

    try:
        result = dev.mrpc_cmd(
            request.command,
            payload=payload_bytes,
            resp_len=request.resp_len,
        )
        return MrpcResponse(
            command=f"0x{request.command:x}",
            response=result.hex() if result else "",
            response_len=len(result),
        )
    except Exception as e:
        raise_on_error(e, "mrpc_command")
