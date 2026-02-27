"""Pydantic models for Switchtec event data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EventEntry(BaseModel):
    """A single event entry."""

    model_config = ConfigDict(frozen=True)

    event_id: int
    index: int = 0
    count: int = 0
    first_timestamp: int = 0
    last_timestamp: int = 0
    data: list[int] = Field(default_factory=list)


class EventSummaryResult(BaseModel):
    """Summary of all pending events."""

    model_config = ConfigDict(frozen=True)

    global_events: int = 0
    partition_events: int = 0
    pff_events: int = 0
    total_count: int = 0
