"""Generation-aware equalization validation.

Provides per-generation TX equalization cursor ranges, FOM thresholds,
and validation functions for EQ coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass

from serialcables_switchtec.bindings.constants import SwitchtecGen


@dataclass(frozen=True)
class EqRange:
    """Valid range for an equalization cursor value."""

    min_val: int
    max_val: int
    name: str


@dataclass(frozen=True)
class EqValidationResult:
    """Result of validating a single EQ cursor."""

    lane: int
    cursor_name: str
    value: int
    valid: bool
    expected_range: EqRange
    message: str


@dataclass(frozen=True)
class FomValidationResult:
    """Result of validating a Figure of Merit value."""

    lane: int
    fom: int
    threshold: int
    valid: bool
    message: str


# Generation-specific EQ cursor ranges.
# Gen3-Gen5 use standard pre/post ranges.
# Gen6 PAM4 uses wider bipolar ranges for c(-1) and c(+1).
GEN_EQ_RANGES: dict[SwitchtecGen, dict[str, EqRange]] = {
    SwitchtecGen.GEN3: {
        "pre": EqRange(-3, 0, "Pre-cursor"),
        "post": EqRange(-4, 0, "Post-cursor"),
    },
    SwitchtecGen.GEN4: {
        "pre": EqRange(-6, 0, "Pre-cursor"),
        "post": EqRange(-9, 0, "Post-cursor"),
    },
    SwitchtecGen.GEN5: {
        "pre": EqRange(-6, 0, "Pre-cursor"),
        "post": EqRange(-9, 0, "Post-cursor"),
    },
    SwitchtecGen.GEN6: {
        "pre": EqRange(-10, 10, "c(-1)"),
        "post": EqRange(-10, 10, "c(+1)"),
    },
}

# Minimum acceptable FOM per generation.
GEN_FOM_THRESHOLDS: dict[SwitchtecGen, int] = {
    SwitchtecGen.GEN3: 0,
    SwitchtecGen.GEN4: 0,
    SwitchtecGen.GEN5: 8,
    SwitchtecGen.GEN6: 12,
}


def validate_eq_cursor(
    lane: int,
    cursor_name: str,
    value: int,
    gen: SwitchtecGen,
) -> EqValidationResult:
    """Validate a single EQ cursor value against generation-specific ranges.

    Args:
        lane: Lane number.
        cursor_name: Cursor identifier ("pre" or "post").
        value: Cursor value to validate.
        gen: PCIe generation.

    Returns:
        EqValidationResult.
    """
    ranges = GEN_EQ_RANGES.get(gen)
    if ranges is None:
        return EqValidationResult(
            lane=lane,
            cursor_name=cursor_name,
            value=value,
            valid=True,
            expected_range=EqRange(0, 0, "unknown"),
            message=f"No EQ ranges defined for {gen.name}",
        )

    eq_range = ranges.get(cursor_name)
    if eq_range is None:
        return EqValidationResult(
            lane=lane,
            cursor_name=cursor_name,
            value=value,
            valid=True,
            expected_range=EqRange(0, 0, "unknown"),
            message=f"No range defined for cursor '{cursor_name}'",
        )

    valid = eq_range.min_val <= value <= eq_range.max_val
    if valid:
        message = (
            f"Lane {lane} {eq_range.name}={value} within "
            f"[{eq_range.min_val}, {eq_range.max_val}]"
        )
    else:
        message = (
            f"Lane {lane} {eq_range.name}={value} outside "
            f"[{eq_range.min_val}, {eq_range.max_val}]"
        )

    return EqValidationResult(
        lane=lane,
        cursor_name=cursor_name,
        value=value,
        valid=valid,
        expected_range=eq_range,
        message=message,
    )


def validate_fom(
    lane: int,
    fom: int,
    gen: SwitchtecGen,
) -> FomValidationResult:
    """Validate a Figure of Merit value against generation-specific thresholds.

    Args:
        lane: Lane number.
        fom: FOM value.
        gen: PCIe generation.

    Returns:
        FomValidationResult.
    """
    threshold = GEN_FOM_THRESHOLDS.get(gen, 0)
    valid = fom >= threshold

    if valid:
        message = f"Lane {lane} FOM={fom} >= threshold {threshold}"
    else:
        message = f"Lane {lane} FOM={fom} < threshold {threshold}"

    return FomValidationResult(
        lane=lane,
        fom=fom,
        threshold=threshold,
        valid=valid,
        message=message,
    )


def validate_eq_table(
    cursors: list[tuple[int, int]],
    gen: SwitchtecGen,
) -> list[EqValidationResult]:
    """Validate a list of (pre, post) cursor pairs.

    Args:
        cursors: List of (pre_value, post_value) tuples, one per lane.
        gen: PCIe generation.

    Returns:
        List of EqValidationResult, two per lane (pre + post).
    """
    results: list[EqValidationResult] = []
    for lane, (pre, post) in enumerate(cursors):
        results.append(validate_eq_cursor(lane, "pre", pre, gen))
        results.append(validate_eq_cursor(lane, "post", post, gen))
    return results
