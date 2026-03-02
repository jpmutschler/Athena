"""Tests for FabricManager."""

from __future__ import annotations

import ctypes

import pytest

from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.bindings.types import (
    SwitchtecFabPortConfig,
    SwitchtecGfmsBindReq,
    SwitchtecGfmsUnbindReq,
)
from serialcables_switchtec.core.fabric import FabricManager
from serialcables_switchtec.exceptions import InvalidParameterError, SwitchtecError
from serialcables_switchtec.models.fabric import (
    FabPortConfig,
    GfmsBindRequest,
    GfmsUnbindRequest,
)


class TestPortControlEnable:
    def test_port_control_enable(self, device, mock_library):
        fab = FabricManager(device)
        fab.port_control(
            phys_port_id=3,
            control_type=FabPortControlType.ENABLE,
        )
        mock_library.switchtec_port_control.assert_called_once_with(
            0xDEADBEEF,
            int(FabPortControlType.ENABLE),
            3,
            int(FabHotResetFlag.NONE),
        )

    def test_port_control_enable_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_port_control.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError):
            fab.port_control(
                phys_port_id=3,
                control_type=FabPortControlType.ENABLE,
            )


class TestPortControlDisable:
    def test_port_control_disable(self, device, mock_library):
        fab = FabricManager(device)
        fab.port_control(
            phys_port_id=5,
            control_type=FabPortControlType.DISABLE,
        )
        mock_library.switchtec_port_control.assert_called_once_with(
            0xDEADBEEF,
            int(FabPortControlType.DISABLE),
            5,
            int(FabHotResetFlag.NONE),
        )


class TestPortControlHotReset:
    def test_port_control_hot_reset(self, device, mock_library):
        fab = FabricManager(device)
        fab.port_control(
            phys_port_id=2,
            control_type=FabPortControlType.HOT_RESET,
            hot_reset_flag=FabHotResetFlag.PERST,
        )
        mock_library.switchtec_port_control.assert_called_once_with(
            0xDEADBEEF,
            int(FabPortControlType.HOT_RESET),
            2,
            int(FabHotResetFlag.PERST),
        )

    def test_port_control_hot_reset_default_flag(self, device, mock_library):
        fab = FabricManager(device)
        fab.port_control(
            phys_port_id=1,
            control_type=FabPortControlType.HOT_RESET,
        )
        mock_library.switchtec_port_control.assert_called_once_with(
            0xDEADBEEF,
            int(FabPortControlType.HOT_RESET),
            1,
            int(FabHotResetFlag.NONE),
        )


class TestGetPortConfig:
    def test_get_port_config_calls_lib(self, device, mock_library):
        fab = FabricManager(device)
        fab.get_port_config(phys_port_id=4)
        mock_library.switchtec_fab_port_config_get.assert_called_once()
        call_args = mock_library.switchtec_fab_port_config_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 4

    def test_get_port_config_returns_fab_port_config(self, device, mock_library):
        fab = FabricManager(device)
        result = fab.get_port_config(phys_port_id=7)
        assert isinstance(result, FabPortConfig)
        assert result.phys_port_id == 7
        # Mock does not fill struct, so fields default to 0
        assert result.port_type == 0
        assert result.clock_source == 0
        assert result.clock_sris == 0
        assert result.hvd_inst == 0

    def test_get_port_config_with_filled_struct(self, device, mock_library):
        def _fill_port_config(handle, port_id, config_ref):
            config = ctypes.cast(
                config_ref, ctypes.POINTER(SwitchtecFabPortConfig)
            ).contents
            config.port_type = 1
            config.clock_source = 2
            config.clock_sris = 3
            config.hvd_inst = 4
            return 0

        mock_library.switchtec_fab_port_config_get.side_effect = _fill_port_config
        fab = FabricManager(device)
        result = fab.get_port_config(phys_port_id=5)
        assert result.phys_port_id == 5
        assert result.port_type == 1
        assert result.clock_source == 2
        assert result.clock_sris == 3
        assert result.hvd_inst == 4

    def test_get_port_config_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_fab_port_config_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError):
            fab.get_port_config(phys_port_id=0)


