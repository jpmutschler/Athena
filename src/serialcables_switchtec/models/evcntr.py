"""Pydantic models for event counter data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvCntrSetupResult(BaseModel):
    """Event counter setup configuration."""

    model_config = ConfigDict(frozen=True)

    port_mask: int
    type_mask: int
    egress: bool
    threshold: int


class EvCntrValue(BaseModel):
    """A single event counter value with its setup."""

    model_config = ConfigDict(frozen=True)

    counter_id: int
    count: int
    setup: EvCntrSetupResult | None = None


class EvCntrSetupRequest(BaseModel):
    """Request to configure an event counter."""

    port_mask: int = Field(ge=0, le=0xFFFFFFFF)
    type_mask: int = Field(ge=0, le=0x7FFFFF)
    egress: bool = False
    threshold: int = Field(default=0, ge=0, le=0xFFFFFFFF)
