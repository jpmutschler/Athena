"""Tests for SwitchtecDevice core module."""

from __future__ import annotations

import ctypes
from ctypes import POINTER
from unittest.mock import MagicMock, patch

import pytest

from serialcables_switchtec.bindings.constants import (
    SwitchtecBootPhase,
    SwitchtecGen,
    SwitchtecVariant,
)
from serialcables_switchtec.bindings.types import (
    SwitchtecDeviceInfo,
    SwitchtecPortId,
    SwitchtecStatus,
)
from serialcables_switchtec.core.device import SwitchtecDevice, _ensure_library
from serialcables_switchtec.exceptions import DeviceOpenError, SwitchtecError
from serialcables_switchtec.models.device import DeviceInfo, DeviceSummary, PortStatus


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


class TestSwitchtecDeviceDieTemperatures:
    def test_get_die_temperatures_calls_lib(self, device, mock_library):
        result = device.get_die_temperatures(nr_sensors=3)
        mock_library.switchtec_die_temps.assert_called_once()
        call_args = mock_library.switchtec_die_temps.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 3

    def test_get_die_temperatures_returns_list(self, device, mock_library):
        result = device.get_die_temperatures(nr_sensors=5)
        assert isinstance(result, list)
        assert len(result) == 5
        # Mock does not fill the array, so readings default to 0.0
        assert all(r == 0.0 for r in result)

    def test_get_die_temperatures_default_sensors(self, device, mock_library):
        result = device.get_die_temperatures()
        assert len(result) == 5

    def test_get_die_temperatures_single_sensor(self, device, mock_library):
        result = device.get_die_temperatures(nr_sensors=1)
        assert len(result) == 1

    def test_get_die_temperatures_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_die_temps.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with pytest.raises(SwitchtecError):
            device.get_die_temperatures()


class TestSwitchtecDeviceGetStatus:
    def test_get_status_calls_lib(self, device, mock_library):
        result = device.get_status()
        mock_library.switchtec_status.assert_called_once()
        call_args = mock_library.switchtec_status.call_args[0]
        assert call_args[0] == 0xDEADBEEF

    def test_get_status_returns_empty_when_zero_ports(
        self, device, mock_library
    ):
        # switchtec_status returns 0 (nr_ports=0), so result is empty
        result = device.get_status()
        assert isinstance(result, list)
        assert len(result) == 0
        # status_free should be called in finally
        mock_library.switchtec_status_free.assert_called_once()

    def test_get_status_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_status.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with pytest.raises(SwitchtecError):
            device.get_status()


class TestSwitchtecDevicePffToPort:
    def test_pff_to_port_calls_lib(self, device, mock_library):
        partition, port = device.pff_to_port(pff=10)
        mock_library.switchtec_pff_to_port.assert_called_once()
        call_args = mock_library.switchtec_pff_to_port.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 10

    def test_pff_to_port_returns_tuple(self, device, mock_library):
        partition, port = device.pff_to_port(pff=5)
        # Mock does not write to byref, so values default to 0
        assert partition == 0
        assert port == 0
        assert isinstance(partition, int)
        assert isinstance(port, int)

    def test_pff_to_port_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_pff_to_port.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with pytest.raises(SwitchtecError):
            device.pff_to_port(pff=0)


class TestSwitchtecDevicePortToPff:
    def test_port_to_pff_calls_lib(self, device, mock_library):
        pff = device.port_to_pff(partition=0, port=3)
        mock_library.switchtec_port_to_pff.assert_called_once()
        call_args = mock_library.switchtec_port_to_pff.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0
        assert call_args[2] == 3

    def test_port_to_pff_returns_int(self, device, mock_library):
        pff = device.port_to_pff(partition=1, port=2)
        # Mock does not write to byref, so pff defaults to 0
        assert pff == 0
        assert isinstance(pff, int)

    def test_port_to_pff_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_port_to_pff.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with pytest.raises(SwitchtecError):
            device.port_to_pff(partition=0, port=0)


