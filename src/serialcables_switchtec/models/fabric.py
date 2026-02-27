"""Pydantic models for Switchtec fabric/topology data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FabPortConfig(BaseModel):
    """Fabric port configuration."""

    model_config = ConfigDict(frozen=True)

    phys_port_id: int = Field(ge=0, le=59)
    port_type: int = Field(default=0, ge=0, le=255)
    clock_source: int = Field(default=0, ge=0, le=255)
    clock_sris: int = Field(default=0, ge=0, le=255)
    hvd_inst: int = Field(default=0, ge=0, le=255)
    link_width: int = Field(default=0, ge=0, le=255)


class FabTopoPort(BaseModel):
    """A port entry in the fabric topology."""

    model_config = ConfigDict(frozen=True)

    phys_port_id: int
    port_type: str = "unknown"
    link_width: int = 0
    link_rate: int = 0
    link_up: bool = False


class FabTopology(BaseModel):
    """Fabric topology summary."""

    model_config = ConfigDict(frozen=True)

    switch_id: int = 0
    num_ports: int = 0
    ports: list[FabTopoPort] = Field(default_factory=list)


class GfmsBindRequest(BaseModel):
    """GFMS bind request parameters."""

    model_config = ConfigDict(frozen=True)

    host_sw_idx: int = Field(ge=0, le=255)
    host_phys_port_id: int = Field(ge=0, le=255)
    host_log_port_id: int = Field(ge=0, le=255)
    ep_sw_idx: int = Field(ge=0, le=255)
    ep_phys_port_id: int = Field(ge=0, le=255)


class GfmsUnbindRequest(BaseModel):
    """GFMS unbind request parameters."""

    model_config = ConfigDict(frozen=True)

    host_sw_idx: int = Field(ge=0, le=255)
    host_phys_port_id: int = Field(ge=0, le=255)
    host_log_port_id: int = Field(ge=0, le=255)
    opt: int = Field(default=0, ge=0, le=255)
