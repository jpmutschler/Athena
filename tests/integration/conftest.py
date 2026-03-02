"""Shared fixtures for cross-layer integration tests.

These fixtures create mock devices with *real* frozen Pydantic return values
(PortStatus, DeviceSummary) rather than MagicMocks, ensuring that real recipe
code receives the exact types it expects.
"""

from __future__ import annotations

import threading

import pytest

from serialcables_switchtec.models.device import (
    DeviceSummary,
    PortId,
    PortStatus,
)


def make_real_port_status(
    phys_id: int = 0,
    link_up: bool = True,
    link_rate: int = 5,
    neg_lnk_width: int = 16,
    cfg_lnk_width: int = 16,
    ltssm: int = 0,
    ltssm_str: str = "L0",
    flit_mode: str | None = "OFF",
) -> PortStatus:
    """Create a real frozen PortStatus with defaults for a healthy Gen5 port."""
    return PortStatus(
        port=PortId(
            partition=0,
            stack=0,
            upstream=(phys_id == 0),
            stk_id=0,
            phys_id=phys_id,
            log_id=phys_id,
        ),
        cfg_lnk_width=cfg_lnk_width,
        neg_lnk_width=neg_lnk_width,
        link_up=link_up,
        link_rate=link_rate,
        ltssm=ltssm,
        ltssm_str=ltssm_str,
        lane_reversal=0,
        lane_reversal_str="none",
        first_act_lane=0,
        pci_bdf=f"0{phys_id}:00.0",
        vendor_id=0x11F8,
        device_id=0x4000,
        flit_mode=flit_mode,
    )


def make_real_device_summary(
    name: str = "PSX48XG5",
    generation: str = "Gen5",
    port_count: int = 48,
    die_temperature: float = 42.5,
    supports_flit: bool = False,
) -> DeviceSummary:
    """Create a real frozen DeviceSummary."""
    return DeviceSummary(
        name=name,
        device_id=0x5A00,
        generation=generation,
        variant="PSX",
        boot_phase="Main Firmware",
        partition=0,
        fw_version="4.70B058",
        die_temperature=die_temperature,
        port_count=port_count,
        supports_flit=supports_flit,
    )


@pytest.fixture
def cancel():
    """Provide a threading.Event for recipe cancellation."""
    return threading.Event()


def drive_generator(gen):
    """Drive a generator to completion, returning (results, return_value).

    Works for both Recipe.run() and WorkflowExecutor.run() generators.
    """
    results = []
    return_value = None
    try:
        while True:
            results.append(next(gen))
    except StopIteration as stop:
        return_value = stop.value
    return results, return_value
