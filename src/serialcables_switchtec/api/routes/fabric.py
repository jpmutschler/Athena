"""Fabric topology management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.rate_limit import csr_write_limiter, fabric_control_limiter
from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.models.fabric import (
    FabPortConfig,
    GfmsBindRequest,
    GfmsUnbindRequest,
)

router = APIRouter()




class PortControlRequest(BaseModel):
    phys_port_id: int = Field(ge=0, le=59)
    control_type: int = Field(ge=0, le=2)
    hot_reset_flag: int = Field(default=0, ge=0, le=1)


class SetPortConfigRequest(BaseModel):
    port_type: int = Field(default=0, ge=0, le=255)
    clock_source: int = Field(default=0, ge=0, le=255)
    clock_sris: int = Field(default=0, ge=0, le=255)
    hvd_inst: int = Field(default=0, ge=0, le=255)


@router.post("/{device_id}/fabric/port-control")
def port_control(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: PortControlRequest = ...,
) -> dict[str, str]:
    """Control a fabric port (enable/disable/hot-reset)."""
    fabric_control_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.port_control(
            phys_port_id=request.phys_port_id,
            control_type=FabPortControlType(request.control_type),
            hot_reset_flag=FabHotResetFlag(request.hot_reset_flag),
        )
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "port_control")


@router.get(
    "/{device_id}/fabric/port-config/{port_id}",
    response_model=FabPortConfig,
)
def get_port_config(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
) -> FabPortConfig:
    """Get configuration for a fabric port."""
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        return mgr.get_port_config(port_id)
    except Exception as e:
        raise_on_error(e, "get_port_config")


@router.post("/{device_id}/fabric/port-config/{port_id}")
def set_port_config(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    port_id: int = Path(ge=0, le=59),
    request: SetPortConfigRequest = ...,
) -> dict[str, str]:
    """Set configuration for a fabric port."""
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        config = FabPortConfig(
            phys_port_id=port_id,
            port_type=request.port_type,
            clock_source=request.clock_source,
            clock_sris=request.clock_sris,
            hvd_inst=request.hvd_inst,
        )
        mgr.set_port_config(config)
        return {"status": "ok"}
    except Exception as e:
        raise_on_error(e, "set_port_config")


@router.post("/{device_id}/fabric/bind")
def gfms_bind(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: GfmsBindRequest = ...,
) -> dict[str, str]:
    """Bind a host port to an endpoint port via GFMS."""
    fabric_control_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.bind(request)
        return {"status": "bound"}
    except Exception as e:
        raise_on_error(e, "gfms_bind")


@router.post("/{device_id}/fabric/unbind")
def gfms_unbind(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: GfmsUnbindRequest = ...,
) -> dict[str, str]:
    """Unbind a host port from an endpoint port via GFMS."""
    fabric_control_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.unbind(request)
        return {"status": "unbound"}
    except Exception as e:
        raise_on_error(e, "gfms_unbind")


@router.post("/{device_id}/fabric/clear-events")
def clear_gfms_events(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
) -> dict[str, str]:
    """Clear all GFMS events."""
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.clear_gfms_events()
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "clear_gfms_events")


# --- Config Space Read/Write ------------------------------------------------


class CsrWriteRequest(BaseModel):
    addr: int = Field(ge=0, le=0xFFF)
    value: int = Field(ge=0)
    width: int = Field(default=32)

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        if v not in (8, 16, 32):
            raise ValueError("width must be 8, 16, or 32")
        return v

    @model_validator(mode="after")
    def validate_value_and_alignment(self) -> "CsrWriteRequest":
        max_val = (1 << self.width) - 1
        if self.value > max_val:
            raise ValueError(
                f"value 0x{self.value:x} exceeds {self.width}-bit maximum 0x{max_val:x}"
            )
        if self.width == 16 and (self.addr & 0x1):
            raise ValueError(
                f"16-bit CSR access requires even address, got 0x{self.addr:x}"
            )
        if self.width == 32 and (self.addr & 0x3):
            raise ValueError(
                f"32-bit CSR access requires 4-byte aligned address, got 0x{self.addr:x}"
            )
        return self


@router.get("/{device_id}/fabric/csr/{pdfid}")
def csr_read(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    pdfid: int = Path(ge=0, le=0xFFFF),
    addr: int = Query(ge=0, le=0xFFF),
    width: int = Query(default=32),
) -> dict[str, object]:
    """Read an endpoint PCIe config space register."""
    if width not in (8, 16, 32):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="width must be 8, 16, or 32")
    if width == 16 and (addr & 0x1):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"16-bit CSR access requires even address, got 0x{addr:x}",
        )
    if width == 32 and (addr & 0x3):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=f"32-bit CSR access requires 4-byte aligned address, got 0x{addr:x}",
        )
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        value = mgr.csr_read(pdfid, addr, width)
        return {
            "pdfid": pdfid,
            "addr": addr,
            "width": width,
            "value": value,
        }
    except Exception as e:
        raise_on_error(e, "csr_read")


@router.post("/{device_id}/fabric/csr/{pdfid}")
def csr_write(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    pdfid: int = Path(ge=0, le=0xFFFF),
    request: CsrWriteRequest = ...,
) -> dict[str, str]:
    """Write an endpoint PCIe config space register."""
    csr_write_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.csr_write(pdfid, request.addr, request.value, request.width)
        return {"status": "written"}
    except Exception as e:
        raise_on_error(e, "csr_write")
