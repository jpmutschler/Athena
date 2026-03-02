"""Gen6 FLIT mode inference and labeling.

PCIe Gen6 replaces traditional TLP framing with FLIT (Flow-control unIT)
encoding.  68-byte FLITs are mandatory for all Gen6 links; 256-byte FLITs
are an optional high-throughput mode negotiated during link training.

Since the C library does not yet expose a direct FLIT mode register read,
this module infers the FLIT mode from the device generation and negotiated
link rate.
"""

from __future__ import annotations

from serialcables_switchtec.bindings.constants import (
    FlitMode,
    SwitchtecGen,
)

_FLIT_MODE_LABELS: dict[FlitMode, str] = {
    FlitMode.OFF: "OFF",
    FlitMode.FLIT_68B: "68B",
    FlitMode.FLIT_256B: "256B",
}

# Gen6 link rate value (from DiagPatternLinkRate / LinkRate enums)
_GEN6_LINK_RATE = 6


def infer_flit_mode(generation: SwitchtecGen, link_rate: int) -> FlitMode:
    """Infer the FLIT encoding mode from device generation and link rate.

    Args:
        generation: The device's PCIe generation.
        link_rate: Negotiated link rate value (1=Gen1 ... 6=Gen6).

    Returns:
        ``FlitMode.FLIT_68B`` for Gen6 devices operating at Gen6 speed,
        ``FlitMode.OFF`` otherwise.
    """
    if generation == SwitchtecGen.GEN6 and link_rate >= _GEN6_LINK_RATE:
        return FlitMode.FLIT_68B
    # TODO: Detect FLIT_256B when C library exposes negotiated FLIT size register
    return FlitMode.OFF


def flit_mode_label(mode: FlitMode) -> str:
    """Return a human-readable label for a FLIT mode value.

    Returns:
        ``"OFF"``, ``"68B"``, or ``"256B"``.
    """
    return _FLIT_MODE_LABELS.get(mode, "OFF")
