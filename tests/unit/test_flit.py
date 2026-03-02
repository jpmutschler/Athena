"""Tests for Gen6 FLIT mode inference and labeling."""

from __future__ import annotations

from serialcables_switchtec.bindings.constants import FlitMode, SwitchtecGen
from serialcables_switchtec.core.flit import flit_mode_label, infer_flit_mode


class TestInferFlitMode:
    """Tests for infer_flit_mode()."""

    def test_gen6_at_gen6_rate_returns_flit_68b(self):
        assert infer_flit_mode(SwitchtecGen.GEN6, 6) == FlitMode.FLIT_68B

    def test_gen6_at_higher_rate_returns_flit_68b(self):
        assert infer_flit_mode(SwitchtecGen.GEN6, 7) == FlitMode.FLIT_68B

    def test_gen6_at_gen5_rate_returns_off(self):
        """Gen6 device training at Gen5 speed uses traditional TLP."""
        assert infer_flit_mode(SwitchtecGen.GEN6, 5) == FlitMode.OFF

    def test_gen6_at_gen3_rate_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.GEN6, 3) == FlitMode.OFF

    def test_gen5_at_gen5_rate_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.GEN5, 5) == FlitMode.OFF

    def test_gen4_at_gen4_rate_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.GEN4, 4) == FlitMode.OFF

    def test_gen3_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.GEN3, 3) == FlitMode.OFF

    def test_unknown_gen_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.UNKNOWN, 6) == FlitMode.OFF

    def test_gen5_at_gen6_rate_returns_off(self):
        """Gen5 device should not report FLIT even at rate=6."""
        assert infer_flit_mode(SwitchtecGen.GEN5, 6) == FlitMode.OFF

    def test_link_rate_zero_returns_off(self):
        assert infer_flit_mode(SwitchtecGen.GEN6, 0) == FlitMode.OFF


class TestFlitModeLabel:
    """Tests for flit_mode_label()."""

    def test_off_label(self):
        assert flit_mode_label(FlitMode.OFF) == "OFF"

    def test_68b_label(self):
        assert flit_mode_label(FlitMode.FLIT_68B) == "68B"

    def test_256b_label(self):
        assert flit_mode_label(FlitMode.FLIT_256B) == "256B"


class TestFlitModeEnum:
    """Tests for FlitMode enum values."""

    def test_enum_values(self):
        assert FlitMode.OFF == 0
        assert FlitMode.FLIT_68B == 1
        assert FlitMode.FLIT_256B == 2

    def test_enum_is_int(self):
        assert isinstance(FlitMode.OFF, int)
