"""Workflow recipe registry."""

from __future__ import annotations

from serialcables_switchtec.core.workflows.all_port_sweep import AllPortSweep
from serialcables_switchtec.core.workflows.bandwidth_baseline import BandwidthBaseline
from serialcables_switchtec.core.workflows.base import Recipe
from serialcables_switchtec.core.workflows.ber_soak import BerSoak
from serialcables_switchtec.core.workflows.config_dump import ConfigDump
from serialcables_switchtec.core.workflows.cross_hair_margin import CrossHairMargin
from serialcables_switchtec.core.workflows.eq_report import EqReport
from serialcables_switchtec.core.workflows.error_injection_recovery import ErrorInjectionRecovery
from serialcables_switchtec.core.workflows.event_counter_baseline import EventCounterBaseline
from serialcables_switchtec.core.workflows.eye_quick_scan import EyeQuickScan
from serialcables_switchtec.core.workflows.fabric_bind_unbind import FabricBindUnbind
from serialcables_switchtec.core.workflows.firmware_validation import FirmwareValidation
from serialcables_switchtec.core.workflows.latency_profile import LatencyProfile
from serialcables_switchtec.core.workflows.link_health_check import LinkHealthCheck
from serialcables_switchtec.core.workflows.link_training_debug import LinkTrainingDebug
from serialcables_switchtec.core.workflows.loopback_sweep import LoopbackSweep
from serialcables_switchtec.core.workflows.ltssm_monitor import LtssmMonitor
from serialcables_switchtec.core.workflows.models import RecipeCategory
from serialcables_switchtec.core.workflows.osa_capture import OsaCapture
from serialcables_switchtec.core.workflows.thermal_profile import ThermalProfile

RECIPE_REGISTRY: dict[str, type[Recipe]] = {
    "all_port_sweep": AllPortSweep,
    "bandwidth_baseline": BandwidthBaseline,
    "ber_soak": BerSoak,
    "config_dump": ConfigDump,
    "cross_hair_margin": CrossHairMargin,
    "eq_report": EqReport,
    "error_injection_recovery": ErrorInjectionRecovery,
    "event_counter_baseline": EventCounterBaseline,
    "eye_quick_scan": EyeQuickScan,
    "fabric_bind_unbind": FabricBindUnbind,
    "firmware_validation": FirmwareValidation,
    "latency_profile": LatencyProfile,
    "link_health_check": LinkHealthCheck,
    "link_training_debug": LinkTrainingDebug,
    "loopback_sweep": LoopbackSweep,
    "ltssm_monitor": LtssmMonitor,
    "osa_capture": OsaCapture,
    "thermal_profile": ThermalProfile,
}


def get_recipe(name: str) -> Recipe:
    """Instantiate a recipe by registry name."""
    cls = RECIPE_REGISTRY[name]
    return cls()


def get_recipes_by_category(category: RecipeCategory) -> list[Recipe]:
    """Return all recipe instances for a given category."""
    return [
        cls()
        for cls in RECIPE_REGISTRY.values()
        if cls.category == category
    ]
