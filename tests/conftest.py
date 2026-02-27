"""Shared test fixtures with FakeLibrary mock."""

from __future__ import annotations

import ctypes
from ctypes import c_float, c_int
from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.bindings import library as library_module
from serialcables_switchtec.bindings.constants import (
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
)


class FakeLibrary:
    """Mock Switchtec library for testing without hardware."""

    def __init__(self) -> None:
        self._handle = 0xDEADBEEF

        # Platform functions
        self.switchtec_open = MagicMock(return_value=self._handle)
        self.switchtec_open_by_index = MagicMock(return_value=self._handle)
        self.switchtec_open_by_pci_addr = MagicMock(return_value=self._handle)
        self.switchtec_close = MagicMock()
        self.switchtec_list = MagicMock(return_value=0)
        self.switchtec_list_free = MagicMock()

        # Accessor functions
        self.switchtec_name = MagicMock(return_value=b"switchtec0")
        self.switchtec_partition = MagicMock(return_value=0)
        self.switchtec_device_id = MagicMock(return_value=0x8264)
        self.switchtec_gen = MagicMock(return_value=SwitchtecGen.GEN6)
        self.switchtec_variant = MagicMock(return_value=SwitchtecVariant.PFX)
        self.switchtec_boot_phase = MagicMock(return_value=SwitchtecBootPhase.FW)

        # Status functions
        self.switchtec_status = MagicMock(return_value=0)
        self.switchtec_status_free = MagicMock()
        self.switchtec_die_temp = MagicMock(return_value=42.5)
        self.switchtec_die_temps = MagicMock(return_value=0)
        self.switchtec_get_fw_version = MagicMock(side_effect=self._get_fw_version)
        self.switchtec_get_device_info = MagicMock(return_value=0)
        self.switchtec_get_devices = MagicMock(return_value=0)
        self.switchtec_hard_reset = MagicMock(return_value=0)
        self.switchtec_calc_lane_id = MagicMock(return_value=0)

        # Port mapping
        self.switchtec_pff_to_port = MagicMock(return_value=0)
        self.switchtec_port_to_pff = MagicMock(return_value=0)

        # Error functions
        self.switchtec_strerror = MagicMock(return_value=b"No error")
        self.switchtec_perror = MagicMock()

        # Event functions
        self.switchtec_event_summary = MagicMock(return_value=0)
        self.switchtec_event_ctl = MagicMock(return_value=0)
        self.switchtec_event_wait = MagicMock(return_value=0)

        # BW/Lat functions
        self.switchtec_bwcntr_many = MagicMock(return_value=0)
        self.switchtec_bwcntr_all = MagicMock(return_value=0)
        self.switchtec_lat_setup = MagicMock(return_value=0)
        self.switchtec_lat_get = MagicMock(return_value=0)

        # Diag functions
        self.switchtec_diag_cross_hair_enable = MagicMock(return_value=0)
        self.switchtec_diag_cross_hair_disable = MagicMock(return_value=0)
        self.switchtec_diag_cross_hair_get = MagicMock(return_value=0)
        self.switchtec_diag_eye_set_mode = MagicMock(return_value=0)
        self.switchtec_diag_eye_start = MagicMock(return_value=0)
        self.switchtec_diag_eye_fetch = MagicMock(return_value=0)
        self.switchtec_diag_eye_cancel = MagicMock(return_value=0)
        self.switchtec_diag_eye_read = MagicMock(return_value=0)
        self.switchtec_diag_loopback_set = MagicMock(return_value=0)
        self.switchtec_diag_loopback_get = MagicMock(return_value=0)
        self.switchtec_diag_pattern_gen_set = MagicMock(return_value=0)
        self.switchtec_diag_pattern_gen_get = MagicMock(return_value=0)
        self.switchtec_diag_pattern_mon_set = MagicMock(return_value=0)
        self.switchtec_diag_pattern_mon_get = MagicMock(return_value=0)
        self.switchtec_diag_pattern_inject = MagicMock(return_value=0)
        self.switchtec_diag_rcvr_obj = MagicMock(return_value=0)
        self.switchtec_diag_rcvr_ext = MagicMock(return_value=0)
        self.switchtec_diag_port_eq_tx_coeff = MagicMock(return_value=0)
        self.switchtec_diag_port_eq_tx_table = MagicMock(return_value=0)
        self.switchtec_diag_port_eq_tx_fslf = MagicMock(return_value=0)
        self.switchtec_diag_ltssm_log = MagicMock(return_value=0)
        self.switchtec_diag_ltssm_clear = MagicMock(return_value=0)

        # Inject functions
        self.switchtec_inject_err_dllp = MagicMock(return_value=0)
        self.switchtec_inject_err_dllp_crc = MagicMock(return_value=0)
        self.switchtec_inject_err_tlp_lcrc = MagicMock(return_value=0)
        self.switchtec_inject_err_tlp_seq_num = MagicMock(return_value=0)
        self.switchtec_inject_err_ack_nack = MagicMock(return_value=0)
        self.switchtec_inject_err_cto = MagicMock(return_value=0)

        # OSA functions
        self.switchtec_osa = MagicMock(return_value=0)
        self.switchtec_osa_config_type = MagicMock(return_value=0)
        self.switchtec_osa_config_pattern = MagicMock(return_value=0)
        self.switchtec_osa_capture_control = MagicMock(return_value=0)
        self.switchtec_osa_capture_data = MagicMock(return_value=0)
        self.switchtec_osa_dump_conf = MagicMock(return_value=0)

    def _get_fw_version(self, handle, buf, buflen):
        version = b"4.40"
        for i, byte in enumerate(version):
            buf[i] = byte
        buf[len(version)] = 0
        return 0


@pytest.fixture
def fake_lib():
    """Provide a FakeLibrary instance."""
    return FakeLibrary()


@pytest.fixture
def mock_library(fake_lib, monkeypatch):
    """Patch the library module to use FakeLibrary."""
    monkeypatch.setattr(library_module, "_lib_instance", fake_lib)
    yield fake_lib
    monkeypatch.setattr(library_module, "_lib_instance", None)


@pytest.fixture
def device(mock_library):
    """Provide a SwitchtecDevice using the mock library."""
    from serialcables_switchtec.core.device import SwitchtecDevice
    return SwitchtecDevice(handle=0xDEADBEEF, lib=mock_library)