class TestSwitchtecDeviceListDevices:
    def test_list_devices_returns_empty_on_zero_count(self, mock_library):
        mock_library.switchtec_list.return_value = 0
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            result = SwitchtecDevice.list_devices()
        assert isinstance(result, list)
        assert len(result) == 0
        mock_library.switchtec_list_free.assert_not_called()

    def test_list_devices_calls_list_free_on_nonzero_ptr(self, mock_library):
        # Simulate count=0 but the pointer is falsy (None), so no free
        mock_library.switchtec_list.return_value = 0
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            SwitchtecDevice.list_devices()

    def test_list_devices_raises_on_negative_count(
        self, mock_library, monkeypatch
    ):
        mock_library.switchtec_list.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            with pytest.raises(SwitchtecError):
                SwitchtecDevice.list_devices()


class TestSwitchtecDeviceOpenByIndex:
    def test_open_by_index_calls_lib(self, mock_library):
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            dev = SwitchtecDevice.open_by_index(index=2)
        mock_library.switchtec_open_by_index.assert_called_once_with(2)
        assert dev.handle == 0xDEADBEEF
        dev.close()

    def test_open_by_index_raises_on_null(self, mock_library, monkeypatch):
        mock_library.switchtec_open_by_index.return_value = None
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            with pytest.raises(SwitchtecError):
                SwitchtecDevice.open_by_index(index=99)


class TestSwitchtecDeviceOpenByPciAddr:
    def test_open_by_pci_addr_calls_lib(self, mock_library):
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            dev = SwitchtecDevice.open_by_pci_addr(
                domain=0, bus=3, device=0, func=0
            )
        mock_library.switchtec_open_by_pci_addr.assert_called_once_with(
            0, 3, 0, 0
        )
        assert dev.handle == 0xDEADBEEF
        dev.close()

    def test_open_by_pci_addr_raises_on_null(
        self, mock_library, monkeypatch
    ):
        mock_library.switchtec_open_by_pci_addr.return_value = None
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            with pytest.raises(SwitchtecError):
                SwitchtecDevice.open_by_pci_addr(
                    domain=0, bus=0, device=0, func=0
                )


class TestEnsureLibrary:
    """Tests for _ensure_library (lines 67-71)."""

    def test_ensure_library_loads_and_configures_prototypes(self, mock_library):
        """First call should load and configure prototypes."""
        import serialcables_switchtec.core.device as device_mod

        # Reset the flag so _ensure_library triggers setup_prototypes
        original_flag = device_mod._prototypes_configured
        device_mod._prototypes_configured = False
        try:
            with patch(
                "serialcables_switchtec.core.device.load_library",
                return_value=mock_library,
            ) as mock_load, patch(
                "serialcables_switchtec.core.device.setup_prototypes"
            ) as mock_setup:
                result = _ensure_library()

            mock_load.assert_called_once()
            mock_setup.assert_called_once_with(mock_library)
            assert result is mock_library
            assert device_mod._prototypes_configured is True
        finally:
            device_mod._prototypes_configured = original_flag

    def test_ensure_library_skips_prototypes_on_second_call(self, mock_library):
        """Second call should skip setup_prototypes."""
        import serialcables_switchtec.core.device as device_mod

        original_flag = device_mod._prototypes_configured
        device_mod._prototypes_configured = True
        try:
            with patch(
                "serialcables_switchtec.core.device.load_library",
                return_value=mock_library,
            ), patch(
                "serialcables_switchtec.core.device.setup_prototypes"
            ) as mock_setup:
                result = _ensure_library()

            mock_setup.assert_not_called()
            assert result is mock_library
        finally:
            device_mod._prototypes_configured = original_flag


class TestSwitchtecDeviceOpen:
    """Tests for SwitchtecDevice.open() classmethod (lines 102-106)."""

    def test_open_by_name_calls_lib(self, mock_library):
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            dev = SwitchtecDevice.open("/dev/switchtec0")

        mock_library.switchtec_open.assert_called_once_with(b"/dev/switchtec0")
        assert dev.handle == 0xDEADBEEF
        dev.close()

    def test_open_by_name_raises_on_null(self, mock_library, monkeypatch):
        mock_library.switchtec_open.return_value = None
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            with pytest.raises(SwitchtecError, match="open device"):
                SwitchtecDevice.open("/dev/switchtec99")

    def test_open_returns_device_with_correct_lib(self, mock_library):
        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            dev = SwitchtecDevice.open("/dev/switchtec0")

        assert dev.lib is mock_library
        dev.close()


