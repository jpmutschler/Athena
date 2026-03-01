"""PAM4/NRZ eye diagram metrics computation.

Provides generation-aware eye analysis that segments the pixel grid
into 3 vertical eyes for Gen6 PAM4 signaling or treats the full grid
as a single eye for NRZ (Gen3–Gen5).
"""

from __future__ import annotations

from dataclasses import dataclass

from serialcables_switchtec.bindings.constants import SwitchtecGen

_NRZ_AREA_WARN = 0.20
_PAM4_AREA_WARN = 0.06
_THRESHOLD_FRACTION = 0.10


@dataclass(frozen=True)
class EyeMetrics:
    """Metrics for a single eye opening."""

    width: int
    height: int
    area_fraction: float
    threshold: float


@dataclass(frozen=True)
class EyeAnalysis:
    """Full eye analysis result, generation-aware."""

    generation: SwitchtecGen
    signaling: str  # "NRZ" or "PAM4"
    eyes: list[EyeMetrics]  # 1 for NRZ, 3 for PAM4
    overall_area: float
    verdict: str  # "PASS", "WARN", "FAIL"


def _compute_single_eye(
    pixels: list[float],
    x_count: int,
    y_count: int,
    threshold: float,
) -> EyeMetrics:
    """Compute width, height, and area for a single eye region.

    The pixel grid is stored row-major: pixels[y * x_count + x].
    """
    if not pixels or x_count == 0 or y_count == 0:
        return EyeMetrics(width=0, height=0, area_fraction=0.0, threshold=threshold)

    # Eye width: longest contiguous open run in center row
    center_y = y_count // 2
    row_start = center_y * x_count
    width = 0
    best_width = 0
    for x in range(x_count):
        if pixels[row_start + x] < threshold:
            width += 1
            best_width = max(best_width, width)
        else:
            width = 0

    # Eye height: longest contiguous open run in center column
    center_x = x_count // 2
    height = 0
    best_height = 0
    for y in range(y_count):
        if pixels[y * x_count + center_x] < threshold:
            height += 1
            best_height = max(best_height, height)
        else:
            height = 0

    # Area: fraction of pixels below threshold
    open_count = sum(1 for p in pixels if p < threshold)
    area = open_count / len(pixels)

    return EyeMetrics(
        width=best_width,
        height=best_height,
        area_fraction=area,
        threshold=threshold,
    )


def _extract_eye_region(
    pixels: list[float],
    x_count: int,
    y_count: int,
    y_start: int,
    y_end: int,
) -> list[float]:
    """Extract a horizontal band of pixels from the full grid."""
    region: list[float] = []
    for y in range(y_start, y_end):
        row_start = y * x_count
        region.extend(pixels[row_start : row_start + x_count])
    return region


def compute_eye_metrics(
    pixels: list[float],
    x_count: int,
    y_count: int,
    threshold_fraction: float = _THRESHOLD_FRACTION,
) -> EyeMetrics:
    """Compute eye metrics for a single (NRZ) eye.

    Args:
        pixels: Flat list of pixel values, row-major.
        x_count: Number of columns (phase steps).
        y_count: Number of rows (voltage steps).
        threshold_fraction: Fraction of max pixel value used as open/closed
            boundary.

    Returns:
        EyeMetrics with width, height, area_fraction, threshold.
    """
    if not pixels:
        return EyeMetrics(width=0, height=0, area_fraction=0.0, threshold=0.0)

    max_val = max(pixels)
    if max_val <= 0:
        return EyeMetrics(width=0, height=0, area_fraction=0.0, threshold=0.0)

    threshold = max_val * threshold_fraction
    return _compute_single_eye(pixels, x_count, y_count, threshold)


def analyze_eye(
    pixels: list[float],
    x_count: int,
    y_count: int,
    generation: SwitchtecGen,
) -> EyeAnalysis:
    """Analyze an eye diagram with generation-aware PAM4/NRZ semantics.

    For Gen6 (PAM4), the pixel grid is segmented into 3 vertical thirds
    representing the top, middle, and bottom eyes. Each eye is analyzed
    independently.

    For Gen3–Gen5 (NRZ), the full grid is treated as a single eye.

    Args:
        pixels: Flat list of pixel values, row-major.
        x_count: Number of columns.
        y_count: Number of rows.
        generation: PCIe generation of the device.

    Returns:
        EyeAnalysis with per-eye metrics and overall verdict.
    """
    is_pam4 = generation >= SwitchtecGen.GEN6
    signaling = "PAM4" if is_pam4 else "NRZ"

    if not pixels or x_count == 0 or y_count == 0:
        return EyeAnalysis(
            generation=generation,
            signaling=signaling,
            eyes=[],
            overall_area=0.0,
            verdict="FAIL",
        )

    max_val = max(pixels)
    if max_val <= 0:
        return EyeAnalysis(
            generation=generation,
            signaling=signaling,
            eyes=[],
            overall_area=0.0,
            verdict="FAIL",
        )

    threshold = max_val * _THRESHOLD_FRACTION

    if is_pam4:
        # Segment into 3 vertical thirds (top, middle, bottom eyes)
        third = y_count // 3
        boundaries = [
            (0, third),
            (third, 2 * third),
            (2 * third, y_count),
        ]
        eyes: list[EyeMetrics] = []
        for y_start, y_end in boundaries:
            region = _extract_eye_region(pixels, x_count, y_count, y_start, y_end)
            region_y_count = y_end - y_start
            eye = _compute_single_eye(region, x_count, region_y_count, threshold)
            eyes.append(eye)

        overall_area = sum(e.area_fraction for e in eyes) / len(eyes)
        warn_threshold = _PAM4_AREA_WARN
    else:
        single_eye = _compute_single_eye(pixels, x_count, y_count, threshold)
        eyes = [single_eye]
        overall_area = single_eye.area_fraction
        warn_threshold = _NRZ_AREA_WARN

    # Verdict
    if overall_area <= 0:
        verdict = "FAIL"
    elif overall_area < warn_threshold:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return EyeAnalysis(
        generation=generation,
        signaling=signaling,
        eyes=eyes,
        overall_area=overall_area,
        verdict=verdict,
    )
