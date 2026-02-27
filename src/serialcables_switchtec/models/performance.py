"""Pydantic models for performance monitoring data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BwCounterDirection(BaseModel):
    """Bandwidth counter for one direction."""

    model_config = ConfigDict(frozen=True)

    posted: int
    comp: int
    nonposted: int

    @property
    def total(self) -> int:
        return self.posted + self.comp + self.nonposted


class BwCounterResult(BaseModel):
    """Bandwidth counter result for a port."""

    model_config = ConfigDict(frozen=True)

    time_us: int
    egress: BwCounterDirection
    ingress: BwCounterDirection


class LatencyResult(BaseModel):
    """Latency measurement result."""

    model_config = ConfigDict(frozen=True)

    egress_port_id: int
    current_ns: int
    max_ns: int
