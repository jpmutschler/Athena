"""Tests for DiagnosticsManager."""

from __future__ import annotations

import ctypes
from unittest.mock import ANY

import pytest

from serialcables_switchtec.bindings.constants import (
    DiagCrossHairState,
    DiagEnd,
    DiagLink,
    DiagLtssmSpeed,
    DiagPattern,
    DiagPatternLinkRate,
)
from serialcables_switchtec.core.diagnostics import DiagnosticsManager
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.diagnostics import (
    CrossHairResult,
    EyeData,
    LoopbackStatus,
    LtssmLogEntry,
    PatternMonResult,
    PortEqCoeff,
    PortEqTable,
    PortEqTxFslf,
    ReceiverExt,
    ReceiverObject,
)


class TestDiagnosticsManagerEyeCancel:
    def test_eye_cancel(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_cancel()
        mock_library.switchtec_diag_eye_cancel.assert_called_once_with(
            0xDEADBEEF
        )


class TestDiagnosticsManagerEyeSetMode:
    def test_eye_set_mode(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_set_mode(mode=0)
        mock_library.switchtec_diag_eye_set_mode.assert_called_once_with(
            0xDEADBEEF, 0
        )

    def test_eye_set_mode_ratio(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_set_mode(mode=1)
        mock_library.switchtec_diag_eye_set_mode.assert_called_once_with(
            0xDEADBEEF, 1
        )


class TestDiagnosticsManagerEyeStart:
    def test_eye_start_with_defaults(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_start(lane_mask=[0x1, 0x0, 0x0, 0x0])
        mock_library.switchtec_diag_eye_start.assert_called_once()
        call_args = mock_library.switchtec_diag_eye_start.call_args[0]
        assert call_args[0] == 0xDEADBEEF

    def test_eye_start_with_custom_ranges(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_start(
            lane_mask=[0xFF, 0x00, 0x00, 0x00],
            x_start=-32,
            x_end=32,
            x_step=2,
            y_start=-128,
            y_end=128,
            y_step=4,
            step_interval=20,
            capture_depth=100,
        )
        mock_library.switchtec_diag_eye_start.assert_called_once()

    def test_eye_start_with_all_params(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_start(
            lane_mask=[0x01],
            x_start=-10,
            x_end=10,
            x_step=1,
            y_start=-50,
            y_end=50,
            y_step=1,
            step_interval=5,
            capture_depth=10,
            sar_sel=1,
            intleav_sel=2,
            hstep=3,
            data_mode=1,
            eye_mode=1,
            refclk=1,
            vstep=2,
        )
        mock_library.switchtec_diag_eye_start.assert_called_once()

    def test_eye_start_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_eye_start.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.eye_start(lane_mask=[0x01])


class TestDiagnosticsManagerEyeFetch:
    def test_eye_fetch_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.eye_fetch(pixel_count=10)
        mock_library.switchtec_diag_eye_fetch.assert_called_once()
        assert isinstance(result, EyeData)

    def test_eye_fetch_returns_eye_data(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.eye_fetch(pixel_count=5)
        assert isinstance(result, EyeData)
        assert len(result.pixels) == 5
        # Mock does not fill pixels, so they default to 0.0
        assert all(p == 0.0 for p in result.pixels)
        assert result.lane_id == 0

    def test_eye_fetch_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_eye_fetch.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.eye_fetch(pixel_count=10)


class TestDiagnosticsManagerEyeRead:
    def test_eye_read_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        num_phases, ber_data = diag.eye_read(lane_id=0, bin_idx=1)
        mock_library.switchtec_diag_eye_read.assert_called_once()
        call_args = mock_library.switchtec_diag_eye_read.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0
        assert call_args[2] == 1

    def test_eye_read_returns_tuple(self, device, mock_library):
        diag = DiagnosticsManager(device)
        num_phases, ber_data = diag.eye_read(lane_id=2, bin_idx=0)
        # Mock does not set num_phases, so it defaults to 0
        assert num_phases == 0
        assert ber_data == []

    def test_eye_read_custom_max_phases(self, device, mock_library):
        diag = DiagnosticsManager(device)
        num_phases, ber_data = diag.eye_read(
            lane_id=0, bin_idx=0, max_phases=120
        )
        assert num_phases == 0
        assert ber_data == []

    def test_eye_read_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_eye_read.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.eye_read(lane_id=0, bin_idx=0)


class TestDiagnosticsManagerLtssm:
    def test_ltssm_clear(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.ltssm_clear(port_id=5)
        mock_library.switchtec_diag_ltssm_clear.assert_called_once_with(
            0xDEADBEEF, 5
        )

    def test_ltssm_log_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.ltssm_log(port_id=3)
        mock_library.switchtec_diag_ltssm_log.assert_called_once()
        call_args = mock_library.switchtec_diag_ltssm_log.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 3

    def test_ltssm_log_returns_empty_list_by_default(
        self, device, mock_library
    ):
        # The mock returns 0 and does not modify log_count,
        # but log_count is initialized to max_entries. The mock does not
        # write a new value, so it stays at 64. We need to verify the
        # function was called; the actual returned list depends on
        # log_count.value which we cannot control without a side_effect.
        # With the default mock, log_count stays at the initialized value.
        diag = DiagnosticsManager(device)
        result = diag.ltssm_log(port_id=0, max_entries=0)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_ltssm_log_custom_max_entries(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.ltssm_log(port_id=1, max_entries=0)
        assert isinstance(result, list)

    def test_ltssm_log_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_ltssm_log.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.ltssm_log(port_id=0)


class TestDiagnosticsManagerLoopback:
    def test_loopback_set_defaults(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.loopback_set(port_id=2)
        mock_library.switchtec_diag_loopback_set.assert_called_once_with(
            0xDEADBEEF, 2, 1, 0, 0, 0, 0, int(DiagLtssmSpeed.GEN4)
        )

    def test_loopback_set_all_options(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.loopback_set(
            port_id=4,
            enable=False,
            enable_parallel=True,
            enable_external=True,
            enable_ltssm=True,
            enable_pipe=True,
            ltssm_speed=DiagLtssmSpeed.GEN5,
        )
        mock_library.switchtec_diag_loopback_set.assert_called_once_with(
            0xDEADBEEF, 4, 0, 1, 1, 1, 1, int(DiagLtssmSpeed.GEN5)
        )

    def test_loopback_set_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_loopback_set.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.loopback_set(port_id=0)

    def test_loopback_get_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.loopback_get(port_id=6)
        mock_library.switchtec_diag_loopback_get.assert_called_once()
        call_args = mock_library.switchtec_diag_loopback_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 6

    def test_loopback_get_returns_loopback_status(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.loopback_get(port_id=3)
        assert isinstance(result, LoopbackStatus)
        assert result.port_id == 3
        # Mock does not write to byref, so enabled/ltssm_speed default to 0
        assert result.enabled == 0
        assert result.ltssm_speed == 0

    def test_loopback_get_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_loopback_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.loopback_get(port_id=0)


class TestDiagnosticsManagerPatternGen:
    def test_pattern_gen_set(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_gen_set(port_id=1)
        mock_library.switchtec_diag_pattern_gen_set.assert_called_once_with(
            0xDEADBEEF, 1, 3, 4
        )

    def test_pattern_gen_set_custom(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_gen_set(
            port_id=5,
            pattern=DiagPattern.PRBS_7,
            link_speed=DiagPatternLinkRate.GEN5,
        )
        mock_library.switchtec_diag_pattern_gen_set.assert_called_once_with(
            0xDEADBEEF, 5, int(DiagPattern.PRBS_7), int(DiagPatternLinkRate.GEN5)
        )

    def test_pattern_gen_get_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.pattern_gen_get(port_id=2)
        mock_library.switchtec_diag_pattern_gen_get.assert_called_once()
        call_args = mock_library.switchtec_diag_pattern_gen_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2

    def test_pattern_gen_get_returns_int(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.pattern_gen_get(port_id=1)
        # Mock does not write to byref, so pattern_type defaults to 0
        assert result == 0
        assert isinstance(result, int)

    def test_pattern_gen_get_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_pattern_gen_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.pattern_gen_get(port_id=0)


class TestDiagnosticsManagerPatternMon:
    def test_pattern_mon_set(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_mon_set(port_id=1)
        mock_library.switchtec_diag_pattern_mon_set.assert_called_once_with(
            0xDEADBEEF, 1, 3
        )

    def test_pattern_mon_get_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.pattern_mon_get(port_id=4, lane_id=2)
        mock_library.switchtec_diag_pattern_mon_get.assert_called_once()
        call_args = mock_library.switchtec_diag_pattern_mon_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 4
        assert call_args[2] == 2

    def test_pattern_mon_get_returns_result(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.pattern_mon_get(port_id=1, lane_id=0)
        assert isinstance(result, PatternMonResult)
        assert result.port_id == 1
        assert result.lane_id == 0
        # Mock does not write to byref, defaults to 0
        assert result.pattern_type == 0
        assert result.error_count == 0

    def test_pattern_mon_get_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_pattern_mon_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.pattern_mon_get(port_id=0, lane_id=0)


class TestDiagnosticsManagerPatternInject:
    def test_pattern_inject(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_inject(port_id=1, err_count=5)
        mock_library.switchtec_diag_pattern_inject.assert_called_once_with(
            0xDEADBEEF, 1, 5
        )


class TestDiagnosticsManagerRcvrObj:
    def test_rcvr_obj_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.rcvr_obj(port_id=1, lane_id=3)
        mock_library.switchtec_diag_rcvr_obj.assert_called_once()
        call_args = mock_library.switchtec_diag_rcvr_obj.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 1
        assert call_args[2] == 3
        assert call_args[3] == int(DiagLink.CURRENT)

    def test_rcvr_obj_with_previous_link(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.rcvr_obj(
            port_id=2, lane_id=0, link=DiagLink.PREVIOUS
        )
        call_args = mock_library.switchtec_diag_rcvr_obj.call_args[0]
        assert call_args[3] == int(DiagLink.PREVIOUS)

    def test_rcvr_obj_returns_receiver_object(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.rcvr_obj(port_id=0, lane_id=0)
        assert isinstance(result, ReceiverObject)
        # Mock does not fill struct, all fields default to 0
        assert result.port_id == 0
        assert result.lane_id == 0
        assert result.ctle == 0
        assert result.target_amplitude == 0
        assert result.speculative_dfe == 0
        assert len(result.dynamic_dfe) == 7
        assert all(d == 0 for d in result.dynamic_dfe)

    def test_rcvr_obj_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_rcvr_obj.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.rcvr_obj(port_id=0, lane_id=0)


class TestDiagnosticsManagerRcvrExt:
    def test_rcvr_ext_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.rcvr_ext(port_id=2, lane_id=1)
        mock_library.switchtec_diag_rcvr_ext.assert_called_once()
        call_args = mock_library.switchtec_diag_rcvr_ext.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2
        assert call_args[2] == 1
        assert call_args[3] == int(DiagLink.CURRENT)

    def test_rcvr_ext_with_previous_link(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.rcvr_ext(port_id=0, lane_id=0, link=DiagLink.PREVIOUS)
        call_args = mock_library.switchtec_diag_rcvr_ext.call_args[0]
        assert call_args[3] == int(DiagLink.PREVIOUS)

    def test_rcvr_ext_returns_receiver_ext(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.rcvr_ext(port_id=0, lane_id=0)
        assert isinstance(result, ReceiverExt)
        assert result.ctle2_rx_mode == 0
        assert result.dtclk_5 == 0
        assert result.dtclk_8_6 == 0
        assert result.dtclk_9 == 0

    def test_rcvr_ext_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_rcvr_ext.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.rcvr_ext(port_id=0, lane_id=0)


class TestDiagnosticsManagerPortEqTxCoeff:
    def test_port_eq_tx_coeff_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_coeff(port_id=3)
        mock_library.switchtec_diag_port_eq_tx_coeff.assert_called_once()
        call_args = mock_library.switchtec_diag_port_eq_tx_coeff.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 3
        assert call_args[2] == 0  # prev_speed default
        assert call_args[3] == int(DiagEnd.LOCAL)
        assert call_args[4] == int(DiagLink.CURRENT)

    def test_port_eq_tx_coeff_custom_params(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.port_eq_tx_coeff(
            port_id=1,
            prev_speed=2,
            end=DiagEnd.FAR_END,
            link=DiagLink.PREVIOUS,
        )
        call_args = mock_library.switchtec_diag_port_eq_tx_coeff.call_args[0]
        assert call_args[2] == 2
        assert call_args[3] == int(DiagEnd.FAR_END)
        assert call_args[4] == int(DiagLink.PREVIOUS)

    def test_port_eq_tx_coeff_returns_result(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_coeff(port_id=0)
        assert isinstance(result, PortEqCoeff)
        # lane_cnt defaults to 0 in the mock, so cursors list is empty
        assert result.lane_count == 0
        assert result.cursors == []

    def test_port_eq_tx_coeff_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_port_eq_tx_coeff.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.port_eq_tx_coeff(port_id=0)


class TestDiagnosticsManagerPortEqTxTable:
    def test_port_eq_tx_table_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_table(port_id=2)
        mock_library.switchtec_diag_port_eq_tx_table.assert_called_once()
        call_args = mock_library.switchtec_diag_port_eq_tx_table.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 2
        assert call_args[2] == 0  # prev_speed default
        assert call_args[3] == int(DiagLink.CURRENT)

    def test_port_eq_tx_table_custom_params(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.port_eq_tx_table(
            port_id=5, prev_speed=3, link=DiagLink.PREVIOUS
        )
        call_args = mock_library.switchtec_diag_port_eq_tx_table.call_args[0]
        assert call_args[2] == 3
        assert call_args[3] == int(DiagLink.PREVIOUS)

    def test_port_eq_tx_table_returns_result(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_table(port_id=0)
        assert isinstance(result, PortEqTable)
        # step_cnt defaults to 0, so steps list is empty
        assert result.step_count == 0
        assert result.steps == []
        assert result.lane_id == 0

    def test_port_eq_tx_table_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_port_eq_tx_table.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.port_eq_tx_table(port_id=0)


class TestDiagnosticsManagerPortEqTxFslf:
    def test_port_eq_tx_fslf_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_fslf(port_id=1)
        mock_library.switchtec_diag_port_eq_tx_fslf.assert_called_once()
        call_args = mock_library.switchtec_diag_port_eq_tx_fslf.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 1
        assert call_args[2] == 0  # prev_speed default
        assert call_args[3] == 0  # lane_id default
        assert call_args[4] == int(DiagEnd.LOCAL)
        assert call_args[5] == int(DiagLink.CURRENT)

    def test_port_eq_tx_fslf_custom_params(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.port_eq_tx_fslf(
            port_id=3,
            prev_speed=1,
            lane_id=5,
            end=DiagEnd.FAR_END,
            link=DiagLink.PREVIOUS,
        )
        call_args = mock_library.switchtec_diag_port_eq_tx_fslf.call_args[0]
        assert call_args[1] == 3
        assert call_args[2] == 1
        assert call_args[3] == 5
        assert call_args[4] == int(DiagEnd.FAR_END)
        assert call_args[5] == int(DiagLink.PREVIOUS)

    def test_port_eq_tx_fslf_returns_result(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.port_eq_tx_fslf(port_id=0)
        assert isinstance(result, PortEqTxFslf)
        assert result.fs == 0
        assert result.lf == 0

    def test_port_eq_tx_fslf_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_port_eq_tx_fslf.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.port_eq_tx_fslf(port_id=0)


class TestDiagnosticsManagerCrossHair:
    def test_cross_hair_enable(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.cross_hair_enable(lane_id=3)
        mock_library.switchtec_diag_cross_hair_enable.assert_called_once_with(
            0xDEADBEEF, 3
        )

    def test_cross_hair_disable(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.cross_hair_disable()
        mock_library.switchtec_diag_cross_hair_disable.assert_called_once_with(
            0xDEADBEEF
        )

    def test_cross_hair_get_calls_lib(self, device, mock_library):
        diag = DiagnosticsManager(device)
        result = diag.cross_hair_get(start_lane_id=0, num_lanes=2)
        mock_library.switchtec_diag_cross_hair_get.assert_called_once()
        call_args = mock_library.switchtec_diag_cross_hair_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0
        assert call_args[2] == 2

    def test_cross_hair_get_returns_list_of_results(
        self, device, mock_library
    ):
        diag = DiagnosticsManager(device)
        results = diag.cross_hair_get(start_lane_id=0, num_lanes=3)
        assert isinstance(results, list)
        assert len(results) == 3
        for r in results:
            assert isinstance(r, CrossHairResult)

    def test_cross_hair_get_default_values(self, device, mock_library):
        diag = DiagnosticsManager(device)
        results = diag.cross_hair_get(start_lane_id=0, num_lanes=1)
        assert len(results) == 1
        r = results[0]
        # Mock does not fill struct, state defaults to 0 (DISABLED)
        assert r.state == 0
        assert r.state_name == DiagCrossHairState.DISABLED.name
        assert r.eye_left_lim == 0
        assert r.eye_right_lim == 0

    def test_cross_hair_get_single_lane(self, device, mock_library):
        diag = DiagnosticsManager(device)
        results = diag.cross_hair_get()
        assert len(results) == 1

    def test_cross_hair_get_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_diag_cross_hair_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.cross_hair_get()


# ─── AER Event Generation Tests ─────────────────────────────────────


class TestAerEventGen:
    def test_aer_event_gen_happy_path(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.aer_event_gen(port_id=3, error_id=0x10, trigger=1)
        mock_library.switchtec_aer_event_gen.assert_called_once_with(
            0xDEADBEEF, 3, 0x10, 1,
        )

    def test_aer_event_gen_verifies_all_args(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.aer_event_gen(port_id=7, error_id=0xFF, trigger=2)
        call_args = mock_library.switchtec_aer_event_gen.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 7
        assert call_args[2] == 0xFF
        assert call_args[3] == 2

    def test_aer_event_gen_default_trigger(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.aer_event_gen(port_id=1, error_id=0x05)
        mock_library.switchtec_aer_event_gen.assert_called_once_with(
            0xDEADBEEF, 1, 0x05, 0,
        )

    def test_aer_event_gen_error_return(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_aer_event_gen.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        diag = DiagnosticsManager(device)
        with pytest.raises(SwitchtecError):
            diag.aer_event_gen(port_id=0, error_id=0x01)
