"""Pydantic models for firmware data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FwImageInfo(BaseModel):
    """Firmware image information."""

    model_config = ConfigDict(frozen=True)

    generation: str
    partition_type: str
    version: str
    partition_addr: int
    partition_len: int
    image_len: int
    valid: bool
    active: bool
    running: bool
    read_only: bool
