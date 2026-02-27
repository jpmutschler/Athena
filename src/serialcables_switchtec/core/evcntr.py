"""Event counter management for BER testing and error monitoring."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from serialcables_switchtec.bindings.types import SwitchtecEvCntrSetup
from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.models.evcntr import EvCntrSetupResult, EvCntrValue
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)

MAX_EVENT_COUNTERS = 64


class EventCounterManager:
    """Event counter operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    @staticmethod
    def _validate_counter_range(counter_id: int, nr_counters: int) -> None:
        """Validate counter_id + nr_counters does not exceed MAX_EVENT_COUNTERS."""
        if counter_id + nr_counters > MAX_EVENT_COUNTERS:
            raise ValueError(
                f"counter_id ({counter_id}) + nr_counters ({nr_counters}) "
                f"exceeds maximum ({MAX_EVENT_COUNTERS})"
            )

    def setup(
        self,
        stack_id: int,
        counter_id: int,
        port_mask: int,
        type_mask: int,
        *,
        egress: bool = False,
        threshold: int = 0,
    ) -> None:
        """Configure an event counter.

        Args:
            stack_id: Stack ID (0-7).
            counter_id: Counter ID within the stack.
            port_mask: Bitmask of ports to count on.
            type_mask: Bitmask of event types to count.
            egress: If True, count egress; otherwise count ingress.
            threshold: Threshold for interrupt generation.
        """
        setup = SwitchtecEvCntrSetup()
        setup.port_mask = port_mask
        setup.type_mask = type_mask
        setup.egress = int(egress)
        setup.threshold = threshold

        ret = self._dev.lib.switchtec_evcntr_setup(
            self._dev.handle, stack_id, counter_id, ctypes.byref(setup),
        )
        check_error(ret, "evcntr_setup")
        logger.info(
            "evcntr_setup",
            stack_id=stack_id, counter=counter_id,
            type_mask=hex(type_mask), egress=egress,
        )

    def get_setup(
        self, stack_id: int, counter_id: int, nr_counters: int = 1,
    ) -> list[EvCntrSetupResult]:
        """Read the setup configuration of one or more counters.

        Args:
            stack_id: Stack ID.
            counter_id: Starting counter ID.
            nr_counters: Number of consecutive counters to read.

        Returns:
            List of counter setup configurations.
        """
        self._validate_counter_range(counter_id, nr_counters)
        setups = (SwitchtecEvCntrSetup * nr_counters)()
        ret = self._dev.lib.switchtec_evcntr_get_setup(
            self._dev.handle, stack_id, counter_id, nr_counters, setups,
        )
        check_error(ret, "evcntr_get_setup")
        return [
            EvCntrSetupResult(
                port_mask=setups[i].port_mask,
                type_mask=setups[i].type_mask,
                egress=bool(setups[i].egress),
                threshold=setups[i].threshold,
            )
            for i in range(nr_counters)
        ]

    def get_counts(
        self,
        stack_id: int,
        counter_id: int,
        nr_counters: int = 1,
        *,
        clear: bool = False,
    ) -> list[int]:
        """Read event counter values.

        Args:
            stack_id: Stack ID.
            counter_id: Starting counter ID.
            nr_counters: Number of consecutive counters to read.
            clear: If True, clear counters after reading.

        Returns:
            List of counter values.
        """
        self._validate_counter_range(counter_id, nr_counters)
        counts = (ctypes.c_uint * nr_counters)()
        ret = self._dev.lib.switchtec_evcntr_get(
            self._dev.handle, stack_id, counter_id, nr_counters,
            counts, int(clear),
        )
        check_error(ret, "evcntr_get")
        return [counts[i] for i in range(nr_counters)]

    def get_both(
        self,
        stack_id: int,
        counter_id: int,
        nr_counters: int = 1,
        *,
        clear: bool = False,
    ) -> list[EvCntrValue]:
        """Read both counter setup and values in one call.

        Args:
            stack_id: Stack ID.
            counter_id: Starting counter ID.
            nr_counters: Number of consecutive counters to read.
            clear: If True, clear counters after reading.

        Returns:
            List of EvCntrValue with setup and count.
        """
        self._validate_counter_range(counter_id, nr_counters)
        setups = (SwitchtecEvCntrSetup * nr_counters)()
        counts = (ctypes.c_uint * nr_counters)()
        ret = self._dev.lib.switchtec_evcntr_get_both(
            self._dev.handle, stack_id, counter_id, nr_counters,
            setups, counts, int(clear),
        )
        check_error(ret, "evcntr_get_both")
        return [
            EvCntrValue(
                counter_id=counter_id + i,
                count=counts[i],
                setup=EvCntrSetupResult(
                    port_mask=setups[i].port_mask,
                    type_mask=setups[i].type_mask,
                    egress=bool(setups[i].egress),
                    threshold=setups[i].threshold,
                ),
            )
            for i in range(nr_counters)
        ]

    def wait(self, timeout_ms: int = 5000) -> int:
        """Wait for an event counter to reach its threshold.

        Args:
            timeout_ms: Timeout in milliseconds.

        Returns:
            Return code from the wait operation.
        """
        ret = self._dev.lib.switchtec_evcntr_wait(self._dev.handle, timeout_ms)
        check_error(ret, "evcntr_wait")
        return ret