class TestSetPortConfig:
    def test_set_port_config_calls_lib(self, device, mock_library):
        fab = FabricManager(device)
        config = FabPortConfig(
            phys_port_id=2,
            port_type=1,
            clock_source=0,
            clock_sris=1,
            hvd_inst=3,
        )
        fab.set_port_config(config)
        mock_library.switchtec_fab_port_config_set.assert_called_once()
        call_args = mock_library.switchtec_fab_port_config_set.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2

    def test_set_port_config_verifies_struct_fields(self, device, mock_library):
        captured = {}

        def _capture_set(handle, port_id, config_ref):
            config = ctypes.cast(
                config_ref, ctypes.POINTER(SwitchtecFabPortConfig)
            ).contents
            captured["port_type"] = config.port_type
            captured["clock_source"] = config.clock_source
            captured["clock_sris"] = config.clock_sris
            captured["hvd_inst"] = config.hvd_inst
            return 0

        mock_library.switchtec_fab_port_config_set.side_effect = _capture_set
        fab = FabricManager(device)
        config = FabPortConfig(
            phys_port_id=2,
            port_type=1,
            clock_source=2,
            clock_sris=1,
            hvd_inst=3,
        )
        fab.set_port_config(config)
        assert captured["port_type"] == 1
        assert captured["clock_source"] == 2
        assert captured["clock_sris"] == 1
        assert captured["hvd_inst"] == 3

    def test_set_port_config_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_fab_port_config_set.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        config = FabPortConfig(phys_port_id=0)
        with pytest.raises(SwitchtecError):
            fab.set_port_config(config)


class TestBind:
    def test_bind_calls_lib(self, device, mock_library):
        fab = FabricManager(device)
        request = GfmsBindRequest(
            host_sw_idx=0,
            host_phys_port_id=1,
            host_log_port_id=2,
            ep_number=1,
            ep_pdfid=[0x100],
        )
        fab.bind(request)
        mock_library.switchtec_gfms_bind.assert_called_once()
        call_args = mock_library.switchtec_gfms_bind.call_args[0]
        assert call_args[0] == 0xDEADBEEF

    def test_bind_verifies_struct_fields(self, device, mock_library):
        captured = {}

        def _capture_bind(handle, req_ref):
            req = ctypes.cast(
                req_ref, ctypes.POINTER(SwitchtecGfmsBindReq)
            ).contents
            captured["host_sw_idx"] = req.host_sw_idx
            captured["host_phys_port_id"] = req.host_phys_port_id
            captured["host_log_port_id"] = req.host_log_port_id
            captured["ep_number"] = req.ep_number
            captured["ep_pdfid_0"] = req.ep_pdfid[0]
            captured["ep_pdfid_1"] = req.ep_pdfid[1]
            return 0

        mock_library.switchtec_gfms_bind.side_effect = _capture_bind
        fab = FabricManager(device)
        req = GfmsBindRequest(
            host_sw_idx=1,
            host_phys_port_id=2,
            host_log_port_id=3,
            ep_number=2,
            ep_pdfid=[0x100, 0x200],
        )
        fab.bind(req)
        assert captured["host_sw_idx"] == 1
        assert captured["host_phys_port_id"] == 2
        assert captured["host_log_port_id"] == 3
        assert captured["ep_number"] == 2
        assert captured["ep_pdfid_0"] == 0x100
        assert captured["ep_pdfid_1"] == 0x200

    def test_bind_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_gfms_bind.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        request = GfmsBindRequest(
            host_sw_idx=0,
            host_phys_port_id=1,
            host_log_port_id=2,
            ep_number=1,
            ep_pdfid=[0x100],
        )
        with pytest.raises(SwitchtecError):
            fab.bind(request)


class TestUnbind:
    def test_unbind_calls_lib(self, device, mock_library):
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=0,
            host_phys_port_id=1,
            host_log_port_id=2,
            pdfid=0x100,
            option=0,
        )
        fab.unbind(request)
        mock_library.switchtec_gfms_unbind.assert_called_once()
        call_args = mock_library.switchtec_gfms_unbind.call_args[0]
        assert call_args[0] == 0xDEADBEEF

    def test_unbind_verifies_struct_fields(self, device, mock_library):
        captured = {}

        def _capture_unbind(handle, req_ref):
            req = ctypes.cast(
                req_ref, ctypes.POINTER(SwitchtecGfmsUnbindReq)
            ).contents
            captured["host_sw_idx"] = req.host_sw_idx
            captured["host_phys_port_id"] = req.host_phys_port_id
            captured["host_log_port_id"] = req.host_log_port_id
            captured["pdfid"] = req.pdfid
            captured["option"] = req.option
            return 0

        mock_library.switchtec_gfms_unbind.side_effect = _capture_unbind
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=1,
            host_phys_port_id=5,
            host_log_port_id=3,
            pdfid=0x200,
            option=1,
        )
        fab.unbind(request)
        assert captured["host_sw_idx"] == 1
        assert captured["host_phys_port_id"] == 5
        assert captured["host_log_port_id"] == 3
        assert captured["pdfid"] == 0x200
        assert captured["option"] == 1

    def test_unbind_with_option(self, device, mock_library):
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=1,
            host_phys_port_id=5,
            host_log_port_id=3,
            pdfid=0x100,
            option=1,
        )
        fab.unbind(request)
        mock_library.switchtec_gfms_unbind.assert_called_once()

    def test_unbind_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_gfms_unbind.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=0,
            host_phys_port_id=1,
            host_log_port_id=2,
        )
        with pytest.raises(SwitchtecError):
            fab.unbind(request)


