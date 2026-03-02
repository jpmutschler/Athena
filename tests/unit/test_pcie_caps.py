"""Tests for PCIe extended capability walker."""

from __future__ import annotations

import pytest

from serialcables_switchtec.core.pcie_caps import (
    PCIE_EXT_CAP_IDS,
    ExtCapEntry,
    walk_extended_caps,
)


def _make_ext_cap_header(cap_id: int, version: int, next_offset: int) -> int:
    """Build a 32-bit extended capability header."""
    return (cap_id & 0xFFFF) | ((version & 0xF) << 16) | ((next_offset & 0xFFC) << 20)


class TestWalkExtendedCaps:
    """Tests for walk_extended_caps()."""

    def test_single_cap(self):
        """Single AER capability at 0x100, no next."""
        config = {0x100: _make_ext_cap_header(0x0001, 2, 0)}

        caps = walk_extended_caps(lambda offset: config.get(offset, 0))
        assert len(caps) == 1
        assert caps[0].cap_id == 0x0001
        assert caps[0].cap_name == "AER"
        assert caps[0].version == 2
        assert caps[0].offset == 0x100

    def test_chain_of_three(self):
        """AER -> SR-IOV -> DPC linked list."""
        config = {
            0x100: _make_ext_cap_header(0x0001, 2, 0x200),
            0x200: _make_ext_cap_header(0x0010, 1, 0x300),
            0x300: _make_ext_cap_header(0x001D, 1, 0),
        }

        caps = walk_extended_caps(lambda offset: config.get(offset, 0))
        assert len(caps) == 3
        assert caps[0].cap_name == "AER"
        assert caps[1].cap_name == "SR-IOV"
        assert caps[2].cap_name == "DPC"

    def test_empty_chain(self):
        """No capabilities (header reads zero)."""
        caps = walk_extended_caps(lambda offset: 0)
        assert caps == []

    def test_all_ones_terminates(self):
        """Config space returning 0xFFFFFFFF (device not present)."""
        caps = walk_extended_caps(lambda offset: 0xFFFFFFFF)
        assert caps == []

    def test_circular_list_terminates(self):
        """Circular linked list does not loop forever."""
        config = {
            0x100: _make_ext_cap_header(0x0001, 1, 0x200),
            0x200: _make_ext_cap_header(0x0010, 1, 0x100),  # loops back
        }

        caps = walk_extended_caps(lambda offset: config.get(offset, 0))
        assert len(caps) == 2

    def test_unknown_cap_id(self):
        """Unknown capability IDs get a descriptive name."""
        config = {0x100: _make_ext_cap_header(0xBEEF, 1, 0)}

        caps = walk_extended_caps(lambda offset: config.get(offset, 0))
        assert len(caps) == 1
        assert "Unknown" in caps[0].cap_name
        assert "0xBEEF" in caps[0].cap_name

    def test_gen6_flit_logging_cap(self):
        """FLIT Logging capability (0x0031) is recognized."""
        config = {0x100: _make_ext_cap_header(0x0031, 1, 0)}

        caps = walk_extended_caps(lambda offset: config.get(offset, 0))
        assert len(caps) == 1
        assert caps[0].cap_name == "FLIT Logging"

    def test_ext_cap_entry_is_frozen(self):
        entry = ExtCapEntry(cap_id=1, cap_name="AER", version=2, offset=0x100)
        with pytest.raises(AttributeError):
            entry.cap_id = 99


class TestPcieExtCapIds:
    """Tests for the capability ID lookup table."""

    def test_well_known_caps_present(self):
        assert 0x0001 in PCIE_EXT_CAP_IDS  # AER
        assert 0x0010 in PCIE_EXT_CAP_IDS  # SR-IOV
        assert 0x001D in PCIE_EXT_CAP_IDS  # DPC
        assert 0x0030 in PCIE_EXT_CAP_IDS  # PL 64.0 GT/s
        assert 0x0031 in PCIE_EXT_CAP_IDS  # FLIT Logging

    def test_gen6_caps_present(self):
        """Gen6-specific capabilities should be in the table."""
        assert "Physical Layer 64.0 GT/s" in PCIE_EXT_CAP_IDS.values()
        assert "FLIT Logging" in PCIE_EXT_CAP_IDS.values()
        assert "FLIT Performance" in PCIE_EXT_CAP_IDS.values()
        assert "FLIT Error Injection" in PCIE_EXT_CAP_IDS.values()
