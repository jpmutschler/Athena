"""Performance monitoring: bandwidth counters, latency counters, event counters."""

from __future__ import annotations

import ctypes
from ctypes import POINTER, c_int

from serialcables_switchtec.bindings.types import SwitchtecBwCntrRes, SwitchtecPortId
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.models.performance import (
    BwCounterDirection,
    BwCounterResult,
    LatencyResult,
)
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)


class PerformanceManager:
    """Performance monitoring operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def bw_get(
        self, phys_port_ids: list[int], clear: bool = False
    ) -> list[BwCounterResult]:
        """Get bandwidth counters for specific ports.

        Args:
            phys_port_ids: List of physical port IDs.
            clear: If True, clear counters after reading.

        Returns:
            List of bandwidth counter results.
        """
        nr_ports = len(phys_port_ids)
        port_ids_arr = (c_int * nr_ports)(*phys_port_ids)
        res_arr = (SwitchtecBwCntrRes * nr_ports)()

        ret = self._dev.lib.switchtec_bwcntr_many(
            self._dev.handle, nr_ports, port_ids_arr, int(clear), res_arr
        )
        check_error(ret, "bwcntr_many")

        results: list[BwCounterResult] = []
        for i in range(nr_ports):
            r = res_arr[i]
            results.append(BwCounterResult(
                time_us=r.time_us,
                egress=BwCounterDirection(
                    posted=r.egress.posted,
                    comp=r.egress.comp,
                    nonposted=r.egress.nonposted,
                ),
                ingress=BwCounterDirection(
                    posted=r.ingress.posted,
                    comp=r.ingress.comp,
                    nonposted=r.ingress.nonposted,
                ),
            ))
        return results

    def lat_setup(
        self, egress_port_id: int, ingress_port_id: int, clear: bool = False
    ) -> None:
        """Configure latency measurement between two ports."""
        ret = self._dev.lib.switchtec_lat_setup(
            self._dev.handle, egress_port_id, ingress_port_id, int(clear)
        )
        check_error(ret, "lat_setup")

    def lat_get(
        self, egress_port_id: int, clear: bool = False
    ) -> LatencyResult:
        """Get latency measurement result.

        Args:
            egress_port_id: Egress port ID.
            clear: If True, clear counters after reading.

        Returns:
            Latency measurement result.
        """
        cur_ns = c_int()
        max_ns = c_int()

        ret = self._dev.lib.switchtec_lat_get(
            self._dev.handle, int(clear), egress_port_id,
            ctypes.byref(cur_ns), ctypes.byref(max_ns),
        )
        check_error(ret, "lat_get")

        return LatencyResult(
            egress_port_id=egress_port_id,
            current_ns=cur_ns.value,
            max_ns=max_ns.value,
        )