class TestClearGfmsEvents:
    def test_clear_gfms_events(self, device, mock_library):
        fab = FabricManager(device)
        fab.clear_gfms_events()
        mock_library.switchtec_clear_gfms_events.assert_called_once_with(
            0xDEADBEEF,
        )

    def test_clear_gfms_events_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_clear_gfms_events.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError):
            fab.clear_gfms_events()


class TestDeviceFabricProperty:
    def test_device_fabric_returns_fabric_manager(self, device, mock_library):
        fab = device.fabric
        assert isinstance(fab, FabricManager)

    def test_device_fabric_is_cached(self, device, mock_library):
        fab1 = device.fabric
        fab2 = device.fabric
        assert fab1 is fab2


class TestCsrReadAlignmentValidation:
    """PCIe config space reads must be naturally aligned per PCIe Base Spec."""

    def test_8bit_read_any_address(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x1, 0x3, 0x7, 0xFF):
            fab.csr_read(pdfid=0x100, addr=addr, width=8)

    def test_16bit_read_even_address_succeeds(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x2, 0x4, 0xFE):
            fab.csr_read(pdfid=0x100, addr=addr, width=16)

    def test_16bit_read_odd_address_raises(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x1, 0x3, 0x5, 0xFF):
            with pytest.raises(InvalidParameterError, match="16-bit CSR access requires even address"):
                fab.csr_read(pdfid=0x100, addr=addr, width=16)

    def test_32bit_read_aligned_address_succeeds(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x4, 0x8, 0xFC):
            fab.csr_read(pdfid=0x100, addr=addr, width=32)

    def test_32bit_read_unaligned_address_raises(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x1, 0x2, 0x3, 0x5, 0x6, 0x7):
            with pytest.raises(InvalidParameterError, match="32-bit CSR access requires 4-byte aligned"):
                fab.csr_read(pdfid=0x100, addr=addr, width=32)


class TestCsrWriteAlignmentValidation:
    """PCIe config space writes must be naturally aligned per PCIe Base Spec."""

    def test_8bit_write_any_address(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x1, 0x3, 0x7, 0xFF):
            fab.csr_write(pdfid=0x100, addr=addr, value=0x12, width=8)

    def test_16bit_write_even_address_succeeds(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x2, 0x4, 0xFE):
            fab.csr_write(pdfid=0x100, addr=addr, value=0x1234, width=16)

    def test_16bit_write_odd_address_raises(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x1, 0x3, 0x5, 0xFF):
            with pytest.raises(InvalidParameterError, match="16-bit CSR access requires even address"):
                fab.csr_write(pdfid=0x100, addr=addr, value=0x1234, width=16)

    def test_32bit_write_aligned_address_succeeds(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x0, 0x4, 0x8, 0xFC):
            fab.csr_write(pdfid=0x100, addr=addr, value=0x12345678, width=32)

    def test_32bit_write_unaligned_address_raises(self, device, mock_library):
        fab = FabricManager(device)
        for addr in (0x1, 0x2, 0x3, 0x5, 0x6, 0x7):
            with pytest.raises(InvalidParameterError, match="32-bit CSR access requires 4-byte aligned"):
                fab.csr_write(pdfid=0x100, addr=addr, value=0x12345678, width=32)


# ─── CSR Read Tests ──────────────────────────────────────────────────


def _make_csr_read_side_effect(value, ctype_class):
    """Build a side_effect that populates the byref output parameter."""

    def side_effect(handle, pdfid, addr, val_ref):
        ptr = ctypes.cast(val_ref, ctypes.POINTER(ctype_class))
        ptr[0] = value
        return 0

    return side_effect


