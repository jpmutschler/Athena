"""Tests for OrderedSetAnalyzer."""

from __future__ import annotations

import ctypes
from unittest.mock import ANY

import pytest

from serialcables_switchtec.core.osa import OrderedSetAnalyzer
from serialcables_switchtec.exceptions import SwitchtecError


class TestOrderedSetAnalyzerStart:
    def test_start_calls_lib_with_correct_args(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        osa.start(stack_id=2)
        mock_library.switchtec_osa.assert_called_once_with(0xDEADBEEF, 2, 1)

    def test_start_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_osa.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.start(stack_id=0)


class TestOrderedSetAnalyzerStop:
    def test_stop_calls_lib_with_correct_args(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        osa.stop(stack_id=3)
        mock_library.switchtec_osa.assert_called_once_with(0xDEADBEEF, 3, 0)

    def test_stop_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_osa.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.stop(stack_id=0)


class TestOrderedSetAnalyzerConfigureType:
    def test_configure_type_calls_lib_with_correct_args(
        self, device, mock_library
    ):
        osa = OrderedSetAnalyzer(device)
        osa.configure_type(
            stack_id=1,
            direction=0,
            lane_mask=0xFF,
            link_rate=4,
            os_types=0x03,
        )
        mock_library.switchtec_osa_config_type.assert_called_once_with(
            0xDEADBEEF, 1, 0, 0xFF, 4, 0x03
        )

    def test_configure_type_with_tx_direction(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        osa.configure_type(
            stack_id=0,
            direction=1,
            lane_mask=0x0F,
            link_rate=5,
            os_types=0x01,
        )
        mock_library.switchtec_osa_config_type.assert_called_once_with(
            0xDEADBEEF, 0, 1, 0x0F, 5, 0x01
        )

    def test_configure_type_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_osa_config_type.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.configure_type(
                stack_id=0,
                direction=0,
                lane_mask=0xFF,
                link_rate=4,
                os_types=0x01,
            )


class TestOrderedSetAnalyzerConfigurePattern:
    def test_configure_pattern_calls_lib(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        value_data = [0x11111111, 0x22222222, 0x33333333, 0x44444444]
        mask_data = [0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF]

        osa.configure_pattern(
            stack_id=1,
            direction=0,
            lane_mask=0xF0,
            link_rate=3,
            value_data=value_data,
            mask_data=mask_data,
        )
        mock_library.switchtec_osa_config_pattern.assert_called_once()
        call_args = mock_library.switchtec_osa_config_pattern.call_args
        assert call_args[0][0] == 0xDEADBEEF
        assert call_args[0][1] == 1
        assert call_args[0][2] == 0
        assert call_args[0][3] == 0xF0
        assert call_args[0][4] == 3

    def test_configure_pattern_truncates_to_4_dwords(
        self, device, mock_library
    ):
        osa = OrderedSetAnalyzer(device)
        value_data = [1, 2, 3, 4, 5, 6]
        mask_data = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

        osa.configure_pattern(
            stack_id=0,
            direction=1,
            lane_mask=0x01,
            link_rate=4,
            value_data=value_data,
            mask_data=mask_data,
        )
        mock_library.switchtec_osa_config_pattern.assert_called_once()

    def test_configure_pattern_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_osa_config_pattern.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.configure_pattern(
                stack_id=0,
                direction=0,
                lane_mask=0xFF,
                link_rate=4,
                value_data=[0, 0, 0, 0],
                mask_data=[0, 0, 0, 0],
            )


class TestOrderedSetAnalyzerCaptureControl:
    def test_capture_control_with_defaults(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        osa.capture_control(stack_id=2, lane_mask=0xFF, direction=0)
        mock_library.switchtec_osa_capture_control.assert_called_once_with(
            0xDEADBEEF, 2, 0xFF, 0, 0, 0, 0, 0, 0
        )

    def test_capture_control_with_all_params(self, device, mock_library):
        osa = OrderedSetAnalyzer(device)
        osa.capture_control(
            stack_id=1,
            lane_mask=0x0F,
            direction=1,
            drop_single_os=1,
            stop_mode=2,
            snapshot_mode=1,
            post_trigger=128,
            os_types=0x07,
        )
        mock_library.switchtec_osa_capture_control.assert_called_once_with(
            0xDEADBEEF, 1, 0x0F, 1, 1, 2, 1, 128, 0x07
        )

    def test_capture_control_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_osa_capture_control.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.capture_control(stack_id=0, lane_mask=0xFF, direction=0)


class TestOrderedSetAnalyzerCaptureData:
    def test_capture_data_returns_ret_value(self, device, mock_library):
        mock_library.switchtec_osa_capture_data.return_value = 0
        osa = OrderedSetAnalyzer(device)
        result = osa.capture_data(stack_id=1, lane=3, direction=0)
        assert result == 0
        mock_library.switchtec_osa_capture_data.assert_called_once_with(
            0xDEADBEEF, 1, 3, 0
        )

    def test_capture_data_with_tx_direction(self, device, mock_library):
        mock_library.switchtec_osa_capture_data.return_value = 5
        osa = OrderedSetAnalyzer(device)
        result = osa.capture_data(stack_id=0, lane=7, direction=1)
        assert result == 5
        mock_library.switchtec_osa_capture_data.assert_called_once_with(
            0xDEADBEEF, 0, 7, 1
        )

    def test_capture_data_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_osa_capture_data.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.capture_data(stack_id=0, lane=0, direction=0)


class TestOrderedSetAnalyzerDumpConfig:
    def test_dump_config_returns_ret_value(self, device, mock_library):
        mock_library.switchtec_osa_dump_conf.return_value = 0
        osa = OrderedSetAnalyzer(device)
        result = osa.dump_config(stack_id=2)
        assert result == 0
        mock_library.switchtec_osa_dump_conf.assert_called_once_with(
            0xDEADBEEF, 2
        )

    def test_dump_config_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_osa_dump_conf.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        osa = OrderedSetAnalyzer(device)
        with pytest.raises(SwitchtecError):
            osa.dump_config(stack_id=0)
