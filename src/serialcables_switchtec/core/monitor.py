"""Continuous monitoring for link health, bandwidth, and error counters."""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)


class MonitorSample(BaseModel):
    """A single monitoring sample with timestamp."""

    model_config = ConfigDict(frozen=True)

    timestamp: float
    elapsed_s: float
    iteration: int


class BwSample(MonitorSample):
    """Bandwidth counter sample for a port."""

    model_config = ConfigDict(frozen=True)

    port_id: int
    time_us: int
    egress_total: int
    ingress_total: int
    egress_posted: int
    egress_comp: int
    egress_nonposted: int
    ingress_posted: int
    ingress_comp: int
    ingress_nonposted: int


class EvCntrSample(MonitorSample):
    """Event counter sample."""

    model_config = ConfigDict(frozen=True)

    stack_id: int
    counter_id: int
    count: int
    delta: int


class LinkHealthMonitor:
    """Monitors link health by sampling counters at regular intervals.

    Holds the device open across iterations and uses clear-on-read for
    delta-based monitoring.

    Usage:
        with SwitchtecDevice.open("/dev/switchtec0") as dev:
            monitor = LinkHealthMonitor(dev)
            for sample in monitor.watch_bw([0, 4], interval=1.0, count=60):
                print(f"Port {sample.port_id}: {sample.egress_total} bytes")
    """

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def watch_bw(
        self,
        port_ids: list[int],
        *,
        interval: float = 1.0,
        count: int = 0,
    ) -> Generator[BwSample, None, None]:
        """Yield bandwidth samples at regular intervals.

        Args:
            port_ids: Physical port IDs to monitor.
            interval: Seconds between samples.
            count: Number of samples (0 = infinite).

        Yields:
            BwSample for each port at each interval.
        """
        perf = self._dev.performance
        # Initial clear read to establish baseline
        perf.bw_get(port_ids, clear=True)

        start = time.monotonic()
        iteration = 0
        while count == 0 or iteration < count:
            time.sleep(interval)
            iteration += 1
            now = time.monotonic()
            elapsed = now - start

            results = perf.bw_get(port_ids, clear=True)
            for pid, r in zip(port_ids, results):
                yield BwSample(
                    timestamp=now,
                    elapsed_s=elapsed,
                    iteration=iteration,
                    port_id=pid,
                    time_us=r.time_us,
                    egress_total=r.egress.total,
                    ingress_total=r.ingress.total,
                    egress_posted=r.egress.posted,
                    egress_comp=r.egress.comp,
                    egress_nonposted=r.egress.nonposted,
                    ingress_posted=r.ingress.posted,
                    ingress_comp=r.ingress.comp,
                    ingress_nonposted=r.ingress.nonposted,
                )

    def watch_evcntr(
        self,
        stack_id: int,
        counter_id: int,
        nr_counters: int = 1,
        *,
        interval: float = 1.0,
        count: int = 0,
    ) -> Generator[EvCntrSample, None, None]:
        """Yield event counter samples at regular intervals.

        Uses clear-on-read so each sample shows the delta since last read.

        Args:
            stack_id: Stack ID.
            counter_id: Starting counter ID.
            nr_counters: Number of consecutive counters.
            interval: Seconds between samples.
            count: Number of samples (0 = infinite).

        Yields:
            EvCntrSample for each counter at each interval.
        """
        evcntr = self._dev.evcntr
        # Initial clear read to establish baseline
        evcntr.get_counts(stack_id, counter_id, nr_counters, clear=True)

        start = time.monotonic()
        iteration = 0
        while count == 0 or iteration < count:
            time.sleep(interval)
            iteration += 1
            now = time.monotonic()
            elapsed = now - start

            counts = evcntr.get_counts(
                stack_id, counter_id, nr_counters, clear=True
            )
            for i, c in enumerate(counts):
                yield EvCntrSample(
                    timestamp=now,
                    elapsed_s=elapsed,
                    iteration=iteration,
                    stack_id=stack_id,
                    counter_id=counter_id + i,
                    count=c,
                    delta=c,  # With clear=True, each read IS the delta
                )