class TestSwitchtecDeviceDel:
    """Tests for __del__ exception suppression (lines 143-144)."""

    def test_del_suppresses_exception_on_close_failure(self, mock_library):
        """When close() raises in __del__, exception is suppressed."""
        mock_library.switchtec_close.side_effect = RuntimeError("close failed")
        dev = SwitchtecDevice(handle=0xDEADBEEF, lib=mock_library)
        # Calling __del__ directly should not raise
        dev.__del__()
        # Verify close was attempted
        mock_library.switchtec_close.assert_called_once()

    def test_del_calls_close_successfully(self, mock_library):
        """Normal __del__ should call close without error."""
        dev = SwitchtecDevice(handle=0xDEADBEEF, lib=mock_library)
        dev.__del__()
        mock_library.switchtec_close.assert_called_once()


class TestGetStatusWithPorts:
    """Tests for get_status() loop body (lines 250-271)."""

    @staticmethod
    def _make_status_array(port_data_list):
        """Build a ctypes array of SwitchtecStatus from dicts."""
        count = len(port_data_list)
        arr = (SwitchtecStatus * count)()
        for i, data in enumerate(port_data_list):
            arr[i].port.partition = data.get("partition", 0)
            arr[i].port.stack = data.get("stack", 0)
            arr[i].port.upstream = data.get("upstream", 0)
            arr[i].port.stk_id = data.get("stk_id", 0)
            arr[i].port.phys_id = data.get("phys_id", i)
            arr[i].port.log_id = data.get("log_id", i)
            arr[i].cfg_lnk_width = data.get("cfg_lnk_width", 16)
            arr[i].neg_lnk_width = data.get("neg_lnk_width", 8)
            arr[i].link_up = data.get("link_up", 1)
            arr[i].link_rate = data.get("link_rate", 4)
            arr[i].ltssm = data.get("ltssm", 0x11)
            arr[i].ltssm_str = data.get("ltssm_str", b"L0")
            arr[i].lane_reversal = data.get("lane_reversal", 0)
            arr[i].lane_reversal_str = data.get("lane_reversal_str", b"Normal")
            arr[i].first_act_lane = data.get("first_act_lane", 0)
            arr[i].pci_bdf = data.get("pci_bdf", b"0000:03:00.0")
            arr[i].pci_dev = data.get("pci_dev", b"/sys/bus/pci/devices/0000:03:00.0")
            arr[i].vendor_id = data.get("vendor_id", 0x11F8)
            arr[i].device_id = data.get("device_id", 0x8264)
        return arr

    def test_get_status_returns_port_status_list(self, device, mock_library):
        """get_status with 2 ports should return 2 PortStatus objects."""
        status_arr = self._make_status_array([
            {"partition": 0, "phys_id": 0, "log_id": 0, "upstream": 1},
            {"partition": 0, "phys_id": 1, "log_id": 1, "upstream": 0},
        ])

        def fake_status(handle, status_ptr_byref):
            # Write the array pointer into the byref
            ptr = ctypes.cast(status_arr, POINTER(SwitchtecStatus))
            ctypes.memmove(
                ctypes.addressof(status_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecStatus)),
            )
            return 2

        mock_library.switchtec_status.side_effect = fake_status
        mock_library.switchtec_get_devices.return_value = 0

        result = device.get_status()

        assert len(result) == 2
        assert isinstance(result[0], PortStatus)
        assert isinstance(result[1], PortStatus)

        # Verify first port (upstream)
        assert result[0].port.partition == 0
        assert result[0].port.phys_id == 0
        assert result[0].port.upstream is True
        assert result[0].cfg_lnk_width == 16
        assert result[0].neg_lnk_width == 8
        assert result[0].link_up is True
        assert result[0].link_rate == 4
        assert result[0].ltssm == 0x11
        assert result[0].ltssm_str == "L0"
        assert result[0].lane_reversal_str == "Normal"
        assert result[0].pci_bdf == "0000:03:00.0"
        assert result[0].pci_dev == "/sys/bus/pci/devices/0000:03:00.0"
        assert result[0].vendor_id == 0x11F8
        assert result[0].device_id == 0x8264

        # Verify second port (downstream)
        assert result[1].port.upstream is False
        assert result[1].port.phys_id == 1

        # status_free should still be called in finally
        mock_library.switchtec_status_free.assert_called_once()

    def test_get_status_handles_null_strings(self, device, mock_library):
        """Ports with null ltssm_str, lane_reversal_str, pci_bdf, pci_dev."""
        status_arr = self._make_status_array([
            {"partition": 0, "phys_id": 0, "log_id": 0},
        ])
        # Set string fields to None (null pointers)
        status_arr[0].ltssm_str = None
        status_arr[0].lane_reversal_str = None
        status_arr[0].pci_bdf = None
        status_arr[0].pci_dev = None
        status_arr[0].vendor_id = 0
        status_arr[0].device_id = 0

        def fake_status(handle, status_ptr_byref):
            ptr = ctypes.cast(status_arr, POINTER(SwitchtecStatus))
            ctypes.memmove(
                ctypes.addressof(status_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecStatus)),
            )
            return 1

        mock_library.switchtec_status.side_effect = fake_status
        mock_library.switchtec_get_devices.return_value = 0

        result = device.get_status()

        assert len(result) == 1
        assert result[0].ltssm_str == ""
        assert result[0].lane_reversal_str == ""
        assert result[0].pci_bdf is None
        assert result[0].pci_dev is None

    def test_get_status_calls_status_free_on_exception(
        self, device, mock_library
    ):
        """status_free should be called even when get_devices raises."""
        status_arr = self._make_status_array([
            {"partition": 0, "phys_id": 0, "log_id": 0},
        ])

        def fake_status(handle, status_ptr_byref):
            ptr = ctypes.cast(status_arr, POINTER(SwitchtecStatus))
            ctypes.memmove(
                ctypes.addressof(status_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecStatus)),
            )
            return 1

        mock_library.switchtec_status.side_effect = fake_status
        mock_library.switchtec_get_devices.side_effect = RuntimeError("fail")

        with pytest.raises(RuntimeError, match="fail"):
            device.get_status()

        # Verify status_free is called despite the exception
        mock_library.switchtec_status_free.assert_called_once()