class TestCsrRead:
    def test_csr_read8_happy_path(self, device, mock_library):
        mock_library.switchtec_ep_csr_read8.side_effect = (
            _make_csr_read_side_effect(0xAB, ctypes.c_uint8)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0x10, width=8)
        mock_library.switchtec_ep_csr_read8.assert_called_once()
        call_args = mock_library.switchtec_ep_csr_read8.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0x100
        assert call_args[2] == 0x10
        assert result == 0xAB

    def test_csr_read16_happy_path(self, device, mock_library):
        mock_library.switchtec_ep_csr_read16.side_effect = (
            _make_csr_read_side_effect(0xBEEF, ctypes.c_uint16)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0x10, width=16)
        mock_library.switchtec_ep_csr_read16.assert_called_once()
        call_args = mock_library.switchtec_ep_csr_read16.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0x100
        assert call_args[2] == 0x10
        assert result == 0xBEEF

    def test_csr_read32_happy_path(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0xDEADBEEF, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0x10, width=32)
        mock_library.switchtec_ep_csr_read32.assert_called_once()
        call_args = mock_library.switchtec_ep_csr_read32.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0x100
        assert call_args[2] == 0x10
        assert result == 0xDEADBEEF

    def test_csr_read_boundary_pdfid_zero(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x42, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0, addr=0x0, width=32)
        call_args = mock_library.switchtec_ep_csr_read32.call_args[0]
        assert call_args[1] == 0
        assert result == 0x42

    def test_csr_read_boundary_pdfid_max(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x42, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0xFFFF, addr=0x0, width=32)
        call_args = mock_library.switchtec_ep_csr_read32.call_args[0]
        assert call_args[1] == 0xFFFF
        assert result == 0x42

    def test_csr_read_boundary_addr_zero(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x1, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0, width=32)
        call_args = mock_library.switchtec_ep_csr_read32.call_args[0]
        assert call_args[2] == 0
        assert result == 0x1

    def test_csr_read_boundary_addr_max_aligned(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x1, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        # 0xFFC is the max 4-byte-aligned address in the 0x000-0xFFF range
        result = fab.csr_read(pdfid=0x100, addr=0xFFC, width=32)
        call_args = mock_library.switchtec_ep_csr_read32.call_args[0]
        assert call_args[2] == 0xFFC
        assert result == 0x1

    def test_csr_read_boundary_addr_max_byte(self, device, mock_library):
        mock_library.switchtec_ep_csr_read8.side_effect = (
            _make_csr_read_side_effect(0xFF, ctypes.c_uint8)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0xFFF, width=8)
        assert result == 0xFF

    def test_csr_read_invalid_pdfid_negative(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="pdfid"):
            fab.csr_read(pdfid=-1, addr=0x10, width=32)

    def test_csr_read_invalid_pdfid_too_large(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="pdfid"):
            fab.csr_read(pdfid=0x10000, addr=0x10, width=32)

    def test_csr_read_invalid_addr_negative(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_read(pdfid=0x100, addr=-1, width=32)

    def test_csr_read_invalid_addr_too_large(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_read(pdfid=0x100, addr=0x1000, width=32)

    def test_csr_read_invalid_width(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError, match="Invalid CSR width"):
            fab.csr_read(pdfid=0x100, addr=0x10, width=64)

    def test_csr_read16_unaligned(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="even address"):
            fab.csr_read(pdfid=0x100, addr=0x11, width=16)

    def test_csr_read32_unaligned(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="4-byte aligned"):
            fab.csr_read(pdfid=0x100, addr=0x11, width=32)

    def test_csr_read_error_return(self, device, mock_library, monkeypatch):
        mock_library.switchtec_ep_csr_read32.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError):
            fab.csr_read(pdfid=0x100, addr=0x10, width=32)


# ─── CSR Write Tests ─────────────────────────────────────────────────


class TestCsrWrite:
    def test_csr_write8_happy_path(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xAB, width=8)
        mock_library.switchtec_ep_csr_write8.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xAB, 0x10,
        )

    def test_csr_write16_happy_path(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xBEEF, width=16)
        mock_library.switchtec_ep_csr_write16.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xBEEF, 0x10,
        )

    def test_csr_write32_happy_path(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xCAFEBABE, width=32)
        mock_library.switchtec_ep_csr_write32.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xCAFEBABE, 0x10,
        )

    def test_csr_write8_boundary_max_value(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xFF, width=8)
        mock_library.switchtec_ep_csr_write8.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xFF, 0x10,
        )

    def test_csr_write16_boundary_max_value(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xFFFF, width=16)
        mock_library.switchtec_ep_csr_write16.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xFFFF, 0x10,
        )

    def test_csr_write32_boundary_max_value(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0xFFFFFFFF, width=32)
        mock_library.switchtec_ep_csr_write32.assert_called_once_with(
            0xDEADBEEF, 0x100, 0xFFFFFFFF, 0x10,
        )

    def test_csr_write_zero_value(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x10, value=0, width=8)
        mock_library.switchtec_ep_csr_write8.assert_called_once_with(
            0xDEADBEEF, 0x100, 0, 0x10,
        )

    def test_csr_write8_value_overflow(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="exceeds"):
            fab.csr_write(pdfid=0x100, addr=0x10, value=0x100, width=8)

    def test_csr_write16_value_overflow(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="exceeds"):
            fab.csr_write(pdfid=0x100, addr=0x10, value=0x10000, width=16)

    def test_csr_write32_value_overflow(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="exceeds"):
            fab.csr_write(pdfid=0x100, addr=0x10, value=0x100000000, width=32)

    def test_csr_write_invalid_pdfid_negative(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="pdfid"):
            fab.csr_write(pdfid=-1, addr=0x10, value=0, width=32)

    def test_csr_write_invalid_pdfid_too_large(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="pdfid"):
            fab.csr_write(pdfid=0x10000, addr=0x10, value=0, width=32)

    def test_csr_write_invalid_addr_negative(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_write(pdfid=0x100, addr=-1, value=0, width=32)

    def test_csr_write_invalid_addr_too_large(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_write(pdfid=0x100, addr=0x1000, value=0, width=32)

    def test_csr_write_invalid_width(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises((SwitchtecError, InvalidParameterError)):
            fab.csr_write(pdfid=0x100, addr=0x10, value=0, width=64)

    def test_csr_write16_unaligned(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="even address"):
            fab.csr_write(pdfid=0x100, addr=0x11, value=0, width=16)

    def test_csr_write32_unaligned(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="4-byte aligned"):
            fab.csr_write(pdfid=0x100, addr=0x03, value=0, width=32)

    def test_csr_write_error_return(self, device, mock_library, monkeypatch):
        mock_library.switchtec_ep_csr_write32.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        with pytest.raises(SwitchtecError):
            fab.csr_write(pdfid=0x100, addr=0x10, value=0x1, width=32)


# ─── Extended Config Space Tests ────────────────────────────────────


class TestCsrReadExtended:
    """Tests for extended config space (0x000-0xFFFF) via extended=True."""

    def test_extended_read_accepts_addr_above_0xfff(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x42, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0x1000, width=32, extended=True)
        assert result == 0x42

    def test_extended_read_accepts_max_addr(self, device, mock_library):
        mock_library.switchtec_ep_csr_read32.side_effect = (
            _make_csr_read_side_effect(0x99, ctypes.c_uint32)
        )
        fab = FabricManager(device)
        result = fab.csr_read(pdfid=0x100, addr=0xFFFC, width=32, extended=True)
        assert result == 0x99

    def test_standard_read_still_rejects_above_0xfff(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_read(pdfid=0x100, addr=0x1000, width=32)

    def test_standard_read_still_rejects_above_0xfff_explicit_false(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_read(pdfid=0x100, addr=0x1000, width=32, extended=False)

    def test_extended_read_rejects_above_0xffff(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_read(pdfid=0x100, addr=0x10000, width=32, extended=True)


class TestCsrWriteExtended:
    """Tests for extended config space writes via extended=True."""

    def test_extended_write_accepts_addr_above_0xfff(self, device, mock_library):
        fab = FabricManager(device)
        fab.csr_write(pdfid=0x100, addr=0x1000, value=0x42, width=32, extended=True)
        mock_library.switchtec_ep_csr_write32.assert_called_once()

    def test_standard_write_still_rejects_above_0xfff(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_write(pdfid=0x100, addr=0x1000, value=0x42, width=32)

    def test_extended_write_rejects_above_0xffff(self, device, mock_library):
        fab = FabricManager(device)
        with pytest.raises(InvalidParameterError, match="addr"):
            fab.csr_write(pdfid=0x100, addr=0x10000, value=0x42, width=32, extended=True)
