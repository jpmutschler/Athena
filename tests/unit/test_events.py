"""Tests for EventManager."""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock

import pytest

from serialcables_switchtec.bindings.constants import EventFlags, EventId
from serialcables_switchtec.core.events import EventManager
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.events import EventSummaryResult


class TestGetSummary:
    def test_get_summary_returns_result(self, device, mock_library):
        mgr = EventManager(device)
        result = mgr.get_summary()
        assert isinstance(result, EventSummaryResult)
        mock_library.switchtec_event_summary.assert_called_once()

    def test_get_summary_with_events(self, device, mock_library):
        """Verify summary counts when the C struct has non-zero values."""

        def fill_summary(handle, summary_ptr):
            summary = summary_ptr._obj
            summary.global_events = 3
            summary.part[0] = 1
            summary.part[1] = 2
            summary.pff[0] = 5
            summary.pff[3] = 10
            return 0

        mock_library.switchtec_event_summary = MagicMock(side_effect=fill_summary)

        mgr = EventManager(device)
        result = mgr.get_summary()
        assert result.global_events == 3
        assert result.partition_events == 3  # 1 + 2
        assert result.pff_events == 15  # 5 + 10
        assert result.total_count == 21  # 3 + 3 + 15

    def test_get_summary_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_event_summary.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventManager(device)
        with pytest.raises(SwitchtecError):
            mgr.get_summary()


class TestEventCtl:
    def test_event_ctl_enable(self, device, mock_library):
        mgr = EventManager(device)
        ret = mgr.event_ctl(
            event_id=EventId.GLOBAL_STACK_ERROR,
            index=0,
            flags=EventFlags.EN_POLL,
        )
        mock_library.switchtec_event_ctl.assert_called_once()
        call_args = mock_library.switchtec_event_ctl.call_args[0]
        assert call_args[0] == 0xDEADBEEF
        assert call_args[1] == int(EventId.GLOBAL_STACK_ERROR)
        assert call_args[2] == 0
        assert call_args[3] == int(EventFlags.EN_POLL)
        assert ret == 0

    def test_event_ctl_clear(self, device, mock_library):
        mgr = EventManager(device)
        ret = mgr.event_ctl(
            event_id=EventId.PFF_AER_IN_P2P,
            index=5,
            flags=EventFlags.CLEAR,
        )
        call_args = mock_library.switchtec_event_ctl.call_args[0]
        assert call_args[1] == int(EventId.PFF_AER_IN_P2P)
        assert call_args[2] == 5
        assert call_args[3] == int(EventFlags.CLEAR)
        assert ret == 0

    def test_event_ctl_with_data(self, device, mock_library):
        mgr = EventManager(device)
        data = [0x1, 0x2, 0x3, 0x4, 0x5]
        ret = mgr.event_ctl(
            event_id=EventId.GLOBAL_FW_EXC,
            index=0,
            flags=EventFlags.CLEAR,
            data=data,
        )
        mock_library.switchtec_event_ctl.assert_called_once()
        # Verify the data array was passed (5th positional arg)
        call_args = mock_library.switchtec_event_ctl.call_args[0]
        data_arr = call_args[4]
        assert data_arr[0] == 0x1
        assert data_arr[1] == 0x2
        assert data_arr[2] == 0x3
        assert data_arr[3] == 0x4
        assert data_arr[4] == 0x5
        assert ret == 0

    def test_event_ctl_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_event_ctl.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventManager(device)
        with pytest.raises(SwitchtecError):
            mgr.event_ctl(
                event_id=EventId.GLOBAL_STACK_ERROR,
                index=0,
                flags=EventFlags.CLEAR,
            )


class TestWaitForEvent:
    def test_wait_for_event(self, device, mock_library):
        mgr = EventManager(device)
        mgr.wait_for_event()
        mock_library.switchtec_event_wait.assert_called_once_with(0xDEADBEEF, -1)

    def test_wait_for_event_with_timeout(self, device, mock_library):
        mgr = EventManager(device)
        mgr.wait_for_event(timeout_ms=5000)
        mock_library.switchtec_event_wait.assert_called_once_with(0xDEADBEEF, 5000)

    def test_wait_for_event_raises_on_error(self, device, mock_library, monkeypatch):
        mock_library.switchtec_event_wait.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)
        mgr = EventManager(device)
        with pytest.raises(SwitchtecError):
            mgr.wait_for_event()


class TestClearAll:
    def test_clear_all_iterates_events(self, device, mock_library):
        mgr = EventManager(device)
        mgr.clear_all()
        # Should be called for each valid event ID (excluding INVALID and
        # MAX_EVENTS)
        valid_events = [e for e in EventId if e != EventId.INVALID and e != EventId.MAX_EVENTS]
        assert mock_library.switchtec_event_ctl.call_count == len(valid_events)

    def test_clear_all_ignores_unsupported(self, device, mock_library):
        """Verify clear_all continues when individual event_ctl calls fail."""
        mock_library.switchtec_event_ctl.return_value = -1
        mgr = EventManager(device)
        # Should not raise -- errors are silently caught
        mgr.clear_all()
        # Still attempted all valid events
        valid_events = [e for e in EventId if e != EventId.INVALID and e != EventId.MAX_EVENTS]
        assert mock_library.switchtec_event_ctl.call_count == len(valid_events)

    def test_clear_all_uses_clear_flag(self, device, mock_library):
        mgr = EventManager(device)
        mgr.clear_all()
        for call_obj in mock_library.switchtec_event_ctl.call_args_list:
            args = call_obj[0]
            # flags argument is the 4th positional arg (index 3)
            assert args[3] == int(EventFlags.CLEAR)


class TestEventManagerViaDevice:
    def test_device_events_property(self, device):
        """Verify the lazy events property on SwitchtecDevice."""
        mgr = device.events
        assert isinstance(mgr, EventManager)
        # Accessing again returns the same instance
        assert device.events is mgr
