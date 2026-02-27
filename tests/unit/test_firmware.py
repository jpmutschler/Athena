"""Tests for FirmwareManager."""

from __future__ import annotations

import ctypes

import pytest

from serialcables_switchtec.bindings.constants import FwType, SwitchtecGen
from serialcables_switchtec.bindings.types import (
    SwitchtecFwImageInfo,
    SwitchtecFwPartSummary,
)
from serialcables_switchtec.core.firmware import FirmwareManager
from serialcables_switchtec.exceptions import InvalidParameterError, SwitchtecError
from serialcables_switchtec.models.firmware import FwPartSummary


class TestFirmwareManagerGetFwVersion:
    def test_get_fw_version(self, device, mock_library) -> None:
        fw = FirmwareManager(device)
        version = fw.get_fw_version()
        assert version == "4.40"
        mock_library.switchtec_get_fw_version.assert_called_once()


class TestFirmwareManagerToggleActivePartition:
    def test_toggle_active_partition_default(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        fw.toggle_active_partition()
        mock_library.switchtec_fw_toggle_active_partition.assert_called_once_with(
            0xDEADBEEF,
            0,  # toggle_bl2=False
            0,  # toggle_key=False
            1,  # toggle_fw=True
            1,  # toggle_cfg=True
            0,  # toggle_riotcore=False
        )

    def test_toggle_active_partition_custom_flags(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        fw.toggle_active_partition(
            toggle_bl2=True,
            toggle_key=True,
            toggle_fw=False,
            toggle_cfg=False,
            toggle_riotcore=True,
        )
        mock_library.switchtec_fw_toggle_active_partition.assert_called_once_with(
            0xDEADBEEF,
            1,  # toggle_bl2=True
            1,  # toggle_key=True
            0,  # toggle_fw=False
            0,  # toggle_cfg=False
            1,  # toggle_riotcore=True
        )


class TestFirmwareManagerIsBootRo:
    def test_is_boot_ro_returns_true(self, device, mock_library) -> None:
        mock_library.switchtec_fw_is_boot_ro.return_value = 1
        fw = FirmwareManager(device)
        assert fw.is_boot_ro() is True
        mock_library.switchtec_fw_is_boot_ro.assert_called_once_with(
            0xDEADBEEF
        )

    def test_is_boot_ro_returns_false(self, device, mock_library) -> None:
        mock_library.switchtec_fw_is_boot_ro.return_value = 0
        fw = FirmwareManager(device)
        assert fw.is_boot_ro() is False
        mock_library.switchtec_fw_is_boot_ro.assert_called_once_with(
            0xDEADBEEF
        )


class TestFirmwareManagerSetBootRo:
    def test_set_boot_ro_readonly(self, device, mock_library) -> None:
        fw = FirmwareManager(device)
        fw.set_boot_ro(read_only=True)
        mock_library.switchtec_fw_set_boot_ro.assert_called_once_with(
            0xDEADBEEF, 1
        )

    def test_set_boot_ro_readwrite(self, device, mock_library) -> None:
        fw = FirmwareManager(device)
        fw.set_boot_ro(read_only=False)
        mock_library.switchtec_fw_set_boot_ro.assert_called_once_with(
            0xDEADBEEF, 0
        )


class TestFirmwareManagerReadFirmware:
    def test_read_firmware_returns_bytes(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        result = fw.read_firmware(address=0x1000, length=256)
        assert isinstance(result, bytes)
        assert len(result) == 256
        mock_library.switchtec_fw_read.assert_called_once()
        call_args = mock_library.switchtec_fw_read.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0x1000
        assert call_args[2] == 256


def _make_image_info(
    gen: int = SwitchtecGen.GEN4,
    fw_type: int = FwType.IMG,
    version: bytes = b"4.40",
    part_addr: int = 0x10000,
    part_len: int = 0x80000,
    image_len: int = 0x70000,
    valid: bool = True,
    active: bool = True,
    running: bool = False,
    read_only: bool = False,
) -> SwitchtecFwImageInfo:
    """Build a SwitchtecFwImageInfo ctypes struct for testing."""
    info = SwitchtecFwImageInfo()
    info.gen = gen
    info.type = fw_type
    info.version = version.ljust(32, b"\x00")
    info.part_addr = part_addr
    info.part_len = part_len
    info.image_len = image_len
    info.valid = valid
    info.active = active
    info.running = running
    info.read_only = read_only
    return info


def _make_part_summary_ptr(
    boot_active: SwitchtecFwImageInfo | None = None,
    img_active: SwitchtecFwImageInfo | None = None,
    img_inactive: SwitchtecFwImageInfo | None = None,
    cfg_active: SwitchtecFwImageInfo | None = None,
) -> ctypes.c_void_p:
    """Build a SwitchtecFwPartSummary and return its address as c_void_p."""
    summary = SwitchtecFwPartSummary()
    if boot_active is not None:
        summary.boot.active = ctypes.pointer(boot_active)
    if img_active is not None:
        summary.img.active = ctypes.pointer(img_active)
    if img_inactive is not None:
        summary.img.inactive = ctypes.pointer(img_inactive)
    if cfg_active is not None:
        summary.cfg.active = ctypes.pointer(cfg_active)
    return summary


class TestFirmwareManagerGetPartSummary:
    def test_get_part_summary_null_fallback(self, device, mock_library) -> None:
        """When C returns NULL, falls back to boot-RO-only summary."""
        mock_library.switchtec_fw_part_summary.return_value = None
        mock_library.switchtec_fw_is_boot_ro.return_value = 1
        fw = FirmwareManager(device)
        summary = fw.get_part_summary()
        assert isinstance(summary, FwPartSummary)
        assert summary.is_boot_ro is True
        assert summary.boot.active is None

    def test_get_part_summary_null_not_ro(self, device, mock_library) -> None:
        """NULL return with boot not RO."""
        mock_library.switchtec_fw_part_summary.return_value = None
        mock_library.switchtec_fw_is_boot_ro.return_value = 0
        fw = FirmwareManager(device)
        summary = fw.get_part_summary()
        assert isinstance(summary, FwPartSummary)
        assert summary.is_boot_ro is False
        assert summary.boot.active is None
        assert summary.boot.inactive is None

    def test_get_part_summary_full(self, device, mock_library) -> None:
        """Full partition summary with real ctypes structs."""
        boot_img = _make_image_info(
            fw_type=FwType.BOOT, version=b"1.00", read_only=True,
        )
        img_active = _make_image_info(
            fw_type=FwType.IMG, version=b"4.40", active=True, running=True,
        )
        img_inactive = _make_image_info(
            fw_type=FwType.IMG, version=b"4.30", active=False,
        )
        cfg_img = _make_image_info(
            fw_type=FwType.CFG, version=b"1.10",
        )

        # Keep reference alive so ctypes pointers stay valid
        summary_struct = _make_part_summary_ptr(
            boot_active=boot_img,
            img_active=img_active,
            img_inactive=img_inactive,
            cfg_active=cfg_img,
        )
        mock_library.switchtec_fw_part_summary.return_value = ctypes.addressof(
            summary_struct
        )
        mock_library.switchtec_fw_is_boot_ro.return_value = 1

        fw = FirmwareManager(device)
        summary = fw.get_part_summary()

        assert summary.is_boot_ro is True

        # Boot partition
        assert summary.boot.active is not None
        assert summary.boot.active.version == "1.00"
        assert summary.boot.active.read_only is True
        assert summary.boot.active.generation == "GEN4"
        assert summary.boot.active.partition_type == "BOOT"
        assert summary.boot.inactive is None

        # IMG partition
        assert summary.img.active is not None
        assert summary.img.active.version == "4.40"
        assert summary.img.active.running is True
        assert summary.img.inactive is not None
        assert summary.img.inactive.version == "4.30"
        assert summary.img.inactive.active is False

        # CFG partition
        assert summary.cfg.active is not None
        assert summary.cfg.active.version == "1.10"

        # Empty partitions
        assert summary.map.active is None
        assert summary.nvlog.active is None
        assert summary.seeprom.active is None

        # Verify free was called
        mock_library.switchtec_fw_part_summary_free.assert_called_once()


class TestFirmwareManagerErrorPaths:
    def test_toggle_active_partition_raises_on_error(
        self, device, mock_library, monkeypatch
    ) -> None:
        mock_library.switchtec_fw_toggle_active_partition.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fw = FirmwareManager(device)
        with pytest.raises(SwitchtecError):
            fw.toggle_active_partition()

    def test_read_firmware_raises_on_error(
        self, device, mock_library, monkeypatch
    ) -> None:
        mock_library.switchtec_fw_read.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fw = FirmwareManager(device)
        with pytest.raises(SwitchtecError):
            fw.read_firmware(address=0x1000, length=256)

    def test_set_boot_ro_raises_on_error(
        self, device, mock_library, monkeypatch
    ) -> None:
        mock_library.switchtec_fw_set_boot_ro.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fw = FirmwareManager(device)
        with pytest.raises(SwitchtecError):
            fw.set_boot_ro(read_only=True)

    def test_read_firmware_rejects_negative_length(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        with pytest.raises(InvalidParameterError):
            fw.read_firmware(address=0x1000, length=-1)

    def test_read_firmware_rejects_zero_length(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        with pytest.raises(InvalidParameterError):
            fw.read_firmware(address=0x1000, length=0)

    def test_read_firmware_rejects_huge_length(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        with pytest.raises(InvalidParameterError):
            fw.read_firmware(address=0x1000, length=100_000_000)

    def test_read_firmware_rejects_negative_address(
        self, device, mock_library
    ) -> None:
        fw = FirmwareManager(device)
        with pytest.raises(InvalidParameterError):
            fw.read_firmware(address=-1, length=256)


class TestFirmwareManagerViaDevice:
    def test_device_firmware_property(self, device, mock_library) -> None:
        """Verify the firmware property on SwitchtecDevice returns a FirmwareManager."""
        fw = device.firmware
        assert isinstance(fw, FirmwareManager)

    def test_device_firmware_property_cached(
        self, device, mock_library
    ) -> None:
        """Verify the firmware property returns the same instance."""
        fw1 = device.firmware
        fw2 = device.firmware
        assert fw1 is fw2
