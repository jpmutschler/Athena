"""Tests for UI state module: device connection, caching, scan."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.device import (
    DeviceInfo,
    DeviceSummary,
    PortId,
    PortStatus,
)
from serialcables_switchtec.ui import state


@pytest.fixture(autouse=True)
def _reset_ui_state():
    """Reset global state between tests."""
    state._active_device = None
    state._active_path = ""
    state._cached_summary = None
    yield
    state._active_device = None
    state._active_path = ""
    state._cached_summary = None


def _make_summary(**overrides) -> DeviceSummary:
    defaults = {
        "name": "PSX48XG5",
        "device_id": 0x5A00,
        "generation": "Gen5",
        "variant": "PSX",
        "boot_phase": "BL2",
        "partition": 0,
        "fw_version": "4.70B058",
        "die_temperature": 42.5,
        "port_count": 48,
    }
    defaults.update(overrides)
    return DeviceSummary(**defaults)


def _make_port_status(phys_id: int = 0, link_up: bool = True) -> PortStatus:
    return PortStatus(
        port=PortId(
            partition=0, stack=0, upstream=True,
            stk_id=0, phys_id=phys_id, log_id=0,
        ),
        cfg_lnk_width=16,
        neg_lnk_width=16,
        link_up=link_up,
        link_rate=5,
        ltssm=0,
        ltssm_str="L0",
        lane_reversal=0,
        lane_reversal_str="none",
        first_act_lane=0,
    )


def _make_mock_device(summary=None, ports=None):
    dev = MagicMock()
    dev.get_summary.return_value = summary or _make_summary()
    dev.get_status.return_value = ports or [_make_port_status()]
    dev.close.return_value = None
    return dev


# ── connect_device ───────────────────────────────────────────────────────


class TestConnectDevice:
    """connect_device() tests."""

    def test_connect_sets_active_device(self):
        mock_dev = _make_mock_device()
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=mock_dev,
        ):
            result = state.connect_device("/dev/switchtec0")
        assert result.name == "PSX48XG5"
        assert state.get_active_device() is mock_dev

    def test_connect_sets_active_path(self):
        mock_dev = _make_mock_device()
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=mock_dev,
        ):
            state.connect_device("/dev/switchtec0")
        assert state.get_active_path() == "/dev/switchtec0"

    def test_connect_caches_summary(self):
        summary = _make_summary(die_temperature=55.0)
        mock_dev = _make_mock_device(summary=summary)
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=mock_dev,
        ):
            state.connect_device("/dev/switchtec0")
        assert state.get_summary().die_temperature == 55.0

    def test_connect_closes_old_device(self):
        old_dev = _make_mock_device()
        state._active_device = old_dev

        new_dev = _make_mock_device()
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=new_dev,
        ):
            state.connect_device("/dev/switchtec1")
        old_dev.close.assert_called_once()

    def test_connect_handles_old_close_failure(self):
        old_dev = _make_mock_device()
        old_dev.close.side_effect = RuntimeError("close failed")
        state._active_device = old_dev

        new_dev = _make_mock_device()
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=new_dev,
        ):
            state.connect_device("/dev/switchtec1")
        assert state.get_active_device() is new_dev

    def test_connect_raises_on_open_failure(self):
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            side_effect=SwitchtecError("open failed"),
        ):
            with pytest.raises(SwitchtecError):
                state.connect_device("/dev/switchtec0")

    def test_connect_closes_on_summary_failure(self):
        mock_dev = MagicMock()
        mock_dev.get_summary.side_effect = RuntimeError("summary failed")
        mock_dev.close.return_value = None
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.open",
            return_value=mock_dev,
        ):
            with pytest.raises(RuntimeError):
                state.connect_device("/dev/switchtec0")
        mock_dev.close.assert_called_once()


# ── disconnect_device ────────────────────────────────────────────────────


class TestDisconnectDevice:
    """disconnect_device() tests."""

    def test_disconnect_clears_device(self):
        state._active_device = _make_mock_device()
        state.disconnect_device()
        assert state.get_active_device() is None

    def test_disconnect_clears_path(self):
        state._active_path = "/dev/switchtec0"
        state._active_device = _make_mock_device()
        state.disconnect_device()
        assert state.get_active_path() == ""

    def test_disconnect_clears_summary(self):
        state._cached_summary = _make_summary()
        state._active_device = _make_mock_device()
        state.disconnect_device()
        assert state.get_summary() is None

    def test_disconnect_closes_device(self):
        mock_dev = _make_mock_device()
        state._active_device = mock_dev
        state.disconnect_device()
        mock_dev.close.assert_called_once()

    def test_disconnect_handles_close_failure(self):
        mock_dev = _make_mock_device()
        mock_dev.close.side_effect = RuntimeError("close failed")
        state._active_device = mock_dev
        state.disconnect_device()
        assert state.get_active_device() is None

    def test_disconnect_noop_when_not_connected(self):
        state.disconnect_device()
        assert state.get_active_device() is None


# ── get_active_device / is_connected ─────────────────────────────────────


class TestGetActiveDevice:
    """get_active_device() and is_connected() tests."""

    def test_returns_none_initially(self):
        assert state.get_active_device() is None

    def test_returns_device_after_set(self):
        dev = _make_mock_device()
        state._active_device = dev
        assert state.get_active_device() is dev

    def test_is_connected_false_initially(self):
        assert state.is_connected() is False

    def test_is_connected_true_after_set(self):
        state._active_device = _make_mock_device()
        assert state.is_connected() is True


# ── get_summary / refresh_summary ────────────────────────────────────────


class TestSummary:
    """get_summary() and refresh_summary() tests."""

    def test_get_summary_none_initially(self):
        assert state.get_summary() is None

    def test_get_summary_returns_cached(self):
        summary = _make_summary()
        state._cached_summary = summary
        assert state.get_summary() is summary

    def test_refresh_summary_updates_cache(self):
        new_summary = _make_summary(die_temperature=60.0)
        mock_dev = _make_mock_device(summary=new_summary)
        state._active_device = mock_dev
        result = state.refresh_summary()
        assert result.die_temperature == 60.0
        assert state.get_summary().die_temperature == 60.0

    def test_refresh_summary_none_when_disconnected(self):
        assert state.refresh_summary() is None

    def test_refresh_summary_returns_none_on_error(self):
        mock_dev = MagicMock()
        mock_dev.get_summary.side_effect = SwitchtecError("hw error")
        state._active_device = mock_dev
        assert state.refresh_summary() is None


# ── get_port_status ──────────────────────────────────────────────────────


class TestGetPortStatus:
    """get_port_status() tests."""

    def test_returns_empty_when_disconnected(self):
        assert state.get_port_status() == []

    def test_returns_ports(self):
        ports = [_make_port_status(0), _make_port_status(4)]
        mock_dev = _make_mock_device(ports=ports)
        state._active_device = mock_dev
        result = state.get_port_status()
        assert len(result) == 2
        assert result[0].port.phys_id == 0
        assert result[1].port.phys_id == 4

    def test_returns_empty_on_error(self):
        mock_dev = MagicMock()
        mock_dev.get_status.side_effect = SwitchtecError("hw error")
        state._active_device = mock_dev
        assert state.get_port_status() == []


# ── scan_devices ─────────────────────────────────────────────────────────


class TestScanDevices:
    """scan_devices() tests."""

    def test_scan_returns_devices(self):
        devices = [
            DeviceInfo(
                name="PSX48XG5", description="Gen5 Switch",
                pci_dev="0000:03:00.0", product_id="5A00",
                product_rev="A0", fw_version="4.70", path="/dev/switchtec0",
            ),
        ]
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.list_devices",
            return_value=devices,
        ):
            result = state.scan_devices()
        assert len(result) == 1
        assert result[0].name == "PSX48XG5"

    def test_scan_returns_empty_on_error(self):
        with patch(
            "serialcables_switchtec.core.device.SwitchtecDevice.list_devices",
            side_effect=SwitchtecError("scan failed"),
        ):
            result = state.scan_devices()
        assert result == []
