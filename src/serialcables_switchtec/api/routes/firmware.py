"""Firmware management API routes.

Provides firmware lifecycle operations for Switchtec devices including
version queries, partition management, boot-protection control, and
firmware image upload.

Switchtec devices maintain dual firmware partitions (active and inactive)
for each image type (boot, map, img, cfg, nvlog, seeprom, key, bl2, riot).
The ``toggle`` endpoint swaps which partition is active so the next reset
boots the alternate image.  The ``boot-ro`` endpoints control whether the
boot partition is write-protected.

Firmware uploads are streamed to a temporary file and limited to 64 MB
(``MAX_FIRMWARE_UPLOAD_SIZE``).  The actual write is performed in a
dedicated 2-thread pool to avoid blocking the main event loop.
"""

from __future__ import annotations

import asyncio
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path as FilePath

from fastapi import APIRouter, HTTPException, Path, UploadFile
from pydantic import BaseModel

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.firmware import FwPartSummary

router = APIRouter()

_firmware_write_executor = ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="fw-write"
)

MAX_FIRMWARE_UPLOAD_SIZE = 64 * 1024 * 1024  # 64 MB




class TogglePartitionRequest(BaseModel):
    toggle_bl2: bool = False
    toggle_key: bool = False
    toggle_fw: bool = True
    toggle_cfg: bool = True
    toggle_riotcore: bool = False


class SetBootRoRequest(BaseModel):
    read_only: bool = True