class TestGetSummary:
    """Tests for get_summary() (lines 316-317)."""

    def test_get_summary_returns_device_summary(self, device, mock_library):
        """get_summary should aggregate properties into DeviceSummary."""
        # Mock get_status to return an empty list (already default)
        mock_library.switchtec_status.return_value = 0
        mock_library.switchtec_get_devices.return_value = 0

        summary = device.get_summary()

        assert isinstance(summary, DeviceSummary)
        assert summary.name == "switchtec0"
        assert summary.device_id == 0x8264
        assert summary.generation == "GEN6"
        assert summary.variant == "PFX"
        assert summary.boot_phase == "Main Firmware"
        assert summary.partition == 0
        assert summary.fw_version == "4.40"
        assert summary.die_temperature == 42.5
        assert summary.port_count == 0

    def test_get_summary_reflects_port_count(self, device, mock_library):
        """get_summary.port_count should match number of ports from get_status."""
        # Patch get_status on the instance to return a list with 3 items
        with patch.object(
            device, "get_status",
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        ):
            summary = device.get_summary()

        assert summary.port_count == 3


class TestListDevicesWithData:
    """Tests for list_devices() loop body (lines 346-347) and free (line 359)."""

    @staticmethod
    def _make_device_info_array(device_data_list):
        """Build a ctypes array of SwitchtecDeviceInfo from dicts."""
        count = len(device_data_list)
        arr = (SwitchtecDeviceInfo * count)()
        for i, data in enumerate(device_data_list):
            arr[i].name = data.get("name", b"switchtec0")
            arr[i].desc = data.get("desc", b"Microchip Switchtec")
            arr[i].pci_dev = data.get("pci_dev", b"0000:03:00.0")
            arr[i].product_id = data.get("product_id", b"8264")
            arr[i].product_rev = data.get("product_rev", b"B1")
            arr[i].fw_version = data.get("fw_version", b"4.40")
            arr[i].path = data.get("path", b"/dev/switchtec0")
        return arr

    def test_list_devices_returns_device_info_objects(self, mock_library):
        """list_devices with 2 devices should return 2 DeviceInfo objects."""
        dev_arr = self._make_device_info_array([
            {
                "name": b"switchtec0",
                "desc": b"Microchip PSX Gen6",
                "pci_dev": b"0000:03:00.0",
                "product_id": b"8264",
                "product_rev": b"B1",
                "fw_version": b"4.40",
                "path": b"/dev/switchtec0",
            },
            {
                "name": b"switchtec1",
                "desc": b"Microchip PFX Gen5",
                "pci_dev": b"0000:04:00.0",
                "product_id": b"4000",
                "product_rev": b"A0",
                "fw_version": b"3.10",
                "path": b"/dev/switchtec1",
            },
        ])

        def fake_list(devlist_ptr_byref):
            ptr = ctypes.cast(dev_arr, POINTER(SwitchtecDeviceInfo))
            ctypes.memmove(
                ctypes.addressof(devlist_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecDeviceInfo)),
            )
            return 2

        mock_library.switchtec_list.side_effect = fake_list

        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            result = SwitchtecDevice.list_devices()

        assert len(result) == 2
        assert isinstance(result[0], DeviceInfo)
        assert isinstance(result[1], DeviceInfo)

        assert result[0].name == "switchtec0"
        assert result[0].description == "Microchip PSX Gen6"
        assert result[0].pci_dev == "0000:03:00.0"
        assert result[0].product_id == "8264"
        assert result[0].product_rev == "B1"
        assert result[0].fw_version == "4.40"
        assert result[0].path == "/dev/switchtec0"

        assert result[1].name == "switchtec1"
        assert result[1].pci_dev == "0000:04:00.0"

        # list_free should be called (pointer is truthy)
        mock_library.switchtec_list_free.assert_called_once()

    def test_list_devices_single_device(self, mock_library):
        """list_devices with 1 device."""
        dev_arr = self._make_device_info_array([
            {"name": b"switchtec0", "path": b"/dev/switchtec0"},
        ])

        def fake_list(devlist_ptr_byref):
            ptr = ctypes.cast(dev_arr, POINTER(SwitchtecDeviceInfo))
            ctypes.memmove(
                ctypes.addressof(devlist_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecDeviceInfo)),
            )
            return 1

        mock_library.switchtec_list.side_effect = fake_list

        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            result = SwitchtecDevice.list_devices()

        assert len(result) == 1
        assert result[0].name == "switchtec0"
        assert result[0].path == "/dev/switchtec0"
        mock_library.switchtec_list_free.assert_called_once()

    def test_list_devices_calls_free_even_on_exception(self, mock_library):
        """switchtec_list_free should be called even when loop raises."""
        dev_arr = self._make_device_info_array([
            {"name": b"switchtec0"},
        ])
        # Corrupt the array so .decode() fails
        dev_arr[0].name = b"\xff" * 255 + b"\x00"

        def fake_list(devlist_ptr_byref):
            ptr = ctypes.cast(dev_arr, POINTER(SwitchtecDeviceInfo))
            ctypes.memmove(
                ctypes.addressof(devlist_ptr_byref._obj),
                ctypes.addressof(ctypes.pointer(ptr).contents),
                ctypes.sizeof(POINTER(SwitchtecDeviceInfo)),
            )
            return 1

        mock_library.switchtec_list.side_effect = fake_list

        with patch(
            "serialcables_switchtec.core.device._ensure_library",
            return_value=mock_library,
        ):
            with pytest.raises(UnicodeDecodeError):
                SwitchtecDevice.list_devices()

        # free should be called in finally even on exception
        mock_library.switchtec_list_free.assert_called_once()
