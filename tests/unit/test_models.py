"""Tests for Pydantic models."""

from __future__ import annotations

import pytest

from serialcables_switchtec.models.device import DeviceInfo, DeviceSummary, PortId, PortStatus
from serialcables_switchtec.models.diagnostics import (
    CrossHairResult,
    EqCursor,
    LtssmLogEntry,
    PatternMonResult,
    PortEqCoeff,
    ReceiverObject,
)
from serialcables_switchtec.models.performance import BwCounterDirection, BwCounterResult


class TestDeviceInfo:
    def test_creation(self):
        info = DeviceInfo(
            name="switchtec0",
            description="Test device",
            pci_dev="0000:01:00.0",
            product_id="PSX-48",
            product_rev="A0",
            fw_version="4.40",
            path="/dev/switchtec0",
        )
        assert info.name == "switchtec0"
        assert info.fw_version == "4.40"

    def test_frozen(self):
        info = DeviceInfo(
            name="test", description="", pci_dev="",
            product_id="", product_rev="", fw_version="", path="",
        )
        with pytest.raises(Exception):
            info.name = "new_name"


class TestPortId:
    def test_creation(self):
        port = PortId(
            partition=0, stack=1, upstream=True,
            stk_id=0, phys_id=8, log_id=0,
        )
        assert port.upstream is True
        assert port.phys_id == 8


class TestPortStatus:
    def test_link_up(self):
        port_id = PortId(
            partition=0, stack=0, upstream=False,
            stk_id=0, phys_id=0, log_id=0,
        )
        status = PortStatus(
            port=port_id, cfg_lnk_width=16, neg_lnk_width=16,
            link_up=True, link_rate=6, ltssm=0x11,
            ltssm_str="L0 (ACTIVE)",
            lane_reversal=0, lane_reversal_str="None",
            first_act_lane=0,
        )
        assert status.link_up is True
        assert status.link_rate == 6


class TestDeviceSummary:
    def test_creation(self):
        summary = DeviceSummary(
            name="switchtec0", device_id=0x8264,
            generation="GEN6", variant="PFX",
            boot_phase="Main Firmware", partition=0,
            fw_version="4.40", die_temperature=42.5,
            port_count=20,
        )
        assert summary.generation == "GEN6"
        assert summary.die_temperature == 42.5


class TestLtssmLogEntry:
    def test_creation(self):
        entry = LtssmLogEntry(
            timestamp=12345, link_rate=32.0, link_state=0x11,
            link_state_str="L0 (ACTIVE)", link_width=16,
            tx_minor_state=0, rx_minor_state=0,
        )
        assert entry.link_state_str == "L0 (ACTIVE)"


class TestReceiverObject:
    def test_dynamic_dfe(self):
        rcvr = ReceiverObject(
            port_id=0, lane_id=0, ctle=3,
            target_amplitude=50, speculative_dfe=10,
            dynamic_dfe=[1, 2, 3, 4, 5, 6, 7],
        )
        assert len(rcvr.dynamic_dfe) == 7


class TestBwCounterResult:
    def test_total(self):
        direction = BwCounterDirection(posted=100, comp=200, nonposted=50)
        assert direction.total == 350

    def test_result(self):
        result = BwCounterResult(
            time_us=1000000,
            egress=BwCounterDirection(posted=100, comp=200, nonposted=50),
            ingress=BwCounterDirection(posted=150, comp=250, nonposted=75),
        )
        assert result.egress.total == 350
        assert result.ingress.total == 475
