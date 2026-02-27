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


class FwPartitionInfo(BaseModel):
    """Firmware partition active/inactive image info."""

    model_config = ConfigDict(frozen=True)

    active: FwImageInfo | None = None
    inactive: FwImageInfo | None = None


class FwPartSummary(BaseModel):
    """Summary of all firmware partition images."""

    model_config = ConfigDict(frozen=True)

    boot: FwPartitionInfo = FwPartitionInfo()
    map: FwPartitionInfo = FwPartitionInfo()
    img: FwPartitionInfo = FwPartitionInfo()
    cfg: FwPartitionInfo = FwPartitionInfo()
    nvlog: FwPartitionInfo = FwPartitionInfo()
    seeprom: FwPartitionInfo = FwPartitionInfo()
    key: FwPartitionInfo = FwPartitionInfo()
    bl2: FwPartitionInfo = FwPartitionInfo()
    riot: FwPartitionInfo = FwPartitionInfo()
    is_boot_ro: bool = False
