"""Tests for ctypes structure definitions."""

from __future__ import annotations

import ctypes

from serialcables_switchtec.bindings.types import (
    Range,
    SwitchtecBwCntrDir,
    SwitchtecBwCntrRes,
    SwitchtecDeviceInfo,
    SwitchtecDiagCrossHair,
    SwitchtecDiagLtssmLog,
    SwitchtecFwImageInfo,
    SwitchtecPortEqCoeff,
    SwitchtecPortEqCursor,
    SwitchtecPortEqTable,
    SwitchtecPortEqTableStep,
    SwitchtecPortEqTxFslf,
    SwitchtecPortId,
    SwitchtecRcvrExt,
    SwitchtecRcvrObj,
    SwitchtecStatus,
)


class TestRange:
    def test_fields(self) -> None:
        r = Range(start=-64, end=64, step=2)
        assert r.start == -64
        assert r.end == 64
        assert r.step == 2


class TestSwitchtecPortId:
    def test_fields(self) -> None:
        pid = SwitchtecPortId()
        pid.partition = 0
        pid.stack = 1
        pid.upstream = 1
        pid.phys_id = 8
        assert pid.partition == 0
        assert pid.phys_id == 8


class TestSwitchtecDeviceInfo:
    def test_name_field(self) -> None:
        info = SwitchtecDeviceInfo()
        info.name = b"switchtec0"
        assert info.name == b"switchtec0"


class TestSwitchtecRcvrObj:
    def test_dynamic_dfe_array(self) -> None:
        obj = SwitchtecRcvrObj()
        obj.port_id = 5
        obj.dynamic_dfe[0] = 1
        obj.dynamic_dfe[6] = 7
        assert obj.dynamic_dfe[0] == 1
        assert obj.dynamic_dfe[6] == 7


class TestSwitchtecDiagLtssmLog:
    def test_fields(self) -> None:
        log = SwitchtecDiagLtssmLog()
        log.timestamp = 12345
        log.link_rate = 32.0
        log.link_state = 0x11
        assert log.timestamp == 12345


class TestSwitchtecStatus:
    def test_basic_fields(self) -> None:
        status = SwitchtecStatus()
        status.cfg_lnk_width = 16
        status.neg_lnk_width = 8
        status.link_up = 1
        status.link_rate = 4
        status.ltssm = 0x0103
        status.first_act_lane = 0
        assert status.cfg_lnk_width == 16
        assert status.neg_lnk_width == 8
        assert status.link_up == 1
        assert status.link_rate == 4
        assert status.ltssm == 0x0103
        assert status.first_act_lane == 0

    def test_embedded_port_id(self) -> None:
        status = SwitchtecStatus()
        status.port.partition = 2
        status.port.stack = 3
        status.port.phys_id = 12
        assert status.port.partition == 2
        assert status.port.stack == 3
        assert status.port.phys_id == 12

    def test_vendor_device_id(self) -> None:
        status = SwitchtecStatus()
        status.vendor_id = 0x11F8
        status.device_id = 0x8264
        assert status.vendor_id == 0x11F8
        assert status.device_id == 0x8264

    def test_acs_ctrl(self) -> None:
        status = SwitchtecStatus()
        status.acs_ctrl = 0x0F
        assert status.acs_ctrl == 0x0F

    def test_lane_reversal(self) -> None:
        status = SwitchtecStatus()
        status.lane_reversal = 1
        assert status.lane_reversal == 1


class TestSwitchtecBwCntrDir:
    def test_fields(self) -> None:
        bw = SwitchtecBwCntrDir()
        bw.posted = 1000
        bw.comp = 2000
        bw.nonposted = 500
        assert bw.posted == 1000
        assert bw.comp == 2000
        assert bw.nonposted == 500

    def test_zero_values(self) -> None:
        bw = SwitchtecBwCntrDir()
        assert bw.posted == 0
        assert bw.comp == 0
        assert bw.nonposted == 0

    def test_large_values(self) -> None:
        bw = SwitchtecBwCntrDir()
        bw.posted = 0xFFFFFFFFFFFFFFFF
        assert bw.posted == 0xFFFFFFFFFFFFFFFF


class TestSwitchtecBwCntrRes:
    def test_time_us(self) -> None:
        res = SwitchtecBwCntrRes()
        res.time_us = 1_000_000
        assert res.time_us == 1_000_000

    def test_egress_ingress(self) -> None:
        res = SwitchtecBwCntrRes()
        res.egress.posted = 100
        res.egress.comp = 200
        res.egress.nonposted = 50
        res.ingress.posted = 150
        res.ingress.comp = 250
        res.ingress.nonposted = 75
        assert res.egress.posted == 100
        assert res.egress.comp == 200
        assert res.egress.nonposted == 50
        assert res.ingress.posted == 150
        assert res.ingress.comp == 250
        assert res.ingress.nonposted == 75

    def test_default_zero(self) -> None:
        res = SwitchtecBwCntrRes()
        assert res.time_us == 0
        assert res.egress.posted == 0
        assert res.ingress.nonposted == 0


class TestSwitchtecRcvrExt:
    def test_fields(self) -> None:
        ext = SwitchtecRcvrExt()
        ext.ctle2_rx_mode = 3
        ext.dtclk_5 = 1
        ext.dtclk_8_6 = 5
        ext.dtclk_9 = 0
        assert ext.ctle2_rx_mode == 3
        assert ext.dtclk_5 == 1
        assert ext.dtclk_8_6 == 5
        assert ext.dtclk_9 == 0

    def test_default_zero(self) -> None:
        ext = SwitchtecRcvrExt()
        assert ext.ctle2_rx_mode == 0
        assert ext.dtclk_5 == 0
        assert ext.dtclk_8_6 == 0
        assert ext.dtclk_9 == 0


