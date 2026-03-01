"""Event management for Switchtec devices."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from serialcables_switchtec.bindings.constants import EventFlags, EventId
from serialcables_switchtec.bindings.types import SwitchtecEventSummary
from serialcables_switchtec.exceptions import SwitchtecError, check_error
from serialcables_switchtec.models.events import EventSummaryResult
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)


class EventManager:
    """Manages event operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def get_summary(self) -> EventSummaryResult:
        """Get a summary of all pending events.

        Returns:
            EventSummaryResult with counts of global, partition,
            and PFF events.
        """
        summary = SwitchtecEventSummary()
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_event_summary(
                self._dev.handle,
                ctypes.byref(summary),
            )
        check_error(ret, "event_summary")

        global_count = summary.global_events
        part_count = sum(summary.part[i] for i in range(len(summary.part)))
        pff_count = sum(summary.pff[i] for i in range(len(summary.pff)))
        total = global_count + part_count + pff_count

        logger.info("event_summary_retrieved", total=total)
        return EventSummaryResult(
            global_events=global_count,
            partition_events=part_count,
            pff_events=pff_count,
            total_count=total,
        )

    def event_ctl(
        self,
        event_id: EventId,
        index: int,
        flags: EventFlags,
        data: list[int] | None = None,
    ) -> int:
        """Control event configuration (enable/disable/clear).

        Args:
            event_id: The event to control.
            index: Event index (partition or PFF index).
            flags: Control flags (CLEAR, EN_POLL, etc.).
            data: Optional array of up to 5 uint32 data values.

        Returns:
            The number of events that occurred.
        """
        data_arr = (ctypes.c_uint32 * 5)()
        if data:
            for i, val in enumerate(data[:5]):
                data_arr[i] = val

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_event_ctl(
                self._dev.handle,
                int(event_id),
                index,
                int(flags),
                data_arr,
            )
        check_error(ret, "event_ctl")
        logger.info(
            "event_ctl",
            event_id=event_id.name,
            index=index,
            flags=str(flags),
        )
        return ret

    def wait_for_event(self, timeout_ms: int = -1) -> None:
        """Wait for any event to occur.

        Args:
            timeout_ms: Timeout in milliseconds. -1 for infinite.
        """
        # NOTE: Intentionally does NOT acquire device_op().
        # This is a blocking call that can wait indefinitely (timeout_ms=-1).
        # Holding the lock would starve all other device operations.
        # The C library's event_wait uses a separate poll/ioctl path
        # that is safe to call concurrently with other operations.
        ret = self._dev.lib.switchtec_event_wait(
            self._dev.handle,
            timeout_ms,
        )
        check_error(ret, "event_wait")
        logger.info("event_wait_completed")

    def clear_all(self) -> None:
        """Clear all events by iterating through event IDs."""
        for event_id in EventId:
            if event_id == EventId.INVALID or event_id == EventId.MAX_EVENTS:
                continue
            try:
                self.event_ctl(
                    event_id,
                    index=0,
                    flags=EventFlags.CLEAR,
                )
            except SwitchtecError:
                # Some events may not be supported on all devices
                continue
        logger.info("all_events_cleared")
