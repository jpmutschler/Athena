"""Tests for PerformanceManager."""

from __future__ import annotations

import ctypes
from unittest.mock import ANY

import pytest

from serialcables_switchtec.core.performance import PerformanceManager
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.performance import (
    BwCounterResult,
    LatencyResult,
)


class TestPerformanceManagerBwGet:
    def test_bw_get_calls_lib_with_correct_args(self, device, mock_library):
        perf = PerformanceManager(device)
        perf.bw_get(phys_port_ids=[0, 1, 2])
        mock_library.switchtec_bwcntr_many.assert_called_once()
        call_args = mock_library.switchtec_bwcntr_many.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 3
        # port_ids_arr is a c_int array, verify it was passed
        assert call_args[3] == 0  # clear=False -> int(False) == 0

    def test_bw_get_with_clear_flag(self, device, mock_library):
        perf = PerformanceManager(device)
        perf.bw_get(phys_port_ids=[5], clear=True)
        call_args = mock_library.switchtec_bwcntr_many.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 1
        assert call_args[3] == 1  # clear=True -> int(True) == 1

    def test_bw_get_returns_list_of_results(self, device, mock_library):
        perf = PerformanceManager(device)
        results = perf.bw_get(phys_port_ids=[0, 1])
        assert isinstance(results, list)
        assert len(results) == 2
        for r in results:
            assert isinstance(r, BwCounterResult)

    def test_bw_get_single_port(self, device, mock_library):
        perf = PerformanceManager(device)
        results = perf.bw_get(phys_port_ids=[7])
        assert len(results) == 1
        assert isinstance(results[0], BwCounterResult)
        assert results[0].time_us == 0
        assert results[0].egress.posted == 0
        assert results[0].ingress.posted == 0

    def test_bw_get_empty_port_list(self, device, mock_library):
        perf = PerformanceManager(device)
        results = perf.bw_get(phys_port_ids=[])
        assert results == []

    def test_bw_get_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_bwcntr_many.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        perf = PerformanceManager(device)
        with pytest.raises(SwitchtecError):
            perf.bw_get(phys_port_ids=[0])


class TestPerformanceManagerLatSetup:
    def test_lat_setup_calls_lib_with_correct_args(
        self, device, mock_library
    ):
        perf = PerformanceManager(device)
        perf.lat_setup(egress_port_id=1, ingress_port_id=2)
        mock_library.switchtec_lat_setup.assert_called_once_with(
            0xDEADBEEF, 1, 2, 0
        )

    def test_lat_setup_with_clear(self, device, mock_library):
        perf = PerformanceManager(device)
        perf.lat_setup(egress_port_id=3, ingress_port_id=4, clear=True)
        mock_library.switchtec_lat_setup.assert_called_once_with(
            0xDEADBEEF, 3, 4, 1
        )

    def test_lat_setup_raises_on_error(
        self, device, mock_library, monkeypatch
    ):
        mock_library.switchtec_lat_setup.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        perf = PerformanceManager(device)
        with pytest.raises(SwitchtecError):
            perf.lat_setup(egress_port_id=0, ingress_port_id=1)


class TestPerformanceManagerLatGet:
    def test_lat_get_calls_lib_with_correct_args(self, device, mock_library):
        perf = PerformanceManager(device)
        perf.lat_get(egress_port_id=5)
        mock_library.switchtec_lat_get.assert_called_once()
        call_args = mock_library.switchtec_lat_get.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == 0  # clear=False -> int(False) == 0
        assert call_args[2] == 5  # egress_port_id

    def test_lat_get_with_clear(self, device, mock_library):
        perf = PerformanceManager(device)
        perf.lat_get(egress_port_id=2, clear=True)
        call_args = mock_library.switchtec_lat_get.call_args[0]
        assert call_args[1] == 1  # clear=True

    def test_lat_get_returns_latency_result(self, device, mock_library):
        perf = PerformanceManager(device)
        result = perf.lat_get(egress_port_id=3)
        assert isinstance(result, LatencyResult)
        assert result.egress_port_id == 3
        # cur_ns and max_ns default to 0 since the mock does not write to byref
        assert result.current_ns == 0
        assert result.max_ns == 0

    def test_lat_get_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_lat_get.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        perf = PerformanceManager(device)
        with pytest.raises(SwitchtecError):
            perf.lat_get(egress_port_id=0)
