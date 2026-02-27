"""Firmware management for Switchtec devices."""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from serialcables_switchtec.bindings.constants import FwType, SwitchtecGen
from serialcables_switchtec.bindings.types import (
    SwitchtecFwImageInfo,
    SwitchtecFwPartSummary,
)
from serialcables_switchtec.exceptions import InvalidParameterError, check_error
from serialcables_switchtec.models.firmware import (
    FwImageInfo,
    FwPartitionInfo,
    FwPartSummary,
)
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)

MAX_FW_READ_LENGTH = 16 * 1024 * 1024  # 16 MB

# ctypes callback type for firmware write progress: void(int cur, int tot)
_FwProgressCallback = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int)


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

    def write_firmware(
        self,
        image_path: str | Path,
        *,
        dont_activate: bool = False,
        force: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        """Write a firmware image file to the device.

        Args:
            image_path: Path to the firmware image file.
            dont_activate: If True, don't activate the new firmware after write.
            force: If True, force write even if image appears incompatible.
            progress_callback: Optional callback(current_bytes, total_bytes).

        Raises:
            InvalidParameterError: If the image file does not exist.
        """
        path = Path(image_path)
        if not path.exists():
            raise InvalidParameterError(f"Firmware image not found: {path}")

        if progress_callback is not None:
            c_callback = _FwProgressCallback(progress_callback)
        else:
            c_callback = _FwProgressCallback(lambda cur, tot: None)

        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            ret = self._dev.lib.switchtec_fw_write_fd(
                self._dev.handle,
                fd,
                int(dont_activate),
                int(force),
                c_callback,
            )
            check_error(ret, "fw_write")
        finally:
            os.close(fd)

        logger.info(
            "firmware_written",
            image=str(path),
            dont_activate=dont_activate,
            force=force,
        )

    @staticmethod
    def _gen_str(gen_val: int) -> str:
        """Map C enum switchtec_gen value to a human-readable string."""
        try:
            return SwitchtecGen(gen_val).name
        except ValueError:
            return "UNKNOWN"

    @staticmethod
    def _type_str(type_val: int) -> str:
        """Map C enum switchtec_fw_type value to a human-readable string."""
        try:
            return FwType(type_val).name
        except ValueError:
            return "UNKNOWN"

    @staticmethod
    def _read_image_info(ptr: ctypes.POINTER(SwitchtecFwImageInfo)) -> FwImageInfo | None:
        """Dereference a pointer to SwitchtecFwImageInfo and return a Pydantic model.

        Returns None if the pointer is NULL.
        """
        if not ptr:
            return None
        info = ptr.contents
        return FwImageInfo(
            generation=FirmwareManager._gen_str(info.gen),
            partition_type=FirmwareManager._type_str(info.type),
            version=info.version.decode("utf-8", errors="replace").rstrip("\x00"),
            partition_addr=info.part_addr,
            partition_len=info.part_len,
            image_len=info.image_len,
            valid=bool(info.valid),
            active=bool(info.active),
            running=bool(info.running),
            read_only=bool(info.read_only),
        )

    @staticmethod
    def _read_part_type(part_type) -> FwPartitionInfo:
        """Read active/inactive pointers from a SwitchtecFwPartType."""
        return FwPartitionInfo(
            active=FirmwareManager._read_image_info(part_type.active),
            inactive=FirmwareManager._read_image_info(part_type.inactive),
        )

    def get_part_summary(self) -> FwPartSummary:
        """Get a summary of all firmware partitions.

        Calls the C library's switchtec_fw_part_summary() to retrieve
        full partition information including active/inactive images for
        all 9 partition types.

        Returns:
            FwPartSummary with all partition info populated.
        """
        raw_ptr = self._dev.lib.switchtec_fw_part_summary(self._dev.handle)
        if not raw_ptr:
            logger.warning("fw_part_summary returned NULL, falling back to boot-RO only")
            return FwPartSummary(is_boot_ro=self.is_boot_ro())

        try:
            summary = ctypes.cast(raw_ptr, ctypes.POINTER(SwitchtecFwPartSummary)).contents
            return FwPartSummary(
                boot=self._read_part_type(summary.boot),
                map=self._read_part_type(summary.map),
                img=self._read_part_type(summary.img),
                cfg=self._read_part_type(summary.cfg),
                nvlog=self._read_part_type(summary.nvlog),
                seeprom=self._read_part_type(summary.seeprom),
                key=self._read_part_type(summary.key),
                bl2=self._read_part_type(summary.bl2),
                riot=self._read_part_type(summary.riot),
                is_boot_ro=self.is_boot_ro(),
            )
        finally:
            self._dev.lib.switchtec_fw_part_summary_free(raw_ptr)
