"""Tests for SwitchtecDevice core module."""

from __future__ import annotations

import pytest

from serialcables_switchtec.bindings.constants import (
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
)
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


class TestSwitchtecDeviceProperties:
    def test_lib_property(self, device, mock_library):
        assert device.lib is mock_library

    def test_name(self, device):
        assert device.name == "switchtec0"

    def test_partition(self, device):
        assert device.partition == 0

    def test_device_id(self, device):
        assert device.device_id == 0x8264

    def test_generation(self, device):
        assert device.generation == SwitchtecGen.GEN6

    def test_generation_str(self, device):
        assert device.generation_str == "GEN6"

    def test_variant(self, device):
        assert device.variant == SwitchtecVariant.PFX

    def test_variant_str(self, device):
        assert device.variant_str == "PFX"

    def test_boot_phase(self, device):
        assert device.boot_phase == SwitchtecBootPhase.FW

    def test_boot_phase_str(self, device):
        assert device.boot_phase_str == "Main Firmware"

    def test_die_temperature(self, device):
        assert device.die_temperature == 42.5

    def test_get_fw_version(self, device):
        version = device.get_fw_version()
        assert version == "4.40"


class TestSwitchtecDeviceLifecycle:
    def test_context_manager(self, mock_library):
        dev = SwitchtecDevice(handle=0xDEADBEEF, lib=mock_library)
        with dev:
            assert dev.name == "switchtec0"
        mock_library.switchtec_close.assert_called_once()

    def test_close_idempotent(self, device, mock_library):
        device.close()
        device.close()
        mock_library.switchtec_close.assert_called_once()

    def test_handle_after_close(self, device):
        device.close()
        with pytest.raises(SwitchtecError, match="closed"):
            _ = device.handle