class TestSwitchtecPortEqCoeff:
    def test_lane_cnt(self) -> None:
        coeff = SwitchtecPortEqCoeff()
        coeff.lane_cnt = 16
        assert coeff.lane_cnt == 16

    def test_cursors_array(self) -> None:
        coeff = SwitchtecPortEqCoeff()
        coeff.cursors[0].pre = 10
        coeff.cursors[0].post = 20
        coeff.cursors[15].pre = 5
        coeff.cursors[15].post = 15
        assert coeff.cursors[0].pre == 10
        assert coeff.cursors[0].post == 20
        assert coeff.cursors[15].pre == 5
        assert coeff.cursors[15].post == 15

    def test_cursors_array_length(self) -> None:
        coeff = SwitchtecPortEqCoeff()
        assert len(coeff.cursors) == 16

    def test_reserved_field(self) -> None:
        coeff = SwitchtecPortEqCoeff()
        assert len(coeff.reserved) == 3


class TestSwitchtecPortEqTable:
    def test_lane_id_and_step_cnt(self) -> None:
        table = SwitchtecPortEqTable()
        table.lane_id = 4
        table.step_cnt = 10
        assert table.lane_id == 4
        assert table.step_cnt == 10

    def test_steps_array(self) -> None:
        table = SwitchtecPortEqTable()
        table.steps[0].pre_cursor = 3
        table.steps[0].post_cursor = 7
        table.steps[0].fom = 42
        assert table.steps[0].pre_cursor == 3
        assert table.steps[0].post_cursor == 7
        assert table.steps[0].fom == 42

    def test_steps_array_length(self) -> None:
        table = SwitchtecPortEqTable()
        assert len(table.steps) == 126

    def test_step_all_fields(self) -> None:
        step = SwitchtecPortEqTableStep()
        step.pre_cursor = 1
        step.post_cursor = 2
        step.fom = 3
        step.pre_cursor_up = 4
        step.post_cursor_up = 5
        step.error_status = 6
        step.active_status = 7
        step.speed = 8
        assert step.pre_cursor == 1
        assert step.post_cursor == 2
        assert step.fom == 3
        assert step.pre_cursor_up == 4
        assert step.post_cursor_up == 5
        assert step.error_status == 6
        assert step.active_status == 7
        assert step.speed == 8


class TestSwitchtecPortEqTxFslf:
    def test_fields(self) -> None:
        fslf = SwitchtecPortEqTxFslf()
        fslf.fs = 63
        fslf.lf = 15
        assert fslf.fs == 63
        assert fslf.lf == 15

    def test_default_zero(self) -> None:
        fslf = SwitchtecPortEqTxFslf()
        assert fslf.fs == 0
        assert fslf.lf == 0


class TestSwitchtecDiagCrossHair:
    def test_state_and_lane(self) -> None:
        ch = SwitchtecDiagCrossHair()
        ch.state = 21  # DONE
        ch.lane_id = 3
        assert ch.state == 21
        assert ch.lane_id == 3

    def test_eye_limit_fields(self) -> None:
        ch = SwitchtecDiagCrossHair()
        ch.eye_left_lim = -10
        ch.eye_right_lim = 10
        ch.eye_bot_left_lim = -5
        ch.eye_bot_right_lim = 5
        ch.eye_top_left_lim = -8
        ch.eye_top_right_lim = 8
        assert ch.eye_left_lim == -10
        assert ch.eye_right_lim == 10
        assert ch.eye_bot_left_lim == -5
        assert ch.eye_bot_right_lim == 5
        assert ch.eye_top_left_lim == -8
        assert ch.eye_top_right_lim == 8

    def test_default_zero(self) -> None:
        ch = SwitchtecDiagCrossHair()
        assert ch.state == 0
        assert ch.lane_id == 0
        assert ch.eye_left_lim == 0


class TestSwitchtecFwImageInfo:
    def test_basic_fields(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.gen = 1  # GEN4
        fw.part_id = 0x1234
        fw.type = 3  # IMG
        assert fw.gen == 1
        assert fw.part_id == 0x1234
        assert fw.type == 3

    def test_version_field(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.version = b"4.40"
        assert fw.version == b"4.40"

    def test_address_and_length_fields(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.part_addr = 0x10000
        fw.part_len = 0x80000
        fw.part_body_offset = 0x100
        fw.image_len = 0x40000
        assert fw.part_addr == 0x10000
        assert fw.part_len == 0x80000
        assert fw.part_body_offset == 0x100
        assert fw.image_len == 0x40000

    def test_image_crc(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.image_crc = 0xDEADBEEF
        assert fw.image_crc == 0xDEADBEEF

    def test_boolean_fields(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.valid = True
        fw.active = True
        fw.running = False
        fw.read_only = True
        fw.signed_image = False
        assert fw.valid is True
        assert fw.active is True
        assert fw.running is False
        assert fw.read_only is True
        assert fw.signed_image is False

    def test_secure_version_and_redundant(self) -> None:
        fw = SwitchtecFwImageInfo()
        fw.secure_version = 42
        fw.redundant = 1
        assert fw.secure_version == 42
        assert fw.redundant == 1

    def test_default_zero(self) -> None:
        fw = SwitchtecFwImageInfo()
        assert fw.gen == 0
        assert fw.part_id == 0
        assert fw.image_crc == 0
        assert fw.secure_version == 0


class TestSwitchtecPortEqCursor:
    def test_fields(self) -> None:
        cursor = SwitchtecPortEqCursor()
        cursor.pre = 10
        cursor.post = 20
        assert cursor.pre == 10
        assert cursor.post == 20

    def test_default_zero(self) -> None:
        cursor = SwitchtecPortEqCursor()
        assert cursor.pre == 0
        assert cursor.post == 0
