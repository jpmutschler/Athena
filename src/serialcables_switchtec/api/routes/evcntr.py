"""Event counter API routes for BER testing and error monitoring.

Switchtec switches provide up to 64 programmable hardware event counters
per stack (8 stacks max, counters 0-63 each).  Each counter is configured
with a ``type_mask`` that selects which PCIe error/event types to count,
a ``port_mask`` that selects which ports within the stack to monitor, and
an optional ``threshold`` that causes the counter to saturate or trigger
once the count is reached.

Typical workflow:

1. ``POST .../evcntr/{stack}/{counter}/setup`` -- configure the counter
   with the desired port mask, type mask, direction, and threshold.
2. ``GET .../evcntr/{stack}/{counter}/counts`` -- poll the accumulated
   count.  Use ``clear=true`` for clear-on-read semantics.
3. ``GET .../evcntr/{stack}/{counter}`` -- read both the setup
   configuration and the current count in a single call.

The ``type_mask`` is a 23-bit bitmask where each bit corresponds to a
specific PCIe event type (e.g. bit 0 = UNSUP_REQ_ERR, bit 1 = ECRC_ERR,
etc.).  Consult the Switchtec firmware reference for the full mapping.

The ``port_mask`` is a 32-bit bitmask where each bit selects a physical
port within the stack to include in the count.
"""

from __future__ import annotations

from fastapi import APIRouter, Path, Query

from serialcables_switchtec.api.dependencies import DEVICE_ID_PATTERN, get_device
from serialcables_switchtec.api.error_handlers import raise_on_error
from serialcables_switchtec.models.evcntr import (
    EvCntrSetupRequest,
    EvCntrSetupResult,
    EvCntrValue,
)

router = APIRouter()


@router.post("/{device_id}/evcntr/{stack_id}/{counter_id}/setup")
def evcntr_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    request: EvCntrSetupRequest = ...,
) -> dict[str, str]:
    """Configure a single hardware event counter on a specific stack.

    Programs the counter identified by ``stack_id`` and ``counter_id`` with
    the event types, port selection, direction, and threshold specified in
    the request body.  Any previous configuration for this counter is
    overwritten.

    Path parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` -- stack index (0-7).
    - ``counter_id`` -- counter index within the stack (0-63).

    Request body fields:

    - ``port_mask`` -- 32-bit bitmask selecting which physical ports within
      the stack contribute to this counter.
    - ``type_mask`` -- 23-bit bitmask selecting which PCIe event types to
      count (e.g. ECRC errors, bad TLPs, replay timeouts).
    - ``egress`` -- ``true`` to count egress events, ``false`` (default) for
      ingress events.
    - ``threshold`` -- 32-bit count value at which the counter saturates or
      fires an interrupt.  0 (default) means no threshold.

    Response format::

        {"status": "configured"}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- stack_id, counter_id, or mask values
      out of range.
    - **500 Internal Server Error** -- firmware rejected the setup command.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.evcntr
        mgr.setup(
            stack_id, counter_id,
            request.port_mask, request.type_mask,
            egress=request.egress, threshold=request.threshold,
        )
        return {"status": "configured"}
    except Exception as e:
        raise_on_error(e, "evcntr_setup")


@router.get(
    "/{device_id}/evcntr/{stack_id}/{counter_id}/setup",
    response_model=list[EvCntrSetupResult],
)
def evcntr_get_setup(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
) -> list[EvCntrSetupResult]:
    """Read the setup configuration of one or more consecutive event counters.

    Returns a list of ``EvCntrSetupResult`` objects, each describing the
    ``port_mask``, ``type_mask``, ``egress`` direction, and ``threshold``
    that a counter was programmed with.

    Path parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` -- stack index (0-7).
    - ``counter_id`` -- starting counter index within the stack (0-63).

    Query parameters:

    - ``nr_counters`` -- number of consecutive counters to read starting
      from ``counter_id``.  Defaults to 1, maximum 64.

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- firmware read failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.evcntr
        return mgr.get_setup(stack_id, counter_id, nr_counters)
    except Exception as e:
        raise_on_error(e, "evcntr_get_setup")


@router.get("/{device_id}/evcntr/{stack_id}/{counter_id}/counts")
def evcntr_get_counts(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
    clear: bool = Query(default=False),
) -> dict[str, list[dict[str, int]]]:
    """Read raw count values from one or more consecutive event counters.

    Returns a JSON object with a ``counters`` array.  Each entry has:

    - ``id`` -- the absolute counter index (counter_id + offset).
    - ``count`` -- the accumulated event count since the last clear.

    Path parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` -- stack index (0-7).
    - ``counter_id`` -- starting counter index within the stack (0-63).

    Query parameters:

    - ``nr_counters`` -- number of consecutive counters to read.  Defaults
      to 1, maximum 64.
    - ``clear`` -- when ``true``, the counters are atomically read and then
      zeroed (clear-on-read semantics), useful for computing per-interval
      BER deltas.  Defaults to ``false``.

    Response format::

        {"counters": [{"id": 0, "count": 1523}, {"id": 1, "count": 0}]}

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- firmware read failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.evcntr
        counts = mgr.get_counts(stack_id, counter_id, nr_counters, clear=clear)
        return {
            "counters": [
                {"id": counter_id + i, "count": c}
                for i, c in enumerate(counts)
            ],
        }
    except Exception as e:
        raise_on_error(e, "evcntr_get_counts")


@router.get(
    "/{device_id}/evcntr/{stack_id}/{counter_id}",
    response_model=list[EvCntrValue],
)
def evcntr_get_both(
    device_id: str = Path(pattern=DEVICE_ID_PATTERN),
    stack_id: int = Path(ge=0, le=7),
    counter_id: int = Path(ge=0, le=63),
    nr_counters: int = Query(default=1, ge=1, le=64),
    clear: bool = Query(default=False),
) -> list[EvCntrValue]:
    """Read both setup configuration and count values in a single call.

    Combines the data from the ``/setup`` and ``/counts`` endpoints into a
    list of ``EvCntrValue`` objects.  Each entry contains:

    - ``counter_id`` -- the absolute counter index.
    - ``count`` -- the accumulated event count.
    - ``setup`` -- an ``EvCntrSetupResult`` with the ``port_mask``,
      ``type_mask``, ``egress``, and ``threshold`` that this counter was
      programmed with.  May be ``null`` if the counter was never configured.

    This is the preferred endpoint for dashboard polling because it returns
    all relevant data in a single round-trip.

    Path parameters:

    - ``device_id`` -- the registered device identifier.
    - ``stack_id`` -- stack index (0-7).
    - ``counter_id`` -- starting counter index within the stack (0-63).

    Query parameters:

    - ``nr_counters`` -- number of consecutive counters to read.  Defaults
      to 1, maximum 64.
    - ``clear`` -- when ``true``, the counts are atomically read and zeroed.
      Defaults to ``false``.

    Error responses:

    - **404 Not Found** -- device not found.
    - **422 Unprocessable Entity** -- parameter out of range.
    - **500 Internal Server Error** -- firmware read failed.
    """
    dev = get_device(device_id)
    try:
        mgr = dev.evcntr
        return mgr.get_both(stack_id, counter_id, nr_counters, clear=clear)
    except Exception as e:
        raise_on_error(e, "evcntr_get_both")
