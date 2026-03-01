"""Tests for LinkHealthMonitor watch_bw and watch_evcntr generators."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from serialcables_switchtec.core.monitor import (
    BwSample,
    EvCntrSample,
    LinkHealthMonitor,
)
from serialcables_switchtec.models.performance import (
    BwCounterDirection,
    BwCounterResult,
)


def _make_bw_result(
    time_us: int = 1000,
    egress_posted: int = 100,
    egress_comp: int = 50,
    egress_nonposted: int = 25,
    ingress_posted: int = 80,
    ingress_comp: int = 40,
    ingress_nonposted: int = 20,
) -> BwCounterResult:
    return BwCounterResult(
        time_us=time_us,
        egress=BwCounterDirection(
            posted=egress_posted, comp=egress_comp, nonposted=egress_nonposted,
        ),
        ingress=BwCounterDirection(
            posted=ingress_posted, comp=ingress_comp, nonposted=ingress_nonposted,
        ),
    )


def _make_mock_device():
    dev = MagicMock()
    dev.performance.bw_get.return_value = [_make_bw_result()]
    dev.evcntr.get_counts.return_value = [42]
    return dev


# ── watch_bw ─────────────────────────────────────────────────────────────


class TestWatchBw:
    """watch_bw() generator tests."""

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_yields_samples(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_bw([0], interval=1.0, count=2))
        assert len(samples) == 2

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_is_bw_sample(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert isinstance(sample, BwSample)

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_port_id(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([7], interval=1.0, count=1))
        assert sample.port_id == 7

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_egress_total(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert sample.egress_total == 175  # 100 + 50 + 25

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_ingress_total(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert sample.ingress_total == 140  # 80 + 40 + 20

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_breakdown_fields(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert sample.egress_posted == 100
        assert sample.egress_comp == 50
        assert sample.egress_nonposted == 25
        assert sample.ingress_posted == 80
        assert sample.ingress_comp == 40
        assert sample.ingress_nonposted == 20

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_iteration_counter(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_bw([0], interval=1.0, count=3))
        assert [s.iteration for s in samples] == [1, 2, 3]

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_initial_clear_read(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        list(monitor.watch_bw([0], interval=1.0, count=1))
        # First call is baseline clear, second is the actual read
        calls = dev.performance.bw_get.call_args_list
        assert len(calls) == 2
        assert calls[0][1].get("clear") is True

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_multiple_ports(self, mock_sleep):
        dev = _make_mock_device()
        dev.performance.bw_get.return_value = [_make_bw_result(), _make_bw_result()]
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_bw([0, 4], interval=1.0, count=1))
        assert len(samples) == 2
        assert samples[0].port_id == 0
        assert samples[1].port_id == 4

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sleep_called_with_interval(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        list(monitor.watch_bw([0], interval=2.5, count=1))
        mock_sleep.assert_called_with(2.5)

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_elapsed_increases(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_bw([0], interval=1.0, count=3))
        for i in range(1, len(samples)):
            assert samples[i].elapsed_s >= samples[i - 1].elapsed_s

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_timestamp_is_positive(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert sample.timestamp > 0

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_time_us_from_result(self, mock_sleep):
        dev = _make_mock_device()
        dev.performance.bw_get.return_value = [_make_bw_result(time_us=5000)]
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        assert sample.time_us == 5000

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_is_frozen(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_bw([0], interval=1.0, count=1))
        with pytest.raises(Exception):
            sample.port_id = 99  # type: ignore[misc]


# ── watch_evcntr ─────────────────────────────────────────────────────────


class TestWatchEvCntr:
    """watch_evcntr() generator tests."""

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_yields_samples(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_evcntr(0, 0, count=2))
        assert len(samples) == 2

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_is_evcntr_sample(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_evcntr(0, 0, count=1))
        assert isinstance(sample, EvCntrSample)

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sample_fields(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        sample = next(monitor.watch_evcntr(3, 5, count=1))
        assert sample.stack_id == 3
        assert sample.counter_id == 5
        assert sample.count == 42
        assert sample.delta == 42

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_initial_clear_read(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        list(monitor.watch_evcntr(0, 0, count=1))
        calls = dev.evcntr.get_counts.call_args_list
        assert len(calls) == 2
        assert calls[0][1].get("clear") is True

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_multiple_counters(self, mock_sleep):
        dev = _make_mock_device()
        dev.evcntr.get_counts.return_value = [10, 20, 30]
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_evcntr(0, 0, nr_counters=3, count=1))
        assert len(samples) == 3
        assert samples[0].counter_id == 0
        assert samples[1].counter_id == 1
        assert samples[2].counter_id == 2

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_iteration_counter(self, mock_sleep):
        dev = _make_mock_device()
        monitor = LinkHealthMonitor(dev)
        samples = list(monitor.watch_evcntr(0, 0, count=3))
        assert [s.iteration for s in samples] == [1, 2, 3]
