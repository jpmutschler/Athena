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

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [{
                "port": {
                    "partition": 0, "stack": 0, "upstream": True,
                    "stk_id": 0, "phys_id": 0, "log_id": 0,
                },
                "cfg_lnk_width": 16,
                "neg_lnk_width": 16,
                "link_up": True,
                "link_rate": 5,
                "ltssm": 0,
                "ltssm_str": "L0",
                "lane_reversal": 0,
                "lane_reversal_str": "none",
                "first_act_lane": 0,
                "pci_bdf": "03:00.0",
            }],
        },
    )

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
    flit_mode: str | None = None


class DeviceSummary(BaseModel):
    """Summary of a Switchtec device's current state."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [{
                "name": "PSX48XG5",
                "device_id": 23040,
                "generation": "Gen5",
                "variant": "PSX",
                "boot_phase": "BL2",
                "partition": 0,
                "fw_version": "4.70B058",
                "die_temperature": 42.5,
                "port_count": 48,
            }],
        },
    )

    name: str
    device_id: int
    generation: str
    variant: str
    boot_phase: str
    partition: int
    fw_version: str
    die_temperature: float
    port_count: int
    supports_flit: bool = False
