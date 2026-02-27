"""Tests for constants and enum definitions."""

from __future__ import annotations

from serialcables_switchtec.bindings.constants import (
    DiagCrossHairState,
    DiagPattern,
    GEN_DATARATE,
    GEN_TRANSFERS,
    PATH_MAX,
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
    ltssm_str,
)


class TestSwitchtecGen:
    def test_gen_values(self):
        assert SwitchtecGen.GEN3 == 0
        assert SwitchtecGen.GEN4 == 1
        assert SwitchtecGen.GEN5 == 2
        assert SwitchtecGen.GEN6 == 3

    def test_gen_from_int(self):
        assert SwitchtecGen(3) == SwitchtecGen.GEN6


class TestSwitchtecVariant:
    def test_variant_names(self):
        assert SwitchtecVariant.PFX.name == "PFX"
        assert SwitchtecVariant.PAX.name == "PAX"


class TestDiagPattern:
    def test_prbs_values(self):
        assert DiagPattern.PRBS_7 == 0
        assert DiagPattern.PRBS_31 == 3
        assert DiagPattern.DISABLED == 6


class TestLtssmStr:
    def test_gen4_l0(self):
        result = ltssm_str(0x0103, SwitchtecGen.GEN4)
        assert result == "L0 (L0)"

    def test_gen5_detect(self):
        result = ltssm_str(0xFF00, SwitchtecGen.GEN5)
        assert result == "Detect"

    def test_gen6_active(self):
        result = ltssm_str(0x11, SwitchtecGen.GEN6)
        assert result == "L0 (ACTIVE)"

    def test_unknown(self):
        result = ltssm_str(0xFFFF, SwitchtecGen.GEN4)
        assert result == "UNKNOWN"

    def test_gen4_no_minor(self):
        result = ltssm_str(0x03, SwitchtecGen.GEN4, show_minor=False)
        assert result == "L0"


class TestGenTransfers:
    def test_gen6_transfer_rate(self):
        assert GEN_TRANSFERS[6] == 64.0

    def test_gen1_transfer_rate(self):
        assert GEN_TRANSFERS[1] == 2.5


class TestGenDatarate:
    def test_gen6_datarate(self):
        assert GEN_DATARATE[6] == 7877.0

    def test_gen1_datarate(self):
        assert GEN_DATARATE[1] == 250.0


class TestPathMax:
    def test_path_max_platform(self):
        import sys
        if sys.platform == "win32":
            assert PATH_MAX == 260
        else:
            assert PATH_MAX == 4096
