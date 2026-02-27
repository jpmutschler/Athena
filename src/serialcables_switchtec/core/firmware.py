"""Firmware management for Switchtec devices."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from serialcables_switchtec.exceptions import InvalidParameterError, check_error
from serialcables_switchtec.models.firmware import FwPartSummary
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)

MAX_FW_READ_LENGTH = 16 * 1024 * 1024  # 16 MB


class FirmwareManager:
    """Manages firmware operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def get_fw_version(self) -> str:
        """Get the current firmware version string."""
        return self._dev.get_fw_version()

    def toggle_active_partition(
        self,
        *,
        toggle_bl2: bool = False,
        toggle_key: bool = False,
        toggle_fw: bool = True,
        toggle_cfg: bool = True,
        toggle_riotcore: bool = False,
    ) -> None:
        """Toggle the active firmware partition.

        Args:
            toggle_bl2: Toggle BL2 partition.
            toggle_key: Toggle key partition.
            toggle_fw: Toggle firmware partition.
            toggle_cfg: Toggle config partition.
            toggle_riotcore: Toggle RIoT Core partition.
        """
        ret = self._dev.lib.switchtec_fw_toggle_active_partition(
            self._dev.handle,
            int(toggle_bl2),
            int(toggle_key),
            int(toggle_fw),
            int(toggle_cfg),
            int(toggle_riotcore),
        )
        check_error(ret, "fw_toggle_active_partition")
        logger.info(
            "firmware_partition_toggled",
            fw=toggle_fw,
            cfg=toggle_cfg,
        )

    def is_boot_ro(self) -> bool:
        """Check if boot partition is read-only.

        Returns:
            True if boot partition is read-only, False otherwise.
        """
        result = self._dev.lib.switchtec_fw_is_boot_ro(self._dev.handle)
        return bool(result)

    def set_boot_ro(self, *, read_only: bool = True) -> None:
        """Set boot partition read-only flag.

        Args:
            read_only: If True, set boot partition to read-only.
        """
        ret = self._dev.lib.switchtec_fw_set_boot_ro(
            self._dev.handle,
            int(read_only),
        )
        check_error(ret, "fw_set_boot_ro")
        logger.info("boot_ro_set", read_only=read_only)

    def read_firmware(self, address: int, length: int) -> bytes:
        """Read raw firmware data from a given address.

        Args:
            address: Start address to read from.
            length: Number of bytes to read.

        Returns:
            Raw firmware data as bytes.

        Raises:
            InvalidParameterError: If address or length is out of range.
        """
        if address < 0:
            raise InvalidParameterError(
                "Firmware read address must be non-negative"
            )
        if length <= 0 or length > MAX_FW_READ_LENGTH:
            raise InvalidParameterError(
                f"Firmware read length must be between 1 and "
                f"{MAX_FW_READ_LENGTH}"
            )
        buf = ctypes.create_string_buffer(length)
        ret = self._dev.lib.switchtec_fw_read(
            self._dev.handle,
            address,
            length,
            buf,
        )
        check_error(ret, "fw_read")
        return buf.raw

    def get_part_summary(self) -> FwPartSummary:
        """Get a summary of all firmware partitions.

        Note: This is a simplified version. The full C struct
        contains flexible array members that are complex to
        marshal via ctypes. For now, we return the boot RO status.

        Returns:
            FwPartSummary with boot read-only status populated.
        """
        is_ro = self.is_boot_ro()
        return FwPartSummary(is_boot_ro=is_ro)
