"""Tests for DiagnosticsManager."""

from __future__ import annotations

from serialcables_switchtec.core.diagnostics import DiagnosticsManager


class TestDiagnosticsManager:
    def test_eye_cancel(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_cancel()
        mock_library.switchtec_diag_eye_cancel.assert_called_once_with(
            0xDEADBEEF
        )

    def test_ltssm_clear(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.ltssm_clear(port_id=5)
        mock_library.switchtec_diag_ltssm_clear.assert_called_once_with(
            0xDEADBEEF, 5
        )

    def test_cross_hair_enable(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.cross_hair_enable(lane_id=3)
        mock_library.switchtec_diag_cross_hair_enable.assert_called_once_with(
            0xDEADBEEF, 3
        )

    def test_cross_hair_disable(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.cross_hair_disable()
        mock_library.switchtec_diag_cross_hair_disable.assert_called_once_with(
            0xDEADBEEF
        )

    def test_pattern_gen_set(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_gen_set(port_id=1)
        mock_library.switchtec_diag_pattern_gen_set.assert_called_once_with(
            0xDEADBEEF, 1, 3, 4
        )

    def test_pattern_mon_set(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_mon_set(port_id=1)
        mock_library.switchtec_diag_pattern_mon_set.assert_called_once_with(
            0xDEADBEEF, 1, 3
        )

    def test_pattern_inject(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.pattern_inject(port_id=1, err_count=5)
        mock_library.switchtec_diag_pattern_inject.assert_called_once_with(
            0xDEADBEEF, 1, 5
        )

    def test_eye_set_mode(self, device, mock_library):
        diag = DiagnosticsManager(device)
        diag.eye_set_mode(mode=0)
        mock_library.switchtec_diag_eye_set_mode.assert_called_once_with(
            0xDEADBEEF, 0
        )
