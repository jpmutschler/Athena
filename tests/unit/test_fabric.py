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
from serialcables_switchtec.exceptions import SwitchtecError
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
            hot_reset_flag=FabHotResetFlag.FUNDAMENTAL,
        )
        mock_library.switchtec_port_control.assert_called_once_with(
            0xDEADBEEF,
            int(FabPortControlType.HOT_RESET),
            2,
            int(FabHotResetFlag.FUNDAMENTAL),
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
        assert result.link_width == 0

    def test_get_port_config_with_filled_struct(self, device, mock_library):
        def _fill_port_config(handle, port_id, config_ref):
            config = ctypes.cast(
                config_ref, ctypes.POINTER(SwitchtecFabPortConfig)
            ).contents
            config.port_type = 1
            config.clock_source = 2
            config.clock_sris = 3
            config.hvd_inst = 4
            config.link_width = 8
            return 0

        mock_library.switchtec_fab_port_config_get.side_effect = _fill_port_config
        fab = FabricManager(device)
        result = fab.get_port_config(phys_port_id=5)
        assert result.phys_port_id == 5
        assert result.port_type == 1
        assert result.clock_source == 2
        assert result.clock_sris == 3
        assert result.hvd_inst == 4
        assert result.link_width == 8

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
            captured["link_width"] = config.link_width
            return 0

        mock_library.switchtec_fab_port_config_set.side_effect = _capture_set
        fab = FabricManager(device)
        config = FabPortConfig(
            phys_port_id=2,
            port_type=1,
            clock_source=2,
            clock_sris=1,
            hvd_inst=3,
            link_width=16,
        )
        fab.set_port_config(config)
        assert captured["port_type"] == 1
        assert captured["clock_source"] == 2
        assert captured["clock_sris"] == 1
        assert captured["hvd_inst"] == 3
        assert captured["link_width"] == 16

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
            ep_sw_idx=3,
            ep_phys_port_id=4,
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
            captured["ep_sw_idx"] = req.ep_sw_idx
            captured["ep_phys_port_id"] = req.ep_phys_port_id
            return 0

        mock_library.switchtec_gfms_bind.side_effect = _capture_bind
        fab = FabricManager(device)
        req = GfmsBindRequest(
            host_sw_idx=1,
            host_phys_port_id=2,
            host_log_port_id=3,
            ep_sw_idx=4,
            ep_phys_port_id=5,
        )
        fab.bind(req)
        assert captured["host_sw_idx"] == 1
        assert captured["host_phys_port_id"] == 2
        assert captured["host_log_port_id"] == 3
        assert captured["ep_sw_idx"] == 4
        assert captured["ep_phys_port_id"] == 5

    def test_bind_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_gfms_bind.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        fab = FabricManager(device)
        request = GfmsBindRequest(
            host_sw_idx=0,
            host_phys_port_id=1,
            host_log_port_id=2,
            ep_sw_idx=3,
            ep_phys_port_id=4,
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
            opt=0,
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
            captured["opt"] = req.opt
            return 0

        mock_library.switchtec_gfms_unbind.side_effect = _capture_unbind
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=1,
            host_phys_port_id=5,
            host_log_port_id=3,
            opt=1,
        )
        fab.unbind(request)
        assert captured["host_sw_idx"] == 1
        assert captured["host_phys_port_id"] == 5
        assert captured["host_log_port_id"] == 3
        assert captured["opt"] == 1

    def test_unbind_with_option(self, device, mock_library):
        fab = FabricManager(device)
        request = GfmsUnbindRequest(
            host_sw_idx=1,
            host_phys_port_id=5,
            host_log_port_id=3,
            opt=1,
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
