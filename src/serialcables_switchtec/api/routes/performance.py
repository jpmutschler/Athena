"""Performance monitoring API routes.

Provides bandwidth and latency measurement for Switchtec PCIe switch ports.
Bandwidth counters are hardware registers that accumulate posted, completion,
and non-posted TLP byte counts per port.  Latency measurement requires a
two-step workflow: first configure the measurement path with the setup
endpoint, then read the result.

All counters support an optional ``clear`` flag.  When ``clear=true``, the
hardware counters are atomically read and then zeroed (clear-on-read
semantics), which is useful for computing deltas between successive polls.
When ``clear=false`` (the default), the counters continue to accumulate.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel, Field, field_validator

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.performance import BwCounterResult, LatencyResult

router = APIRouter()


class BwRequest(BaseModel):
    port_ids: list[int] = Field(min_length=1, max_length=60)
    clear: bool = False

    @field_validator("port_ids")
    @classmethod
    def validate_port_ids(cls, v: list[int]) -> list[int]:
        for pid in v:
            if not (0 <= pid <= 59):
                raise ValueError(f"port_id {pid} out of range 0-59")
        return v


@router.post(
    "/{device_id}/perf/bw",
    response_model=list[BwCounterResult],
)
def get_bandwidth(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: BwRequest = ...,
) -> list[BwCounterResult]:
    """Read bandwidth counters for one or more physical ports.

    Returns a ``BwCounterResult`` per requested port.  Each result contains:

    - ``time_us`` -- the elapsed time in microseconds over which the
      counters accumulated (meaningful only after a clear-and-re-read
      cycle).
    - ``egress`` -- a ``BwCounterDirection`` with ``posted``, ``comp``,
      ``nonposted``, and computed ``total`` byte counts for traffic leaving
      the switch on this port.
    - ``ingress`` -- the same breakdown for traffic entering the switch.

    Request body fields:

    - ``port_ids`` -- list of physical port IDs to query (1-60 entries,
      each in range 0-59).
    - ``clear`` -- when ``true``, counters are atomically read and then
      zeroed (clear-on-read).  Defaults to ``false``.

    The results array preserves the same ordering as the input ``port_ids``
    list.

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- port ID out of range or empty list.
    - **500 Internal Server Error** -- MRPC call failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.performance
        return mgr.bw_get(request.port_ids, clear=request.clear)
    except Exception as e:
        raise_on_error(e, "bw_get")


class LatSetupRequest(BaseModel):
    egress_port_id: int = Field(ge=0, le=59)
    ingress_port_id: int = Field(ge=0, le=59)
    clear: bool = False


@router.post("/{device_id}/perf/latency/setup")
def latency_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    request: LatSetupRequest = ...,
) -> dict[str, str]:
    """Configure the latency measurement path between an egress and ingress port.

    This must be called before reading latency with ``GET .../latency/{port}``.
    The switch firmware will begin measuring round-trip latency for TLPs
    traversing from ``ingress_port_id`` to ``egress_port_id``.

    Request body fields:

    - ``egress_port_id`` -- physical port ID of the egress side (0-59).
    - ``ingress_port_id`` -- physical port ID of the ingress side (0-59).
    - ``clear`` -- when ``true``, the accumulated min/max/current latency
      registers are zeroed before measurement begins.  Defaults to ``false``.

    Response format::

        {"status": "configured"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- port ID out of range.
    - **500 Internal Server Error** -- firmware rejected the setup.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.performance
        mgr.lat_setup(
            request.egress_port_id,
            request.ingress_port_id,
            clear=request.clear,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "lat_setup")


@router.get(
    "/{device_id}/perf/latency/{egress_port_id}",
    response_model=LatencyResult,
)
def get_latency(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    egress_port_id: int = Path(ge=0, le=59),
    clear: bool = Query(default=False),
) -> LatencyResult:
    """Read the current latency measurement for a previously configured egress port.

    The latency setup endpoint (``POST .../latency/setup``) must have been
    called first to establish the measurement path.

    Returns a ``LatencyResult`` with:

    - ``egress_port_id`` -- the port whose latency was measured.
    - ``current_ns`` -- the most recent measured latency in nanoseconds.
    - ``max_ns`` -- the maximum latency observed since the last clear.

    Parameters:

    - ``device_id`` -- the identifier assigned when the device was opened.
    - ``egress_port_id`` (path) -- physical port ID (0-59).
    - ``clear`` (query) -- when ``true``, the latency registers are
      atomically read and zeroed (clear-on-read).  Defaults to ``false``.

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- port ID out of range.
    - **500 Internal Server Error** -- latency read failed (setup may not
      have been called).
    """
    dev = get_device(device_id)
    try:
        mgr = dev.performance
        return mgr.lat_get(egress_port_id, clear=clear)
    except Exception as e:
        raise_on_error(e, "lat_get")
