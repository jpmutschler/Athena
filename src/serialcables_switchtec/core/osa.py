"""Ordered Set Analyzer (OSA) for capturing and analyzing ordered sets."""

from __future__ import annotations

import ctypes
from ctypes import c_uint32
from typing import TYPE_CHECKING

from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)


class OrderedSetAnalyzer:
    """Ordered Set Analyzer operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def start(self, stack_id: int) -> None:
        """Start OSA capture.

        Args:
            stack_id: Stack ID to capture on.
        """
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa(self._dev.handle, stack_id, 1)
        check_error(ret, "osa_start")
        logger.info("osa_started", stack_id=stack_id)

    def stop(self, stack_id: int) -> None:
        """Stop OSA capture."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa(self._dev.handle, stack_id, 0)
        check_error(ret, "osa_stop")
        logger.info("osa_stopped", stack_id=stack_id)

    def configure_type(
        self,
        stack_id: int,
        direction: int,
        lane_mask: int,
        link_rate: int,
        os_types: int,
    ) -> None:
        """Configure OSA ordered set type filter.

        Args:
            stack_id: Stack ID.
            direction: 0=RX, 1=TX.
            lane_mask: Bitmask of lanes to monitor.
            link_rate: Link rate enum value.
            os_types: Ordered set type filter bitmask.
        """
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa_config_type(
                self._dev.handle, stack_id, direction, lane_mask, link_rate, os_types
            )
        check_error(ret, "osa_config_type")

    def configure_pattern(
        self,
        stack_id: int,
        direction: int,
        lane_mask: int,
        link_rate: int,
        value_data: list[int],
        mask_data: list[int],
    ) -> None:
        """Configure OSA pattern match filter.

        Args:
            stack_id: Stack ID.
            direction: 0=RX, 1=TX.
            lane_mask: Bitmask of lanes to monitor.
            link_rate: Link rate enum value.
            value_data: 4-DWORD pattern value.
            mask_data: 4-DWORD pattern mask.
        """
        val = (c_uint32 * 4)(*value_data[:4])
        msk = (c_uint32 * 4)(*mask_data[:4])

        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa_config_pattern(
                self._dev.handle, stack_id, direction, lane_mask, link_rate, val, msk
            )
        check_error(ret, "osa_config_pattern")

    def capture_control(
        self,
        stack_id: int,
        lane_mask: int,
        direction: int,
        drop_single_os: int = 0,
        stop_mode: int = 0,
        snapshot_mode: int = 0,
        post_trigger: int = 0,
        os_types: int = 0,
    ) -> None:
        """Configure OSA capture control parameters.

        Args:
            stack_id: Stack ID.
            lane_mask: Bitmask of lanes.
            direction: 0=RX, 1=TX.
            drop_single_os: Drop single ordered sets.
            stop_mode: Stop mode configuration.
            snapshot_mode: Snapshot mode configuration.
            post_trigger: Post-trigger entries.
            os_types: Ordered set type filter.
        """
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa_capture_control(
                self._dev.handle, stack_id, lane_mask, direction,
                drop_single_os, stop_mode, snapshot_mode,
                post_trigger, os_types,
            )
        check_error(ret, "osa_capture_control")

    def capture_data(
        self, stack_id: int, lane: int, direction: int
    ) -> int:
        """Read captured OSA data.

        Returns:
            Return code from the capture data command.
        """
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa_capture_data(
                self._dev.handle, stack_id, lane, direction
            )
        check_error(ret, "osa_capture_data")
        return ret

    def dump_config(self, stack_id: int) -> int:
        """Dump current OSA configuration."""
        with self._dev.device_op():
            ret = self._dev.lib.switchtec_osa_dump_conf(self._dev.handle, stack_id)
        check_error(ret, "osa_dump_conf")
        return ret
