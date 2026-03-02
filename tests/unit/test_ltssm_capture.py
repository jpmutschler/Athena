"""Tests for LTSSM capture buffer and event-triggered capture."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from serialcables_switchtec.core.ltssm_capture import (
    EventTriggeredCapture,
    LtssmCaptureBuffer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(timestamp: int, state: str = "L0"):
    entry = MagicMock()
    entry.timestamp = timestamp
    entry.link_state_str = state
    return entry


def _make_entries(timestamps: list[int], state: str = "L0"):
    return [_make_entry(ts, state) for ts in timestamps]


# ---------------------------------------------------------------------------
# LtssmCaptureBuffer
# ---------------------------------------------------------------------------


class TestLtssmCaptureBuffer:
    """Tests for the software-side deduplication buffer."""

    def test_ingest_new_entries(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        entries = _make_entries([10, 20, 30])
        new_count = buf.ingest(entries)
        assert new_count == 3
        assert buf.total_entries == 3

    def test_dedup_on_repeated_ingest(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        entries = _make_entries([10, 20, 30])
        buf.ingest(entries)
        # Re-ingest same entries — should all be deduped
        new_count = buf.ingest(entries)
        assert new_count == 0
        assert buf.total_entries == 3

    def test_partial_overlap(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        buf.ingest(_make_entries([10, 20, 30]))
        # Second batch overlaps on 20,30 but adds 40,50
        new_count = buf.ingest(_make_entries([20, 30, 40, 50]))
        assert new_count == 2
        assert buf.total_entries == 5

    def test_wrap_detection(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        buf.ingest(_make_entries([100, 200, 300]))
        assert buf.wrap_count == 0
        # Firmware wrapped: new entries have lower timestamps
        new_count = buf.ingest(_make_entries([10, 20]))
        assert new_count == 2
        assert buf.wrap_count == 1
        assert buf.total_entries == 5

    def test_max_entries_cap(self):
        buf = LtssmCaptureBuffer(max_entries=5)
        buf.ingest(_make_entries([1, 2, 3, 4, 5]))
        assert buf.total_entries == 5
        # Adding more should trim oldest
        buf.ingest(_make_entries([6, 7, 8]))
        assert buf.total_entries == 5
        snapshot = buf.snapshot()
        timestamps = [e.timestamp for e in snapshot]
        assert timestamps == [4, 5, 6, 7, 8]

    def test_empty_ingest(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        new_count = buf.ingest([])
        assert new_count == 0
        assert buf.total_entries == 0

    def test_snapshot_returns_copy(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        buf.ingest(_make_entries([10, 20]))
        snap1 = buf.snapshot()
        snap2 = buf.snapshot()
        assert snap1 is not snap2
        assert snap1 == snap2

    def test_multiple_wraps_tracked(self):
        buf = LtssmCaptureBuffer(max_entries=4096)
        buf.ingest(_make_entries([100, 200]))
        buf.ingest(_make_entries([10, 20]))  # wrap 1
        buf.ingest(_make_entries([5, 6]))    # wrap 2
        assert buf.wrap_count == 2


# ---------------------------------------------------------------------------
# EventTriggeredCapture (Phase 4)
# ---------------------------------------------------------------------------


class TestEventTriggeredCapture:
    """Tests for event-triggered LTSSM capture."""

    def _make_device(self):
        dev = MagicMock()
        dev.events = MagicMock()
        dev.events.event_ctl = MagicMock(return_value=0)
        dev.events.wait_for_event = MagicMock()
        dev.diagnostics = MagicMock()
        dev.diagnostics.ltssm_log = MagicMock(return_value=[])
        return dev

    def test_arm_calls_event_ctl(self):
        dev = self._make_device()
        cap = EventTriggeredCapture(dev, port_id=0)
        cap.arm()
        dev.events.event_ctl.assert_called_once()

    def test_wait_and_capture_on_event(self):
        dev = self._make_device()
        entries = _make_entries([10, 20, 30])
        dev.diagnostics.ltssm_log.return_value = entries
        dev.events.wait_for_event.return_value = None

        cap = EventTriggeredCapture(dev, port_id=0)
        cap.arm()
        new_count = cap.wait_and_capture(timeout_ms=5000)

        assert new_count == 3
        assert cap.trigger_count == 1

    def test_timeout_returns_zero(self):
        dev = self._make_device()
        dev.events.wait_for_event.side_effect = TimeoutError("timeout")

        cap = EventTriggeredCapture(dev, port_id=0)
        cap.arm()
        new_count = cap.wait_and_capture(timeout_ms=100)

        assert new_count == 0
        assert cap.trigger_count == 0

    def test_trigger_count_tracks(self):
        dev = self._make_device()
        entries_batch1 = _make_entries([10, 20])
        entries_batch2 = _make_entries([30, 40])
        dev.diagnostics.ltssm_log.side_effect = [entries_batch1, entries_batch2]
        dev.events.wait_for_event.return_value = None

        cap = EventTriggeredCapture(dev, port_id=0)
        cap.arm()
        cap.wait_and_capture()
        cap.wait_and_capture()

        assert cap.trigger_count == 2

    def test_multiple_triggers_accumulate(self):
        dev = self._make_device()
        entries_batch1 = _make_entries([10, 20])
        entries_batch2 = _make_entries([30, 40])
        dev.diagnostics.ltssm_log.side_effect = [entries_batch1, entries_batch2]
        dev.events.wait_for_event.return_value = None

        cap = EventTriggeredCapture(dev, port_id=0)
        cap.arm()
        cap.wait_and_capture()
        cap.wait_and_capture()

        assert cap.buffer.total_entries == 4
