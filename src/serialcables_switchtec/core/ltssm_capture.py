"""LTSSM capture buffer and event-triggered capture.

Provides a software-side ring buffer that deduplicates polled firmware LTSSM
entries and an event-triggered capture mechanism that arms a hardware event
and captures the LTSSM log when the event fires.
"""

from __future__ import annotations

import threading
from typing import Any

from serialcables_switchtec.bindings.constants import EventFlags, EventId


class LtssmCaptureBuffer:
    """Software-side buffer that deduplicates polled firmware LTSSM entries.

    Entries are deduplicated by timestamp: entries with timestamp <= the
    last seen timestamp are skipped.  When new entries arrive with timestamps
    lower than the last seen, a firmware buffer wrap is detected.

    Thread-safe: all mutable state is guarded by an internal lock.
    """

    def __init__(self, max_entries: int = 4096) -> None:
        self._max_entries = max_entries
        self._entries: list[Any] = []
        self._last_seen_ts: int | None = None
        self._wrap_count = 0
        self._lock = threading.Lock()

    def ingest(self, firmware_entries: list[Any]) -> int:
        """Ingest firmware entries, deduplicating against prior state.

        Returns:
            Number of genuinely new entries accepted.
        """
        if not firmware_entries:
            return 0

        with self._lock:
            new_entries: list[Any] = []

            if self._last_seen_ts is not None:
                # Filter to only genuinely new entries
                new_entries = [
                    e for e in firmware_entries
                    if e.timestamp > self._last_seen_ts
                ]

                # If no new entries found but the batch has entries with lower
                # timestamps than what we've seen, firmware buffer has wrapped
                if not new_entries:
                    last_batch_ts = firmware_entries[-1].timestamp
                    if last_batch_ts < self._last_seen_ts:
                        # Wrap: entirely new entries with lower timestamps
                        self._wrap_count += 1
                        new_entries = list(firmware_entries)
            else:
                new_entries = list(firmware_entries)

            if not new_entries:
                return 0

            self._entries.extend(new_entries)
            self._last_seen_ts = new_entries[-1].timestamp

            # Trim to max_entries, keeping newest
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

            return len(new_entries)

    def snapshot(self) -> list[Any]:
        """Return an immutable copy of the current buffer contents."""
        with self._lock:
            return list(self._entries)

    @property
    def wrap_count(self) -> int:
        """Number of detected firmware buffer wraps."""
        with self._lock:
            return self._wrap_count

    @property
    def total_entries(self) -> int:
        """Number of entries currently held."""
        with self._lock:
            return len(self._entries)


class EventTriggeredCapture:
    """Arms a device event and captures LTSSM log on trigger.

    Leverages ``EventManager.wait_for_event()`` which intentionally does
    NOT hold the device lock (safe for background blocking).
    """

    def __init__(
        self,
        device: Any,
        port_id: int,
        event_id: EventId = EventId.PFF_LINK_STATE,
        buffer_size: int = 4096,
    ) -> None:
        self._device = device
        self._port_id = port_id
        self._event_id = event_id
        self._buffer = LtssmCaptureBuffer(max_entries=buffer_size)
        self._trigger_count = 0

    def arm(self) -> None:
        """Arm the event for polling and clear previous occurrences."""
        self._device.events.event_ctl(
            self._event_id,
            self._port_id,
            EventFlags.EN_POLL | EventFlags.CLEAR,
        )

    def wait_and_capture(self, timeout_ms: int = 5000) -> int:
        """Block until event fires, then capture LTSSM log.

        Returns:
            Number of new entries captured, or 0 on timeout.
        """
        try:
            self._device.events.wait_for_event(timeout_ms=timeout_ms)
        except (TimeoutError, OSError):
            return 0

        entries = self._device.diagnostics.ltssm_log(self._port_id)
        new_count = self._buffer.ingest(entries)
        self._trigger_count += 1
        return new_count

    @property
    def buffer(self) -> LtssmCaptureBuffer:
        """Access the underlying capture buffer."""
        return self._buffer

    @property
    def trigger_count(self) -> int:
        """Number of successful event triggers captured."""
        return self._trigger_count
