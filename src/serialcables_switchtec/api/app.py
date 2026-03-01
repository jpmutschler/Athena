"""FastAPI application factory with device registry and lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from serialcables_switchtec.api.state import (
    get_device_registry,
    verify_api_key,
)
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: cleanup open devices on shutdown."""
    logger.info("api_starting")
    yield
    registry = get_device_registry()
    for dev_id, (dev, _path) in registry.items():
        try:
            dev.close()
            logger.info("device_closed_on_shutdown", device_id=dev_id)
        except Exception as e:
            logger.error(
                "device_close_failed_on_shutdown",
                device_id=dev_id,
                error=str(e),
            )
    registry.clear()
    logger.info("api_stopped")


_OPENAPI_TAGS = [
    {
        "name": "devices",
        "description": "Device registry: open, close, discover, and query Switchtec devices.",
    },
    {
        "name": "ports",
        "description": "Port status and PFF (Physical Function to Forwarding) mapping.",
    },
    {
        "name": "diagnostics",
        "description": (
            "PCIe diagnostics: eye diagrams, LTSSM logs, loopback, "
            "pattern gen/mon, error injection, receiver cal, equalization, cross-hair."
        ),
    },
    {
        "name": "firmware",
        "description": "Firmware version, partition summary, image write, toggle, and boot RO.",
    },
    {
        "name": "evcntr",
        "description": "Event counters: setup, read counts, and BER monitoring.",
    },
    {
        "name": "events",
        "description": "Event summary, clear, and wait-for-event with timeout.",
    },
    {
        "name": "fabric",
        "description": (
            "Fabric topology (PAX devices): port control, GFMS bind/unbind, "
            "config space read/write."
        ),
    },
    {
        "name": "mrpc",
        "description": "Raw MRPC commands for low-level firmware debugging.",
    },
    {
        "name": "osa",
        "description": "Ordered Set Analyzer: capture, type/pattern config, data fetch.",
    },
    {
        "name": "performance",
        "description": "Bandwidth counters and latency measurement between port pairs.",
    },
    {
        "name": "monitor",
        "description": (
            "SSE streaming for continuous bandwidth and event counter monitoring. "
            "Uses Server-Sent Events (text/event-stream) with NDJSON payloads."
        ),
    },
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Athena API",
        description=(
            "Athena -- Serial Cables Gen6 PCIe Switchtec Host Card"
            " Management Interface"
        ),
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=_OPENAPI_TAGS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key"],
    )

    auth_dep = [Depends(verify_api_key)]

    from serialcables_switchtec.api.routes.devices import (
        router as devices_router,
    )
    from serialcables_switchtec.api.routes.diagnostics import (
        router as diag_router,
    )
    from serialcables_switchtec.api.routes.evcntr import (
        router as evcntr_router,
    )
    from serialcables_switchtec.api.routes.events import (
        router as events_router,
    )
    from serialcables_switchtec.api.routes.fabric import (
        router as fabric_router,
    )
    from serialcables_switchtec.api.routes.firmware import (
        router as firmware_router,
    )
    from serialcables_switchtec.api.routes.mrpc import (
        router as mrpc_router,
    )
    from serialcables_switchtec.api.routes.osa import (
        router as osa_router,
    )
    from serialcables_switchtec.api.routes.performance import (
        router as perf_router,
    )
    from serialcables_switchtec.api.routes.monitor import (
        router as monitor_router,
    )
    from serialcables_switchtec.api.routes.ports import (
        router as ports_router,
    )

    app.include_router(
        devices_router,
        prefix="/api/devices",
        tags=["devices"],
        dependencies=auth_dep,
    )
    app.include_router(
        ports_router,
        prefix="/api/devices",
        tags=["ports"],
        dependencies=auth_dep,
    )
    app.include_router(
        diag_router,
        prefix="/api/devices",
        tags=["diagnostics"],
        dependencies=auth_dep,
    )
    app.include_router(
        firmware_router,
        prefix="/api/devices",
        tags=["firmware"],
        dependencies=auth_dep,
    )
    app.include_router(
        evcntr_router,
        prefix="/api/devices",
        tags=["evcntr"],
        dependencies=auth_dep,
    )
    app.include_router(
        events_router,
        prefix="/api/devices",
        tags=["events"],
        dependencies=auth_dep,
    )
    app.include_router(
        fabric_router,
        prefix="/api/devices",
        tags=["fabric"],
        dependencies=auth_dep,
    )
    app.include_router(
        mrpc_router,
        prefix="/api/devices",
        tags=["mrpc"],
        dependencies=auth_dep,
    )
    app.include_router(
        osa_router,
        prefix="/api/devices",
        tags=["osa"],
        dependencies=auth_dep,
    )
    app.include_router(
        perf_router,
        prefix="/api/devices",
        tags=["performance"],
        dependencies=auth_dep,
    )
    app.include_router(
        monitor_router,
        prefix="/api/devices",
        tags=["monitor"],
        dependencies=auth_dep,
    )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
