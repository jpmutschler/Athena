"""Tests for ctypes structure definitions."""

from __future__ import annotations

import ctypes

from serialcables_switchtec.bindings.types import (
    Range,
    SwitchtecDeviceInfo,
    SwitchtecDiagCrossHair,
    SwitchtecDiagLtssmLog,
    SwitchtecPortEqCoeff,
    SwitchtecPortId,
    SwitchtecRcvrObj,
    SwitchtecStatus,
)


class TestRange:
    def test_fields(self):
        r = Range(start=-64, end=64, step=2)
        assert r.start == -64
        assert r.end == 64
        assert r.step == 2


class TestSwitchtecPortId:
    def test_fields(self):
        pid = SwitchtecPortId()
        pid.partition = 0
        pid.stack = 1
        pid.upstream = 1
        pid.phys_id = 8
        assert pid.partition == 0
        assert pid.phys_id == 8


class TestSwitchtecDeviceInfo:
    def test_name_field(self):
        info = SwitchtecDeviceInfo()
        info.name = b"switchtec0"
        assert info.name == b"switchtec0"


class TestSwitchtecRcvrObj:
    def test_dynamic_dfe_array(self):
        obj = SwitchtecRcvrObj()
        obj.port_id = 5
        obj.dynamic_dfe[0] = 1
        obj.dynamic_dfe[6] = 7
        assert obj.dynamic_dfe[0] == 1
        assert obj.dynamic_dfe[6] == 7


class TestSwitchtecDiagLtssmLog:
    def test_fields(self):
        log = SwitchtecDiagLtssmLog()
        log.timestamp = 12345
        log.link_rate = 32.0
        log.link_state = 0x11
        assert log.timestamp == 12345
