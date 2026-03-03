"""Shared helpers for workflow recipe tests.

Extracted from test_workflows.py so that all recipe test modules
can reuse common mock builders and runner utilities.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from serialcables_switchtec.core.workflows.models import (
    RecipeResult,
    RecipeSummary,
    StepStatus,
)


def run_recipe(recipe, dev, cancel=None, **kwargs):
    """Drive a recipe generator to completion, returning (results, summary).

    Collects all yielded RecipeResult objects and the RecipeSummary returned
    via StopIteration.value.
    """
    if cancel is None:
        cancel = threading.Event()
    gen = recipe.run(dev, cancel, **kwargs)
    results: list[RecipeResult] = []
    summary: RecipeSummary | None = None
    try:
        while True:
            result = next(gen)
            results.append(result)
    except StopIteration as stop:
        summary = stop.value
    return results, summary


def final_results(results):
    """Filter out RUNNING status results, keeping only terminal step states."""
    return [r for r in results if r.status != StepStatus.RUNNING]


def make_port_status(
    phys_id=0,
    link_up=True,
    link_rate="16 GT/s",
    neg_lnk_width=4,
    ltssm=0,
    ltssm_str="L0",
    cfg_lnk_width=4,
    vendor_id=0x11F8,
    device_id=0x4000,
    pci_bdf="00:00.0",
):
    """Create a mock PortStatus object."""
    ps = MagicMock()
    ps.port.phys_id = phys_id
    ps.link_up = link_up
    ps.link_rate = link_rate
    ps.neg_lnk_width = neg_lnk_width
    ps.neg_link_width = neg_lnk_width
    ps.ltssm = ltssm
    ps.ltssm_str = ltssm_str
    ps.cfg_lnk_width = cfg_lnk_width
    ps.vendor_id = vendor_id
    ps.device_id = device_id
    ps.pci_bdf = pci_bdf
    return ps


def make_device_summary(
    name="PSX 48XG6",
    device_id=0x4000,
    generation="GEN6",
    variant="PSX",
    boot_phase="Main Firmware",
    partition=0,
    fw_version="4.20",
    die_temperature=42.5,
    port_count=48,
):
    """Create a mock DeviceSummary returned by dev.get_summary()."""
    summary = MagicMock()
    summary.name = name
    summary.device_id = device_id
    summary.generation = generation
    summary.variant = variant
    summary.boot_phase = boot_phase
    summary.partition = partition
    summary.fw_version = fw_version
    summary.die_temperature = die_temperature
    summary.port_count = port_count
    return summary


def make_pattern_mon_result(error_count=0):
    """Create a mock PatternMonResult."""
    mon = MagicMock()
    mon.error_count = error_count
    return mon


def make_ltssm_entry(link_state_str="L0", link_rate="16 GT/s", link_width=4):
    """Create a mock LTSSM log entry."""
    entry = MagicMock()
    entry.link_state_str = link_state_str
    entry.link_rate = link_rate
    entry.link_width = link_width
    return entry


def make_cross_hair_result(
    lane_id=0,
    state_name="DONE",
    eye_left_lim=15,
    eye_right_lim=15,
    eye_top_left_lim=20,
    eye_top_right_lim=20,
    eye_bot_left_lim=20,
    eye_bot_right_lim=20,
):
    """Create a mock cross-hair measurement result."""
    ch = MagicMock()
    ch.lane_id = lane_id
    ch.state_name = state_name
    ch.eye_left_lim = eye_left_lim
    ch.eye_right_lim = eye_right_lim
    ch.eye_top_left_lim = eye_top_left_lim
    ch.eye_top_right_lim = eye_top_right_lim
    ch.eye_bot_left_lim = eye_bot_left_lim
    ch.eye_bot_right_lim = eye_bot_right_lim
    return ch


def make_eq_coeff(lane_count=4, cursors=None):
    """Create a mock EQ TX coefficients result."""
    coeff = MagicMock()
    coeff.lane_count = lane_count
    if cursors is None:
        cursors = []
        for _ in range(lane_count):
            c = MagicMock()
            c.pre = -2
            c.post = -4
            cursors.append(c)
    coeff.cursors = cursors
    return coeff


def make_eq_table(step_count=10, lane_id=0, active_count=5):
    """Create a mock EQ TX table result."""
    table = MagicMock()
    table.step_count = step_count
    table.lane_id = lane_id
    steps = []
    for i in range(step_count):
        s = MagicMock()
        s.active_status = 1 if i < active_count else 0
        steps.append(s)
    table.steps = steps
    return table


def make_eq_fslf(fs=63, lf=15):
    """Create a mock EQ FS/LF result."""
    fslf = MagicMock()
    fslf.fs = fs
    fslf.lf = lf
    return fslf


def make_eye_data(pixels=None, pixel_count=None):
    """Create a mock eye diagram data result."""
    eye = MagicMock()
    if pixels is not None:
        eye.pixels = pixels
    elif pixel_count is not None:
        eye.pixels = [0.0] * pixel_count
    else:
        eye.pixels = [0.0] * 100
    return eye


def make_bw_result(egress_total=1000, ingress_total=500, time_us=1_000_000):
    """Create a mock bandwidth result."""
    bw = MagicMock()
    bw.egress.total = egress_total
    bw.ingress.total = ingress_total
    bw.time_us = time_us
    return bw


def make_lat_result(current_ns=100, max_ns=200):
    """Create a mock latency result."""
    lat = MagicMock()
    lat.current_ns = current_ns
    lat.max_ns = max_ns
    return lat


def make_port_config(phys_port_id=0, port_type=1):
    """Create a mock fabric port config."""
    config = MagicMock()
    config.phys_port_id = phys_port_id
    config.port_type = port_type
    return config


def make_part_summary(boot_valid=True, img_valid=True, cfg_valid=True):
    """Create a mock firmware partition summary."""
    summary = MagicMock()

    for part_name, valid in [("boot", boot_valid), ("img", img_valid), ("cfg", cfg_valid)]:
        part = MagicMock()
        active = MagicMock()
        active.valid = valid
        active.version = "4.20"
        active.read_only = part_name == "boot"
        part.active = active
        setattr(summary, part_name, part)

    return summary


def make_mock_device():
    """Create a MagicMock device with all sub-managers wired up."""
    dev = MagicMock()
    dev.get_status = MagicMock(return_value=[])
    dev.get_summary = MagicMock(return_value=make_device_summary())
    dev.get_die_temperatures = MagicMock(return_value=[42.5, 43.0, 41.0, 44.0, 42.0])
    dev.diagnostics = MagicMock()
    dev.diagnostics.pattern_gen_set = MagicMock()
    dev.diagnostics.pattern_mon_set = MagicMock()
    dev.diagnostics.pattern_mon_get = MagicMock(
        return_value=make_pattern_mon_result(error_count=0),
    )
    dev.diagnostics.ltssm_log = MagicMock(return_value=[])
    dev.diagnostics.ltssm_clear = MagicMock()
    dev.diagnostics.loopback_set = MagicMock()
    dev.diagnostics.eye_start = MagicMock()
    dev.diagnostics.eye_fetch = MagicMock()
    dev.diagnostics.eye_cancel = MagicMock()
    dev.diagnostics.cross_hair_enable = MagicMock()
    dev.diagnostics.cross_hair_disable = MagicMock()
    dev.diagnostics.cross_hair_get = MagicMock()
    dev.diagnostics.port_eq_tx_coeff = MagicMock()
    dev.diagnostics.port_eq_tx_table = MagicMock()
    dev.diagnostics.port_eq_tx_fslf = MagicMock()
    dev.evcntr = MagicMock()
    dev.evcntr.setup = MagicMock()
    dev.evcntr.get_counts = MagicMock(return_value=[0])
    dev.injector = MagicMock()
    dev.fabric = MagicMock()
    dev.firmware = MagicMock()
    dev.osa = MagicMock()
    dev.performance = MagicMock()
    return dev
