"""Fabric topology management for Switchtec PAX devices."""

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.bindings.types import (
    SwitchtecFabPortConfig,
    SwitchtecGfmsBindReq,
    SwitchtecGfmsUnbindReq,
)
from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.models.fabric import (
    FabPortConfig,
    GfmsBindRequest,
    GfmsUnbindRequest,
)
from serialcables_switchtec.utils.logging import get_logger

if TYPE_CHECKING:
    from serialcables_switchtec.core.device import SwitchtecDevice

logger = get_logger(__name__)


class FabricManager:
    """Manages fabric/topology operations on a Switchtec PAX device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def port_control(
        self,
        phys_port_id: int,
        control_type: FabPortControlType,
        hot_reset_flag: FabHotResetFlag = FabHotResetFlag.NONE,
    ) -> None:
        """Control a fabric port (enable/disable/hot-reset).

        Args:
            phys_port_id: Physical port identifier.
            control_type: The control operation to perform.
            hot_reset_flag: Hot reset flag (only relevant for hot-reset).
        """
        ret = self._dev.lib.switchtec_port_control(
            self._dev.handle,
            int(control_type),
            phys_port_id,
            int(hot_reset_flag),
        )
        check_error(ret, "port_control")
        logger.info(
            "port_control",
            port=phys_port_id,
            control=control_type.name,
        )

    def get_port_config(self, phys_port_id: int) -> FabPortConfig:
        """Get configuration for a fabric port.

        Args:
            phys_port_id: Physical port identifier.

        Returns:
            FabPortConfig with the port's current configuration.
        """
        config = SwitchtecFabPortConfig()
        ret = self._dev.lib.switchtec_fab_port_config_get(
            self._dev.handle,
            phys_port_id,
            ctypes.byref(config),
        )
        check_error(ret, "fab_port_config_get")

        return FabPortConfig(
            phys_port_id=phys_port_id,
            port_type=config.port_type,
            clock_source=config.clock_source,
            clock_sris=config.clock_sris,
            hvd_inst=config.hvd_inst,
            link_width=config.link_width,
        )

    def set_port_config(self, config: FabPortConfig) -> None:
        """Set configuration for a fabric port.

        Args:
            config: The port configuration to apply.
        """
        c_config = SwitchtecFabPortConfig()
        c_config.port_type = config.port_type
        c_config.clock_source = config.clock_source
        c_config.clock_sris = config.clock_sris
        c_config.hvd_inst = config.hvd_inst
        c_config.link_width = config.link_width
        ret = self._dev.lib.switchtec_fab_port_config_set(
            self._dev.handle,
            config.phys_port_id,
            ctypes.byref(c_config),
        )
        check_error(ret, "fab_port_config_set")
        logger.info("port_config_set", port=config.phys_port_id)

    def bind(self, request: GfmsBindRequest) -> None:
        """Bind a host port to an endpoint port via GFMS.

        Args:
            request: Bind request parameters.
        """
        req = SwitchtecGfmsBindReq()
        req.host_sw_idx = request.host_sw_idx
        req.host_phys_port_id = request.host_phys_port_id
        req.host_log_port_id = request.host_log_port_id
        req.ep_sw_idx = request.ep_sw_idx
        req.ep_phys_port_id = request.ep_phys_port_id
        ret = self._dev.lib.switchtec_gfms_bind(
            self._dev.handle,
            ctypes.byref(req),
        )
        check_error(ret, "gfms_bind")
        logger.info(
            "gfms_bind",
            host_port=request.host_phys_port_id,
            ep_port=request.ep_phys_port_id,
        )

    def unbind(self, request: GfmsUnbindRequest) -> None:
        """Unbind a host port from an endpoint port via GFMS.

        Args:
            request: Unbind request parameters.
        """
        req = SwitchtecGfmsUnbindReq()
        req.host_sw_idx = request.host_sw_idx
        req.host_phys_port_id = request.host_phys_port_id
        req.host_log_port_id = request.host_log_port_id
        req.opt = request.opt
        ret = self._dev.lib.switchtec_gfms_unbind(
            self._dev.handle,
            ctypes.byref(req),
        )
        check_error(ret, "gfms_unbind")
        logger.info(
            "gfms_unbind",
            host_port=request.host_phys_port_id,
        )

    def clear_gfms_events(self) -> None:
        """Clear all GFMS events."""
        ret = self._dev.lib.switchtec_clear_gfms_events(
            self._dev.handle,
        )
        check_error(ret, "clear_gfms_events")
        logger.info("gfms_events_cleared")
