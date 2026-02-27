"""Fabric topology management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.core.fabric import FabricManager
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
    dev = get_device(device_id)
    try:
        mgr = FabricManager(dev)
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
        mgr = FabricManager(dev)
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
        mgr = FabricManager(dev)
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
    dev = get_device(device_id)
    try:
        mgr = FabricManager(dev)
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
    dev = get_device(device_id)
    try:
        mgr = FabricManager(dev)
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
        mgr = FabricManager(dev)
        mgr.clear_gfms_events()
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "clear_gfms_events")
