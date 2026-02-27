"""Tests for ErrorInjector."""

from __future__ import annotations

from serialcables_switchtec.core.error_injection import ErrorInjector


class TestErrorInjector:
    def test_inject_dllp(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_dllp(phys_port_id=0, data=0x1234)
        mock_library.switchtec_inject_err_dllp.assert_called_once_with(
            0xDEADBEEF, 0, 0x1234
        )

    def test_inject_dllp_crc(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_dllp_crc(phys_port_id=1, enable=True, rate=10)
        mock_library.switchtec_inject_err_dllp_crc.assert_called_once_with(
            0xDEADBEEF, 1, 1, 10
        )

    def test_inject_tlp_lcrc(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_tlp_lcrc(phys_port_id=2, enable=True, rate=5)
        mock_library.switchtec_inject_err_tlp_lcrc.assert_called_once_with(
            0xDEADBEEF, 2, 1, 5
        )

    def test_inject_tlp_seq_num(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_tlp_seq_num(phys_port_id=3)
        mock_library.switchtec_inject_err_tlp_seq_num.assert_called_once_with(
            0xDEADBEEF, 3
        )

    def test_inject_ack_nack(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_ack_nack(phys_port_id=4, seq_num=100, count=3)
        mock_library.switchtec_inject_err_ack_nack.assert_called_once_with(
            0xDEADBEEF, 4, 100, 3
        )

    def test_inject_cto(self, device, mock_library):
        injector = ErrorInjector(device)
        injector.inject_cto(phys_port_id=5)
        mock_library.switchtec_inject_err_cto.assert_called_once_with(
            0xDEADBEEF, 5
        )
