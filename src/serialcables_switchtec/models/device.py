"""Pydantic models for device and port data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DeviceInfo(BaseModel):
    """Information about a discovered Switchtec device."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    pci_dev: str
    product_id: str
    product_rev: str
    fw_version: str
    path: str


class PortId(BaseModel):
    """Port identification within a Switchtec switch."""

    model_config = ConfigDict(frozen=True)

    partition: int
    stack: int
    upstream: bool
    stk_id: int
    phys_id: int
    log_id: int


class PortStatus(BaseModel):
    """Status of a single port."""

    model_config = ConfigDict(frozen=True)

    port: PortId
    cfg_lnk_width: int
    neg_lnk_width: int
    link_up: bool
    link_rate: int
    ltssm: int
    ltssm_str: str
    lane_reversal: int
    lane_reversal_str: str
    first_act_lane: int
    pci_bdf: str | None = None
    pci_dev: str | None = None
    vendor_id: int | None = None
    device_id: int | None = None


class DeviceSummary(BaseModel):
    """Summary of a Switchtec device's current state."""

    model_config = ConfigDict(frozen=True)

    name: str
    device_id: int
    generation: str
    variant: str
    boot_phase: str
    partition: int
    fw_version: str
    die_temperature: float
    port_count: int
