"""Error injection for PCIe link testing.

Wraps switchtec_inject_err_* functions for DLLP, TLP CRC, sequence number,
ACK/NACK, and completion timeout injection.
"""

from __future__ import annotations

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import check_error
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)


class ErrorInjector:
    """Error injection operations on a Switchtec device."""

    def __init__(self, device: SwitchtecDevice) -> None:
        self._dev = device

    def inject_dllp(self, phys_port_id: int, data: int) -> None:
        """Inject a raw DLLP on a port.

        Args:
            phys_port_id: Physical port ID.
            data: DLLP data to inject.
        """
        ret = self._dev.lib.switchtec_inject_err_dllp(
            self._dev.handle, phys_port_id, data
        )
        check_error(ret, "inject_dllp")
        logger.info("dllp_injected", port=phys_port_id, data=data)

    def inject_dllp_crc(
        self, phys_port_id: int, enable: bool, rate: int
    ) -> None:
        """Enable/disable DLLP CRC error injection.

        Args:
            phys_port_id: Physical port ID.
            enable: True to enable, False to disable.
            rate: Injection rate.
        """
        ret = self._dev.lib.switchtec_inject_err_dllp_crc(
            self._dev.handle, phys_port_id, int(enable), rate
        )
        check_error(ret, "inject_dllp_crc")
        logger.info(
            "dllp_crc_injection",
            port=phys_port_id, enable=enable, rate=rate,
        )

    def inject_tlp_lcrc(
        self, phys_port_id: int, enable: bool, rate: int
    ) -> None:
        """Enable/disable TLP LCRC error injection.

        Args:
            phys_port_id: Physical port ID.
            enable: True to enable, False to disable.
            rate: Injection rate.
        """
        ret = self._dev.lib.switchtec_inject_err_tlp_lcrc(
            self._dev.handle, phys_port_id, int(enable), rate
        )
        check_error(ret, "inject_tlp_lcrc")
        logger.info(
            "tlp_lcrc_injection",
            port=phys_port_id, enable=enable, rate=rate,
        )

    def inject_tlp_seq_num(self, phys_port_id: int) -> None:
        """Inject a TLP sequence number error.

        Args:
            phys_port_id: Physical port ID.
        """
        ret = self._dev.lib.switchtec_inject_err_tlp_seq_num(
            self._dev.handle, phys_port_id
        )
        check_error(ret, "inject_tlp_seq_num")
        logger.info("tlp_seq_num_injected", port=phys_port_id)

    def inject_ack_nack(
        self, phys_port_id: int, seq_num: int, count: int
    ) -> None:
        """Inject ACK/NACK errors.

        Args:
            phys_port_id: Physical port ID.
            seq_num: Sequence number.
            count: Number of errors to inject.
        """
        ret = self._dev.lib.switchtec_inject_err_ack_nack(
            self._dev.handle, phys_port_id, seq_num, count
        )
        check_error(ret, "inject_ack_nack")
        logger.info(
            "ack_nack_injected",
            port=phys_port_id, seq_num=seq_num, count=count,
        )

    def inject_cto(self, phys_port_id: int) -> None:
        """Inject a completion timeout error.

        Args:
            phys_port_id: Physical port ID.
        """
        ret = self._dev.lib.switchtec_inject_err_cto(
            self._dev.handle, phys_port_id
        )
        check_error(ret, "inject_cto")
        logger.info("cto_injected", port=phys_port_id)
