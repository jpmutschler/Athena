"""Event counter preset configurations for Switchtec BER and error monitoring.

Each preset configures a bitmask of event types to monitor, mapped to the
hardware EvCntrTypeMask flags.  Presets provide curated selections for
common lab workflows (data integrity, link-layer health, thermal events, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

from serialcables_switchtec.bindings.constants import EvCntrTypeMask


@dataclass(frozen=True)
class EventCounterPreset:
    """A named event counter configuration preset.

    Attributes:
        name: Machine-readable identifier (used as dict key).
        display_name: Human-friendly label for UI display.
        description: Explanation of what this preset monitors.
        type_mask: Bitmask of EvCntrTypeMask values to count.
        threshold: Alert threshold; 0 means no threshold alert.
    """

    name: str
    display_name: str
    description: str
    type_mask: int
    threshold: int


# ---- Preset definitions ------------------------------------------------

_DATA_INTEGRITY_MASK = int(
    EvCntrTypeMask.ECRC_ERR
    | EvCntrTypeMask.MALFORM_TLP_ERR
    | EvCntrTypeMask.POISONED_TLP_ERR
    | EvCntrTypeMask.BAD_TLP
)

_LINK_ERRORS_MASK = int(
    EvCntrTypeMask.DATA_LINK_PROTO_ERR
    | EvCntrTypeMask.REPLAY_TMR_TIMEOUT
    | EvCntrTypeMask.REPLAY_NUM_ROLLOVER
    | EvCntrTypeMask.BAD_DLLP
    | EvCntrTypeMask.NAK_RCVD
)

_BER_RELEVANT_MASK = int(
    EvCntrTypeMask.BAD_TLP
    | EvCntrTypeMask.BAD_DLLP
    | EvCntrTypeMask.RCVR_ERR
    | EvCntrTypeMask.REPLAY_TMR_TIMEOUT
    | EvCntrTypeMask.REPLAY_NUM_ROLLOVER
    | EvCntrTypeMask.NAK_RCVD
)

_THERMAL_MASK = int(
    EvCntrTypeMask.RCV_FATAL_MSG
    | EvCntrTypeMask.RCV_NON_FATAL_MSG
    | EvCntrTypeMask.RCV_CORR_MSG
)

_POWER_MASK = int(
    EvCntrTypeMask.SURPRISE_DOWN_ERR
    | EvCntrTypeMask.RCV_FATAL_MSG
    | EvCntrTypeMask.RCV_NON_FATAL_MSG
)

_COMPLETION_MASK = int(
    EvCntrTypeMask.UNSUP_REQ_ERR
    | EvCntrTypeMask.CMPLTR_ABORT_ERR
    | EvCntrTypeMask.COMP_TLP
)

_ACS_VIOLATION_MASK = int(
    EvCntrTypeMask.UNSUP_REQ_ERR
    | EvCntrTypeMask.CMPLTR_ABORT_ERR
    | EvCntrTypeMask.MALFORM_TLP_ERR
    | EvCntrTypeMask.RCVR_OFLOW_ERR
)

_FLOW_CONTROL_MASK = int(
    EvCntrTypeMask.RCVR_OFLOW_ERR
    | EvCntrTypeMask.HDR_LOG_OFLOW_ERR
    | EvCntrTypeMask.NAK_RCVD
    | EvCntrTypeMask.REPLAY_TMR_TIMEOUT
)

_SURPRISE_EVENTS_MASK = int(
    EvCntrTypeMask.SURPRISE_DOWN_ERR
    | EvCntrTypeMask.UNCOR_INT_ERR
    | EvCntrTypeMask.RCV_FATAL_MSG
)


PRESETS: dict[str, EventCounterPreset] = {
    "data_integrity": EventCounterPreset(
        name="data_integrity",
        display_name="Data Integrity",
        description=(
            "Monitor TLP data-path errors: ECRC, malformed TLP, "
            "poisoned TLP, and bad TLP"
        ),
        type_mask=_DATA_INTEGRITY_MASK,
        threshold=1,
    ),
    "link_errors": EventCounterPreset(
        name="link_errors",
        display_name="Link Errors",
        description=(
            "Monitor data-link layer errors: DLLP protocol, replay "
            "timer/rollover, bad DLLP, and NAK received"
        ),
        type_mask=_LINK_ERRORS_MASK,
        threshold=10,
    ),
    "ber_relevant": EventCounterPreset(
        name="ber_relevant",
        display_name="BER-Relevant",
        description=(
            "Monitor errors relevant to bit-error-rate calculation: "
            "bad TLP/DLLP, receiver errors, replay, and NAK"
        ),
        type_mask=_BER_RELEVANT_MASK,
        threshold=0,
    ),
    "thermal": EventCounterPreset(
        name="thermal",
        display_name="Thermal",
        description=(
            "Monitor AER message events that may indicate thermal or "
            "environmental issues: fatal, non-fatal, and correctable messages"
        ),
        type_mask=_THERMAL_MASK,
        threshold=5,
    ),
    "power": EventCounterPreset(
        name="power",
        display_name="Power",
        description=(
            "Monitor surprise-down and fatal/non-fatal messages that may "
            "indicate power delivery or hot-remove events"
        ),
        type_mask=_POWER_MASK,
        threshold=1,
    ),
    "completion": EventCounterPreset(
        name="completion",
        display_name="Completion",
        description=(
            "Monitor completion-related errors: unsupported request, "
            "completer abort, and completion TLP counters"
        ),
        type_mask=_COMPLETION_MASK,
        threshold=0,
    ),
    "acs_violation": EventCounterPreset(
        name="acs_violation",
        display_name="ACS Violation",
        description=(
            "Monitor errors related to access-control violations: "
            "unsupported request, completer abort, malformed TLP, "
            "and receiver overflow"
        ),
        type_mask=_ACS_VIOLATION_MASK,
        threshold=1,
    ),
    "flow_control": EventCounterPreset(
        name="flow_control",
        display_name="Flow Control",
        description=(
            "Monitor flow-control pressure: receiver overflow, header "
            "log overflow, NAK received, and replay timer timeout"
        ),
        type_mask=_FLOW_CONTROL_MASK,
        threshold=10,
    ),
    "surprise_events": EventCounterPreset(
        name="surprise_events",
        display_name="Surprise Events",
        description=(
            "Monitor unexpected link events: surprise down, uncorrectable "
            "internal errors, and fatal messages"
        ),
        type_mask=_SURPRISE_EVENTS_MASK,
        threshold=1,
    ),
    "all_errors": EventCounterPreset(
        name="all_errors",
        display_name="All Errors",
        description="Monitor all error types (bits 0-18)",
        type_mask=int(EvCntrTypeMask.ALL_ERRORS),
        threshold=0,
    ),
}


def get_preset(name: str) -> EventCounterPreset:
    """Look up a preset by name.

    Args:
        name: Preset identifier (e.g. ``"ber_relevant"``).

    Returns:
        The matching ``EventCounterPreset``.

    Raises:
        KeyError: If no preset with *name* exists.
    """
    try:
        return PRESETS[name]
    except KeyError:
        available = ", ".join(sorted(PRESETS))
        raise KeyError(
            f"Unknown preset {name!r}. Available: {available}"
        ) from None


def list_presets() -> list[EventCounterPreset]:
    """Return all presets sorted by name.

    Returns:
        Sorted list of every registered ``EventCounterPreset``.
    """
    return sorted(PRESETS.values(), key=lambda p: p.name)