@router.get("/{device_id}/firmware/version")
def get_fw_version(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Retrieve the firmware version string of the currently running image.

    Returns the version reported by the active firmware partition, typically
    in the format ``"X.YY BZZZ"`` (e.g. ``"4.70 B536"``).

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Response format::

        {"version": "4.70 B536"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- version read failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.firmware
        version = mgr.get_fw_version()
        return {"version": version}
    except Exception as e:
        raise_on_error(e, "get_fw_version")


@router.post("/{device_id}/firmware/toggle")
def toggle_active_partition(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: TogglePartitionRequest = ...,
) -> dict[str, str]:
    """Toggle which firmware partition (active vs. inactive) will boot next.

    Switchtec devices maintain A/B partition pairs for each firmware image
    type.  This endpoint flips the active flag for selected partition types
    so the device boots from the alternate image on the next reset.

    Request body fields (all default to the most common upgrade scenario):

    - ``toggle_bl2`` -- toggle the second-stage bootloader.  Default ``false``.
    - ``toggle_key`` -- toggle the key manifest partition.  Default ``false``.
    - ``toggle_fw`` -- toggle the main firmware image.  Default ``true``.
    - ``toggle_cfg`` -- toggle the configuration partition.  Default ``true``.
    - ``toggle_riotcore`` -- toggle the RIoT core partition.  Default ``false``.

    A hard reset (or power cycle) is required after toggling for the new
    partition selection to take effect.

    Response format::

        {"status": "toggled"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- toggle command failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.firmware
        mgr.toggle_active_partition(
            toggle_bl2=request.toggle_bl2,
            toggle_key=request.toggle_key,
            toggle_fw=request.toggle_fw,
            toggle_cfg=request.toggle_cfg,
            toggle_riotcore=request.toggle_riotcore,
        )
        return {"status": "toggled"}
    except Exception as e:
        raise_on_error(e, "toggle_active_partition")


@router.get("/{device_id}/firmware/boot-ro")
def get_boot_ro(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, bool]:
    """Check whether the boot partition is currently write-protected.

    When boot-RO is enabled, the active boot partition cannot be
    overwritten by a firmware write operation, protecting the device from
    accidental bricking during firmware updates.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Response format::

        {"read_only": true}

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- status query failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.firmware
        ro = mgr.is_boot_ro()
        return {"read_only": ro}
    except Exception as e:
        raise_on_error(e, "get_boot_ro")


@router.post("/{device_id}/firmware/boot-ro")
def set_boot_ro(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: SetBootRoRequest = ...,
) -> dict[str, str]:
    """Set or clear the boot partition write-protection flag.

    When ``read_only`` is ``true``, subsequent firmware write operations
    will be prevented from modifying the boot partition, protecting the
    device from accidental bricking.  Setting it to ``false`` re-enables
    boot partition writes.

    Request body fields:

    - ``read_only`` -- ``true`` to enable write protection, ``false`` to
      disable it.  Defaults to ``true``.

    Response format::

        {"status": "ok"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- the set-boot-RO command failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.firmware
        mgr.set_boot_ro(read_only=request.read_only)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "set_boot_ro")


@router.post("/{device_id}/firmware/write")
async def write_firmware(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    file: UploadFile = ...,
    dont_activate: bool = False,
    force: bool = False,
) -> dict[str, str]:
    """Upload and write a firmware image to the device via multipart form data.

    The firmware binary is streamed in 64 KB chunks to a temporary file,
    validated against the 64 MB size limit, and then written to the device's
    inactive partition by a dedicated thread pool executor (2 workers) so
    the async event loop is not blocked during the flash operation.

    The temporary file is always cleaned up, even if the write fails.

    Parameters:

    - ``device_id`` (path) -- the registered device identifier.
    - ``file`` (multipart) -- the firmware binary file (.bin).
    - ``dont_activate`` (query) -- when ``true``, the newly written
      partition is **not** toggled to active after writing.  The caller must
      separately call the toggle endpoint and reset.  Default ``false``.
    - ``force`` (query) -- when ``true``, bypass firmware compatibility
      checks (e.g. generation mismatch).  Use with caution.  Default ``false``.

    Response format::

        {"status": "written", "filename": "PSX_FW_4.70_B536.bin"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **413 Request Entity Too Large** -- the uploaded file exceeds the
      64 MB limit (``MAX_FIRMWARE_UPLOAD_SIZE``).
    - **500 Internal Server Error** -- the flash write failed.
    """
    dev = get_device(device_id)
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".bin", delete=False
        ) as tmp:
            tmp_path = tmp.name
            total = 0
            chunk_size = 64 * 1024
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FIRMWARE_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Firmware image exceeds {MAX_FIRMWARE_UPLOAD_SIZE} byte limit",
                    )
                tmp.write(chunk)

        mgr = dev.firmware
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            _firmware_write_executor,
            partial(
                mgr.write_firmware,
                tmp_path,
                dont_activate=dont_activate,
                force=force,
            ),
        )
        return {"status": "written", "filename": file.filename or "unknown"}
    except HTTPException:
        raise
    except Exception as e:
        raise_on_error(e, "write_firmware")
    finally:
        if tmp_path is not None:
            FilePath(tmp_path).unlink(missing_ok=True)


@router.get(
    "/{device_id}/firmware/summary",
    response_model=FwPartSummary,
)
def get_fw_summary(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> FwPartSummary:
    """Retrieve a comprehensive summary of all firmware partition images.

    Returns a ``FwPartSummary`` containing active/inactive ``FwImageInfo``
    pairs for each partition type: ``boot``, ``map``, ``img``, ``cfg``,
    ``nvlog``, ``seeprom``, ``key``, ``bl2``, and ``riot``.

    Each ``FwImageInfo`` includes:

    - ``generation`` -- hardware generation this image targets.
    - ``partition_type`` -- partition category name.
    - ``version`` -- firmware version string.
    - ``partition_addr`` / ``partition_len`` -- flash address and size.
    - ``image_len`` -- actual image size within the partition.
    - ``valid`` -- whether the image CRC is valid.
    - ``active`` -- whether this is the active (boot-selected) image.
    - ``running`` -- whether this image is currently executing.
    - ``read_only`` -- whether this partition is write-protected.

    The top-level ``is_boot_ro`` field indicates the boot partition
    write-protection status.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- partition summary read failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.firmware
        return mgr.get_part_summary()
    except Exception as e:
        raise_on_error(e, "get_fw_summary")
