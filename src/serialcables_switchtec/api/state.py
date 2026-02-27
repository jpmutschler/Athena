"""Shared API state: device registry and async lock."""

from __future__ import annotations

import asyncio
import hmac
import os
import re

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)

# Global device registry: maps device_id to (SwitchtecDevice, path)
_device_registry: dict[str, tuple[SwitchtecDevice, str]] = {}
_registry_lock = asyncio.Lock()

# Device path validation
DEVICE_PATH_PATTERN = re.compile(
    r"^(/dev/switchtec\d+|\\\\\.\\switchtec\d+|\d+)$"
)

# API key auth (optional, enabled when SWITCHTEC_API_KEY env var is set)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Verify API key. Rejects all requests if SWITCHTEC_API_KEY is not configured."""
    expected = os.environ.get("SWITCHTEC_API_KEY")
    if expected is None:
        raise HTTPException(
            status_code=503,
            detail="API key not configured. Set SWITCHTEC_API_KEY environment variable.",
        )
    if api_key is None or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=403, detail="Invalid or missing API key",
        )


def get_device_registry() -> dict[str, tuple[SwitchtecDevice, str]]:
    """Get the global device registry."""
    return _device_registry


def get_registry_lock() -> asyncio.Lock:
    """Get the registry mutation lock."""
    return _registry_lock
