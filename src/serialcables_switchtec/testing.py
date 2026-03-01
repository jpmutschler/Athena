"""Public testing utilities for validation engineers.

Import from ``serialcables_switchtec.testing`` instead of copying
conftest internals.  Works with or without pytest installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple
from unittest.mock import MagicMock

from serialcables_switchtec.bindings.constants import (
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
)

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

__all__ = [
    "FakeLibrary",
    "MockDeviceResult",
    "create_mock_device",
    "patch_library",
    "reset_rate_limiters",
]


class MockDeviceResult(NamedTuple):
    """Result of :func:`create_mock_device`."""

    device: SwitchtecDevice
    fake_lib: FakeLibrary


class FakeLibrary:
    """Mock Switchtec C library with MagicMock stubs for every function."""

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
        self.switchtec_boot_phase = MagicMock(
            return_value=SwitchtecBootPhase.FW,
        )

        # Status functions
        self.switchtec_status = MagicMock(return_value=0)
        self.switchtec_status_free = MagicMock()
        self.switchtec_die_temp = MagicMock(return_value=42.5)
        self.switchtec_die_temps = MagicMock(return_value=0)
        self.switchtec_get_fw_version = MagicMock(
            side_effect=self._get_fw_version,
        )
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

        # Firmware functions
        self.switchtec_fw_toggle_active_partition = MagicMock(
            return_value=0,
        )
        self.switchtec_fw_read = MagicMock(return_value=0)
        self.switchtec_fw_part_summary = MagicMock(return_value=None)
        self.switchtec_fw_part_summary_free = MagicMock()
        self.switchtec_fw_is_boot_ro = MagicMock(return_value=0)
        self.switchtec_fw_set_boot_ro = MagicMock(return_value=0)
        self.switchtec_fw_image_type = MagicMock(return_value=b"IMG")
        self.switchtec_fw_write_fd = MagicMock(return_value=0)

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

        # AER event generation
        self.switchtec_aer_event_gen = MagicMock(return_value=0)

        # Inject functions
        self.switchtec_inject_err_dllp = MagicMock(return_value=0)
        self.switchtec_inject_err_dllp_crc = MagicMock(return_value=0)
        self.switchtec_inject_err_tlp_lcrc = MagicMock(return_value=0)
        self.switchtec_inject_err_tlp_seq_num = MagicMock(return_value=0)
        self.switchtec_inject_err_ack_nack = MagicMock(return_value=0)
        self.switchtec_inject_err_cto = MagicMock(return_value=0)

        # Fabric functions
        self.switchtec_topo_info_dump = MagicMock(return_value=0)
        self.switchtec_fab_port_config_get = MagicMock(return_value=0)
        self.switchtec_fab_port_config_set = MagicMock(return_value=0)
        self.switchtec_port_control = MagicMock(return_value=0)
        self.switchtec_gfms_bind = MagicMock(return_value=0)
        self.switchtec_gfms_unbind = MagicMock(return_value=0)
        self.switchtec_get_gfms_events = MagicMock(return_value=0)
        self.switchtec_clear_gfms_events = MagicMock(return_value=0)

        # Endpoint config space read/write
        self.switchtec_ep_csr_read8 = MagicMock(return_value=0)
        self.switchtec_ep_csr_read16 = MagicMock(return_value=0)
        self.switchtec_ep_csr_read32 = MagicMock(return_value=0)
        self.switchtec_ep_csr_write8 = MagicMock(return_value=0)
        self.switchtec_ep_csr_write16 = MagicMock(return_value=0)
        self.switchtec_ep_csr_write32 = MagicMock(return_value=0)

        # Event counter functions
        self.switchtec_evcntr_type_count = MagicMock(return_value=0)
        self.switchtec_evcntr_setup = MagicMock(return_value=0)
        self.switchtec_evcntr_get_setup = MagicMock(return_value=0)
        self.switchtec_evcntr_get = MagicMock(return_value=0)
        self.switchtec_evcntr_get_both = MagicMock(return_value=0)
        self.switchtec_evcntr_wait = MagicMock(return_value=0)

        # OSA functions
        self.switchtec_osa = MagicMock(return_value=0)
        self.switchtec_osa_config_type = MagicMock(return_value=0)
        self.switchtec_osa_config_pattern = MagicMock(return_value=0)
        self.switchtec_osa_capture_control = MagicMock(return_value=0)
        self.switchtec_osa_capture_data = MagicMock(return_value=0)
        self.switchtec_osa_dump_conf = MagicMock(return_value=0)

        # Raw MRPC command
        self.switchtec_cmd = MagicMock(return_value=0)

    def _get_fw_version(self, handle: int, buf: bytearray, buflen: int) -> int:
        """Populate *buf* with a fake firmware version string."""
        version = b"4.40"
        for i, byte in enumerate(version):
            buf[i] = byte
        buf[len(version)] = 0
        return 0


def create_mock_device() -> MockDeviceResult:
    """Create a ``SwitchtecDevice`` backed by :class:`FakeLibrary`.

    Returns a :class:`MockDeviceResult` ``(device, fake_lib)`` so callers
    can configure mock return values before exercising the device.
    Does not require pytest.
    """
    from serialcables_switchtec.core.device import SwitchtecDevice

    fake_lib = FakeLibrary()
    device = SwitchtecDevice(handle=0xDEADBEEF, lib=fake_lib)
    return MockDeviceResult(device=device, fake_lib=fake_lib)


def patch_library(monkeypatch: object) -> FakeLibrary:
    """Patch the global library singleton with a :class:`FakeLibrary`.

    *monkeypatch* should be a ``pytest.MonkeyPatch`` (or any object with
    a compatible ``setattr``).  Returns the installed :class:`FakeLibrary`.
    """
    from serialcables_switchtec.bindings import library as library_module

    fake_lib = FakeLibrary()
    monkeypatch.setattr(library_module, "_lib_instance", fake_lib)  # type: ignore[attr-defined]
    return fake_lib


def reset_rate_limiters() -> None:
    """Reset all API rate limiters to prevent cross-test leakage."""
    from serialcables_switchtec.api.rate_limit import (
        csr_write_limiter,
        fabric_control_limiter,
        hard_reset_limiter,
        injection_limiter,
        mrpc_limiter,
    )

    hard_reset_limiter.reset()
    injection_limiter.reset()
    fabric_control_limiter.reset()
    mrpc_limiter.reset()
    csr_write_limiter.reset()
