"""Pydantic models for diagnostic data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EyeRange(BaseModel):
    """Range specification for eye diagram capture."""

    model_config = ConfigDict(frozen=True)

    start: int
    end: int
    step: int


class EyeData(BaseModel):
    """Eye diagram capture result."""

    model_config = ConfigDict(frozen=True)

    lane_id: int
    x_range: EyeRange
    y_range: EyeRange
    pixels: list[float]


class LtssmLogEntry(BaseModel):
    """Single LTSSM state log entry."""

    model_config = ConfigDict(frozen=True)

    timestamp: int
    link_rate: float
    link_state: int
    link_state_str: str
    link_width: int
    tx_minor_state: int
    rx_minor_state: int


class LoopbackStatus(BaseModel):
    """Loopback configuration status."""

    model_config = ConfigDict(frozen=True)

    port_id: int
    enabled: int
    ltssm_speed: int


class PatternMonResult(BaseModel):
    """Pattern monitor result."""

    model_config = ConfigDict(frozen=True)

    port_id: int
    lane_id: int
    pattern_type: int
    error_count: int


class ReceiverObject(BaseModel):
    """Receiver calibration object dump."""

    model_config = ConfigDict(frozen=True)

    port_id: int
    lane_id: int
    ctle: int
    target_amplitude: int
    speculative_dfe: int
    dynamic_dfe: list[int]


class ReceiverExt(BaseModel):
    """Extended receiver calibration data."""

    model_config = ConfigDict(frozen=True)

    ctle2_rx_mode: int
    dtclk_5: int
    dtclk_8_6: int
    dtclk_9: int


class CrossHairResult(BaseModel):
    """Cross-hair measurement result."""

    model_config = ConfigDict(frozen=True)

    lane_id: int
    state: int
    state_name: str
    eye_left_lim: int = 0
    eye_right_lim: int = 0
    eye_bot_left_lim: int = 0
    eye_bot_right_lim: int = 0
    eye_top_left_lim: int = 0
    eye_top_right_lim: int = 0


class EqCursor(BaseModel):
    """Equalization cursor pair."""

    model_config = ConfigDict(frozen=True)

    pre: int
    post: int


class PortEqCoeff(BaseModel):
    """Port equalization coefficients."""

    model_config = ConfigDict(frozen=True)

    lane_count: int
    cursors: list[EqCursor]


class EqTableStep(BaseModel):
    """Single step in equalization table."""

    model_config = ConfigDict(frozen=True)

    pre_cursor: int
    post_cursor: int
    fom: int
    pre_cursor_up: int
    post_cursor_up: int
    error_status: int
    active_status: int
    speed: int


class PortEqTable(BaseModel):
    """Port equalization table."""

    model_config = ConfigDict(frozen=True)

    lane_id: int
    step_count: int
    steps: list[EqTableStep]


class PortEqTxFslf(BaseModel):
    """Port equalization TX FS/LF values."""

    model_config = ConfigDict(frozen=True)

    fs: int
    lf: int
