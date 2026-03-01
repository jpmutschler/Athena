"""Tests for PAM4/NRZ eye diagram metrics computation."""

from __future__ import annotations

from serialcables_switchtec.bindings.constants import SwitchtecGen
from serialcables_switchtec.core.eye_metrics import (
    EyeAnalysis,
    EyeMetrics,
    analyze_eye,
    compute_eye_metrics,
)


class TestComputeEyeMetrics:
    """Tests for the compute_eye_metrics function."""

    def test_empty_pixels_returns_zero(self):
        result = compute_eye_metrics([], 0, 0)
        assert result.width == 0
        assert result.height == 0
        assert result.area_fraction == 0.0

    def test_all_zero_pixels_returns_zero(self):
        pixels = [0.0] * 100
        result = compute_eye_metrics(pixels, 10, 10)
        assert result.width == 0
        assert result.height == 0
        assert result.area_fraction == 0.0

    def test_all_max_pixels_closed_eye(self):
        """All pixels at max → no open area, 0 width/height."""
        pixels = [100.0] * 100
        result = compute_eye_metrics(pixels, 10, 10)
        assert result.width == 0
        assert result.height == 0
        assert result.area_fraction == 0.0

    def test_open_eye_center(self):
        """Eye with open center region has non-zero width/height/area."""
        x_count, y_count = 20, 20
        pixels = [100.0] * (x_count * y_count)

        # Create an open region in the center
        for y in range(6, 14):
            for x in range(6, 14):
                pixels[y * x_count + x] = 1.0

        result = compute_eye_metrics(pixels, x_count, y_count)
        assert result.width > 0
        assert result.height > 0
        assert result.area_fraction > 0.0
        assert result.threshold == 10.0  # 100.0 * 0.10

    def test_threshold_fraction_customizable(self):
        """Custom threshold_fraction changes threshold value."""
        x_count, y_count = 10, 10
        pixels = [50.0] * (x_count * y_count)
        # Set center below default threshold but above custom
        center = (y_count // 2) * x_count + (x_count // 2)
        pixels[center] = 4.0

        result_default = compute_eye_metrics(pixels, x_count, y_count, 0.10)
        result_strict = compute_eye_metrics(pixels, x_count, y_count, 0.05)

        assert result_default.threshold == 5.0
        assert result_strict.threshold == 2.5

    def test_width_measures_center_row(self):
        """Width is computed from the center row."""
        x_count, y_count = 10, 10
        pixels = [100.0] * (x_count * y_count)

        # Open the center row columns 3-7
        center_y = y_count // 2
        for x in range(3, 8):
            pixels[center_y * x_count + x] = 1.0

        result = compute_eye_metrics(pixels, x_count, y_count)
        assert result.width == 5

    def test_height_measures_center_column(self):
        """Height is computed from the center column."""
        x_count, y_count = 10, 10
        pixels = [100.0] * (x_count * y_count)

        # Open the center column rows 2-8
        center_x = x_count // 2
        for y in range(2, 9):
            pixels[y * x_count + center_x] = 1.0

        result = compute_eye_metrics(pixels, x_count, y_count)
        assert result.height == 7


class TestAnalyzeEye:
    """Tests for the analyze_eye function with generation-aware logic."""

    def test_nrz_single_eye(self):
        """NRZ (Gen4) returns 1 eye in the analysis."""
        x_count, y_count = 20, 20
        pixels = [100.0] * (x_count * y_count)
        # Open center
        for y in range(5, 15):
            for x in range(5, 15):
                pixels[y * x_count + x] = 1.0

        result = analyze_eye(pixels, x_count, y_count, SwitchtecGen.GEN4)
        assert result.signaling == "NRZ"
        assert len(result.eyes) == 1
        assert result.eyes[0].width > 0
        assert result.verdict in ("PASS", "WARN", "FAIL")

    def test_pam4_three_eyes(self):
        """PAM4 (Gen6) segments into 3 eyes."""
        x_count, y_count = 30, 30
        pixels = [100.0] * (x_count * y_count)
        # Open center of each third
        third = y_count // 3
        for region_start in [0, third, 2 * third]:
            region_center_y = region_start + third // 2
            for y in range(region_center_y - 2, region_center_y + 3):
                for x in range(10, 20):
                    if 0 <= y < y_count:
                        pixels[y * x_count + x] = 1.0

        result = analyze_eye(pixels, x_count, y_count, SwitchtecGen.GEN6)
        assert result.signaling == "PAM4"
        assert len(result.eyes) == 3
        assert result.generation == SwitchtecGen.GEN6

    def test_gen3_is_nrz(self):
        result = analyze_eye([100.0, 1.0, 100.0, 1.0], 2, 2, SwitchtecGen.GEN3)
        assert result.signaling == "NRZ"
        assert len(result.eyes) == 1

    def test_gen5_is_nrz(self):
        result = analyze_eye([100.0, 1.0, 100.0, 1.0], 2, 2, SwitchtecGen.GEN5)
        assert result.signaling == "NRZ"

    def test_gen6_is_pam4(self):
        pixels = [100.0] * 90  # 10x9 grid
        result = analyze_eye(pixels, 10, 9, SwitchtecGen.GEN6)
        assert result.signaling == "PAM4"
        assert len(result.eyes) == 3

    def test_empty_pixels_fail_verdict(self):
        result = analyze_eye([], 0, 0, SwitchtecGen.GEN4)
        assert result.verdict == "FAIL"
        assert result.eyes == []

    def test_all_zero_fail_verdict(self):
        result = analyze_eye([0.0] * 100, 10, 10, SwitchtecGen.GEN4)
        assert result.verdict == "FAIL"
        assert result.eyes == []

    def test_nrz_pass_verdict(self):
        """NRZ with area >= 0.20 → PASS."""
        x_count, y_count = 20, 20
        # All open (below threshold) → area ~1.0
        pixels = [1.0] * (x_count * y_count)
        pixels[0] = 100.0  # Need at least one high value for max

        result = analyze_eye(pixels, x_count, y_count, SwitchtecGen.GEN4)
        assert result.verdict == "PASS"
        assert result.overall_area > 0.20

    def test_nrz_warn_verdict(self):
        """NRZ with 0 < area < 0.20 → WARN."""
        x_count, y_count = 20, 20
        pixels = [100.0] * (x_count * y_count)
        # Open just a small area (~5%)
        for i in range(20):
            pixels[i + 180] = 1.0

        result = analyze_eye(pixels, x_count, y_count, SwitchtecGen.GEN4)
        assert result.overall_area < 0.20
        assert result.verdict == "WARN"

    def test_pam4_warn_threshold_lower(self):
        """PAM4 uses lower threshold (0.06) than NRZ (0.20)."""
        x_count, y_count = 30, 30
        pixels = [100.0] * (x_count * y_count)
        # Open ~10% per eye region → avg area ~0.10
        third = y_count // 3
        for region_idx in range(3):
            start_y = region_idx * third
            for y in range(start_y, start_y + third):
                for x in range(3):
                    pixels[y * x_count + x] = 1.0

        result = analyze_eye(pixels, x_count, y_count, SwitchtecGen.GEN6)
        assert result.signaling == "PAM4"
        # With 3/30 columns open per region, area ~0.10 which is > 0.06
        assert result.verdict == "PASS"

    def test_analysis_returns_immutable_dataclass(self):
        result = analyze_eye([100.0, 1.0], 1, 2, SwitchtecGen.GEN4)
        assert isinstance(result, EyeAnalysis)
        # Frozen dataclass
        try:
            result.verdict = "FAIL"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised

    def test_eye_metrics_immutable(self):
        m = EyeMetrics(width=10, height=20, area_fraction=0.5, threshold=5.0)
        try:
            m.width = 99  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised
