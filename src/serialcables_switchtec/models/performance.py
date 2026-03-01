"""Pydantic models for performance monitoring data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field


class BwCounterDirection(BaseModel):
    """Bandwidth counter for one direction."""

    model_config = ConfigDict(frozen=True)

    posted: int
    comp: int
    nonposted: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return self.posted + self.comp + self.nonposted


class BwCounterResult(BaseModel):
    """Bandwidth counter result for a port."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [{
                "time_us": 1000234,
                "egress": {"posted": 1048576, "comp": 524288, "nonposted": 4096, "total": 1576960},
                "ingress": {"posted": 524288, "comp": 262144, "nonposted": 2048, "total": 788480},
            }],
        },
    )

    time_us: int
    egress: BwCounterDirection
    ingress: BwCounterDirection


class LatencyResult(BaseModel):
    """Latency measurement result."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [{
                "egress_port_id": 0,
                "current_ns": 245,
                "max_ns": 1023,
            }],
        },
    )

    egress_port_id: int
    current_ns: int
    max_ns: int
