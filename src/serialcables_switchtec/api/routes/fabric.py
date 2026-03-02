"""Fabric topology management API routes.

Provides control-plane operations for the Switchtec PCIe fabric including
port enable/disable/hot-reset, port configuration, GFMS bind/unbind for
SR-IOV and multi-host topologies, and direct PCIe Configuration Space
Register (CSR) read/write access.

**Port control** operations (enable, disable, hot-reset) and **GFMS
bind/unbind** are rate-limited to 5 calls per device per 60 seconds via
``fabric_control_limiter``.

**CSR writes** are separately rate-limited to 5 calls per device per
60 seconds via ``csr_write_limiter``.  CSR reads are not rate-limited.

CSR access supports 8-bit, 16-bit, and 32-bit widths.  16-bit accesses
require 2-byte-aligned addresses; 32-bit accesses require 4-byte-aligned
addresses.  The valid address range is 0x000-0xFFF (standard PCIe
configuration space), or 0x000-0xFFFF (extended) when ``extended=true``
is specified.  Extended access uses the Switchtec MRPC tunneled config
path rather than host ECAM.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.api.rate_limit import csr_write_limiter, fabric_control_limiter
from serialcables_switchtec.bindings.constants import (
    PCIE_CFG_SPACE_EXTENDED,
    PCIE_CFG_SPACE_STANDARD,
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
    """Issue a port control command: enable, disable, or hot-reset a fabric port.

    Rate limit: 5 calls per device per 60 seconds.

    Request body fields:

    - ``phys_port_id`` -- physical port number to control (0-59).
    - ``control_type`` -- the operation to perform:
      - ``0`` (DISABLE) -- administratively disable the port.
      - ``1`` (ENABLE) -- enable the port and trigger link training.
      - ``2`` (HOT_RESET) -- issue a PCIe hot reset on the port.
    - ``hot_reset_flag`` -- modifier for hot-reset behavior:
      - ``0`` (NONE) -- standard in-band hot reset.
      - ``1`` (PERST) -- assert PERST# for a fundamental reset.
      Defaults to ``0``.  Only meaningful when ``control_type`` is ``2``.

    Response format::

        {"status": "ok"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **429 Too Many Requests** -- rate limit exceeded.
    - **500 Internal Server Error** -- port control command failed.
    """
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
    """Read the current fabric configuration for a physical port.

    Returns a ``FabPortConfig`` object with:

    - ``phys_port_id`` -- the queried port number.
    - ``port_type`` -- port type code (e.g. upstream, downstream, fabric).
    - ``clock_source`` -- reference clock source identifier.
    - ``clock_sris`` -- SRIS (Separate Reference clock with Independent
      Spread) configuration.
    - ``hvd_inst`` -- HVD (Host Virtual Domain) instance assignment.

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``port_id`` (path) -- physical port number (0-59).

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- port_id out of range.
    - **500 Internal Server Error** -- configuration read failed.
    """
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
    """Write a new fabric configuration to a physical port.

    Overwrites the port's configuration with the values provided in the
    request body.  Changes typically take effect after the next link
    re-training or device reset.

    Request body fields:

    - ``port_type`` -- port type code (0-255).  Default ``0``.
    - ``clock_source`` -- reference clock source (0-255).  Default ``0``.
    - ``clock_sris`` -- SRIS mode (0-255).  Default ``0``.
    - ``hvd_inst`` -- HVD instance (0-255).  Default ``0``.

    Parameters:

    - ``device_id`` -- the registered device identifier.
    - ``port_id`` (path) -- physical port number (0-59).

    Response format::

        {"status": "ok"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- configuration write failed.
    """
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
    """Bind a host port to one or more endpoint functions via GFMS.

    The Global Fabric Management Service (GFMS) controls which host
    partitions can see which downstream endpoint functions.  This endpoint
    creates a binding so the specified host port can enumerate the target
    endpoint PDFIDs (Physical Device Function IDs).

    Rate limit: 5 calls per device per 60 seconds.

    Request body fields:

    - ``host_sw_idx`` -- index of the host switch in the fabric (0-255).
    - ``host_phys_port_id`` -- physical port on the host switch (0-255).
    - ``host_log_port_id`` -- logical port on the host switch (0-255).
    - ``ep_number`` -- number of endpoint functions to bind.  Default ``0``.
    - ``ep_pdfid`` -- list of endpoint PDFID values to bind (max 8 entries).

    Response format::

        {"status": "bound"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range or too many PDFIDs.
    - **429 Too Many Requests** -- rate limit exceeded.
    - **500 Internal Server Error** -- GFMS bind command failed (e.g. the
      endpoint is already bound to another host).
    """
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
    """Remove a GFMS binding between a host port and an endpoint function.

    Removes the visibility of the specified endpoint PDFID from the host
    port.  After unbinding, the host will no longer enumerate the endpoint
    until a new bind is issued.

    Rate limit: 5 calls per device per 60 seconds.

    Request body fields:

    - ``host_sw_idx`` -- index of the host switch in the fabric (0-255).
    - ``host_phys_port_id`` -- physical port on the host switch (0-255).
    - ``host_log_port_id`` -- logical port on the host switch (0-255).
    - ``pdfid`` -- the endpoint PDFID to unbind (0-65535).  Default ``0``.
    - ``option`` -- unbind option flags (0-255).  Default ``0``.

    Response format::

        {"status": "unbound"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **429 Too Many Requests** -- rate limit exceeded.
    - **500 Internal Server Error** -- GFMS unbind command failed.
    """
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
    """Clear all pending GFMS (Global Fabric Management Service) events.

    GFMS events are generated by bind/unbind operations, link state changes
    within the fabric, and topology discovery.  This endpoint resets the
    event queue so subsequent queries only see newly generated events.

    Parameters:

    - ``device_id`` -- the registered device identifier.

    Response format::

        {"status": "cleared"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **500 Internal Server Error** -- event clear command failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.clear_gfms_events()
        return {"status": "cleared"}
    except Exception as e:
        raise_on_error(e, "clear_gfms_events")


# --- Config Space Read/Write ------------------------------------------------


class CsrWriteRequest(BaseModel):
    addr: int = Field(ge=0, le=PCIE_CFG_SPACE_EXTENDED)
    value: int = Field(ge=0)
    width: int = Field(default=32)
    extended: bool = Field(default=False)

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: int) -> int:
        if v not in (8, 16, 32):
            raise ValueError("width must be 8, 16, or 32")
        return v

    @model_validator(mode="after")
    def validate_value_and_alignment(self) -> "CsrWriteRequest":
        addr_limit = PCIE_CFG_SPACE_EXTENDED if self.extended else PCIE_CFG_SPACE_STANDARD
        if self.addr > addr_limit:
            raise ValueError(
                f"addr 0x{self.addr:x} exceeds {'extended' if self.extended else 'standard'} "
                f"config space limit 0x{addr_limit:X}"
            )
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
    addr: int = Query(
        ge=0,
        le=PCIE_CFG_SPACE_EXTENDED,
        description=(
            "Register byte offset. Limited to 0x000-0xFFF (standard config space) "
            "unless extended=true, which allows 0x000-0xFFFF."
        ),
    ),
    width: int = Query(default=32),
    extended: bool = Query(
        default=False,
        description="Allow extended config space addresses (0x000-0xFFFF).",
    ),
) -> dict[str, object]:
    """Read a PCIe Configuration Space Register (CSR) from an endpoint.

    Performs a configuration-space read targeting the endpoint identified by
    its PDFID (Physical Device Function ID).  By default the address must
    fall within the standard 4 KB PCIe configuration space (0x000-0xFFF).
    Pass ``extended=true`` to access the 64 KB extended configuration space
    (0x000-0xFFFF) via ECAM.

    Parameters:

    - ``device_id`` (path) -- the registered device identifier.
    - ``pdfid`` (path) -- target endpoint PDFID (0-65535).
    - ``addr`` (query) -- register byte offset.
    - ``width`` (query) -- access width in bits: ``8``, ``16``, or ``32``.
      Default ``32``.  16-bit reads require even-aligned addresses; 32-bit
      reads require 4-byte-aligned addresses.
    - ``extended`` (query) -- if ``true``, allow extended config space
      addresses (0x000-0xFFFF).  Default ``false``.

    Response format::

        {"pdfid": 256, "addr": 0, "width": 32, "value": 440810036}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- invalid width or address alignment.
    - **500 Internal Server Error** -- CSR read failed.
    """
    from fastapi import HTTPException  # noqa: PLC0415

    addr_limit = PCIE_CFG_SPACE_EXTENDED if extended else PCIE_CFG_SPACE_STANDARD
    if addr > addr_limit:
        raise HTTPException(
            status_code=422,
            detail=(
                f"addr 0x{addr:x} exceeds {'extended' if extended else 'standard'} "
                f"config space limit 0x{addr_limit:X}"
            ),
        )
    if width not in (8, 16, 32):
        raise HTTPException(status_code=422, detail="width must be 8, 16, or 32")
    if width == 16 and (addr & 0x1):
        raise HTTPException(
            status_code=422,
            detail=f"16-bit CSR access requires even address, got 0x{addr:x}",
        )
    if width == 32 and (addr & 0x3):
        raise HTTPException(
            status_code=422,
            detail=f"32-bit CSR access requires 4-byte aligned address, got 0x{addr:x}",
        )
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        value = mgr.csr_read(pdfid, addr, width, extended=extended)
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
    """Write a value to a PCIe Configuration Space Register (CSR) on an endpoint.

    Performs a configuration-space write targeting the endpoint identified by
    its PDFID.  This is a potentially destructive operation that can alter
    endpoint behavior, BAR mappings, or link parameters.

    Rate limit: 5 calls per device per 60 seconds.

    Parameters:

    - ``device_id`` (path) -- the registered device identifier.
    - ``pdfid`` (path) -- target endpoint PDFID (0-65535).

    Request body fields:

    - ``addr`` -- register byte offset (0x000-0xFFF standard, 0x000-0xFFFF
      when ``extended`` is true).
    - ``value`` -- the value to write, which must fit within ``width`` bits.
    - ``width`` -- access width in bits: ``8``, ``16``, or ``32``.
      Default ``32``.  16-bit writes require even-aligned addresses; 32-bit
      writes require 4-byte-aligned addresses.  The ``value`` is validated
      to not exceed the maximum for the chosen width.
    - ``extended`` -- if ``true``, allow extended config space addresses
      (0x000-0xFFFF).  Default ``false``.

    Response format::

        {"status": "written"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- invalid width, alignment, or value overflow.
    - **429 Too Many Requests** -- rate limit exceeded.
    - **500 Internal Server Error** -- CSR write failed.
    """
    csr_write_limiter.check(device_id)
    dev = get_device(device_id)
    try:
        mgr = dev.fabric
        mgr.csr_write(
            pdfid, request.addr, request.value, request.width,
            extended=request.extended,
        )
        return {"status": "written"}
    except Exception as e:
        raise_on_error(e, "csr_write")
