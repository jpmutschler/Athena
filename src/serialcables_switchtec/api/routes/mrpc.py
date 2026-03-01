"""Raw MRPC command API route for firmware debugging."""

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
    """Send a raw MRPC command to the device.

    This is a low-level interface for firmware debugging and testing
    undocumented commands. Most users should prefer the typed endpoints.
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
