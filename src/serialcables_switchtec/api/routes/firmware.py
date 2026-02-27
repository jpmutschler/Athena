"""Firmware management API routes."""

from __future__ import annotations

import tempfile
from pathlib import Path as FilePath

from fastapi import APIRouter, HTTPException, Path, UploadFile
from pydantic import BaseModel

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.core.firmware import FirmwareManager
from serialcables_switchtec.models.firmware import FwPartSummary

router = APIRouter()

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
    """Get the current firmware version string."""
    dev = get_device(device_id)
    try:
        mgr = FirmwareManager(dev)
        version = mgr.get_fw_version()
        return {"version": version}
    except Exception as e:
        raise_on_error(e, "get_fw_version")


@router.post("/{device_id}/firmware/toggle")
def toggle_active_partition(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: TogglePartitionRequest = ...,
) -> dict[str, str]:
    """Toggle the active firmware partition."""
    dev = get_device(device_id)
    try:
        mgr = FirmwareManager(dev)
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
    """Check if boot partition is read-only."""
    dev = get_device(device_id)
    try:
        mgr = FirmwareManager(dev)
        ro = mgr.is_boot_ro()
        return {"read_only": ro}
    except Exception as e:
        raise_on_error(e, "get_boot_ro")


@router.post("/{device_id}/firmware/boot-ro")
def set_boot_ro(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: SetBootRoRequest = ...,
) -> dict[str, str]:
    """Set boot partition read-only flag."""
    dev = get_device(device_id)
    try:
        mgr = FirmwareManager(dev)
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
    """Write a firmware image to the device (multipart upload)."""
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

        mgr = FirmwareManager(dev)
        mgr.write_firmware(
            tmp_path,
            dont_activate=dont_activate,
            force=force,
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
    """Get a summary of all firmware partitions."""
    dev = get_device(device_id)
    try:
        mgr = FirmwareManager(dev)
        return mgr.get_part_summary()
    except Exception as e:
        raise_on_error(e, "get_fw_summary")
