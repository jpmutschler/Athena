"""Diagnostic route integration tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.exceptions import (
    DeviceOpenError,
    InvalidLaneError,
    InvalidParameterError,
    InvalidPortError,
    MrpcError,
    SwitchtecPermissionError,
    SwitchtecTimeoutError,
    UnsupportedError,
)
from serialcables_switchtec.models.device import DeviceSummary, PortId, PortStatus


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    """Set SWITCHTEC_API_KEY so auth is satisfied by the test client."""
    monkeypatch.setenv("SWITCHTEC_API_KEY", "test-key")


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    from serialcables_switchtec.api.app import create_app

    return create_app()


@pytest.fixture
def client(app):
    """Create a test client with default API key header."""
    return TestClient(app, headers={"X-API-Key": "test-key"})


def _make_mock_device(
    name: str = "PSX48XG5",
    device_id: int = 0x5A00,
    temperature: float = 42.5,
) -> MagicMock:
    """Create a mock SwitchtecDevice with sane defaults."""
    dev = MagicMock()
    dev.name = name
    dev.partition = 0
    dev.die_temperature = temperature
    dev.get_summary.return_value = DeviceSummary(
        name=name,
        device_id=device_id,
        generation="Gen5",
        variant="PSX",
        boot_phase="BL2",
        partition=0,
        fw_version="4.70B058",
        die_temperature=temperature,
        port_count=48,
    )
    dev.get_status.return_value = [
        PortStatus(
            port=PortId(
                partition=0,
                stack=0,
                upstream=True,
                stk_id=0,
                phys_id=0,
                log_id=0,
            ),
            cfg_lnk_width=16,
            neg_lnk_width=16,
            link_up=True,
            link_rate=5,
            ltssm=0,
            ltssm_str="L0",
            lane_reversal=0,
            lane_reversal_str="none",
            first_act_lane=0,
        ),
    ]
    dev.port_to_pff.return_value = 3
    dev.close.return_value = None
    return dev


@pytest.fixture
def registered_device(app):
    """Register a mock device in the device registry and clean up after."""
    from serialcables_switchtec.api.state import get_device_registry

    mock_dev = _make_mock_device()
    registry = get_device_registry()
    registry["testdev"] = (mock_dev, "/dev/switchtec0")
    yield mock_dev
    registry.pop("testdev", None)


# -- Diagnostic routes -----------------------------------------------------


class TestDiagRoutes:
    def test_ltssm_not_found(self, client):
        response = client.get("/api/devices/nonexistent/diag/ltssm/0")
        assert response.status_code == 404

    def test_crosshair_not_found(self, client):
        response = client.get("/api/devices/nonexistent/diag/crosshair")
        assert response.status_code == 404

    def test_ltssm_max_entries_bound(self, client):
        """max_entries exceeding 1024 should be rejected."""
        response = client.get("/api/devices/test/diag/ltssm/0?max_entries=9999")
        assert response.status_code == 422

    def test_crosshair_num_lanes_bound(self, client):
        """num_lanes exceeding 64 should be rejected."""
        response = client.get("/api/devices/test/diag/crosshair?num_lanes=999")
        assert response.status_code == 422

    def test_inject_port_bound(self, client):
        """port_id exceeding 59 should be rejected."""
        response = client.post("/api/devices/test/diag/inject/cto/100")
        assert response.status_code == 422

    def test_eye_start_not_found(self, client):
        """POST eye start for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/eye/start",
            json={},
        )
        assert response.status_code == 404

    def test_loopback_set_not_found(self, client):
        """POST loopback set for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/loopback/0",
            json={},
        )
        assert response.status_code == 404

    def test_pattern_gen_not_found(self, client):
        """POST pattern gen for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/patgen/0",
            json={},
        )
        assert response.status_code == 404

    def test_pattern_mon_not_found(self, client):
        """GET pattern monitor for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/diag/patmon/0/0",
        )
        assert response.status_code == 404

    def test_inject_dllp_not_found(self, client):
        """POST DLLP inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/dllp/0",
            json={"data": 0},
        )
        assert response.status_code == 404

    def test_inject_dllp_crc_not_found(self, client):
        """POST DLLP CRC inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/dllp-crc/0",
            json={},
        )
        assert response.status_code == 404

    def test_rcvr_not_found(self, client):
        """GET receiver object for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/diag/rcvr/0/0",
        )
        assert response.status_code == 404

    def test_eq_not_found(self, client):
        """GET EQ coefficients for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/diag/eq/0",
        )
        assert response.status_code == 404

    def test_eye_cancel_not_found(self, client):
        """POST eye cancel for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/eye/cancel",
        )
        assert response.status_code == 404

    def test_ltssm_clear_not_found(self, client):
        """DELETE LTSSM log for nonexistent device should return 404."""
        response = client.delete(
            "/api/devices/nonexistent/diag/ltssm/0",
        )
        assert response.status_code == 404

    def test_loopback_get_not_found(self, client):
        """GET loopback for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/diag/loopback/0",
        )
        assert response.status_code == 404

    def test_crosshair_enable_not_found(self, client):
        """POST crosshair enable for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/crosshair/enable/0",
        )
        assert response.status_code == 404

    def test_crosshair_disable_not_found(self, client):
        """POST crosshair disable for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/crosshair/disable",
        )
        assert response.status_code == 404

    def test_inject_cto_not_found(self, client):
        """POST CTO inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/cto/0",
        )
        assert response.status_code == 404

    # -- Success-path tests (registered device) ----------------------------

    def test_eye_start_happy_path(self, client, registered_device):
        """POST eye start should invoke DiagnosticsManager.eye_start and return started."""
        response = client.post(
            "/api/devices/testdev/diag/eye/start",
            json={
                "lane_mask": [1, 0, 0, 0],
                "x_start": -64,
                "x_end": 64,
                "x_step": 1,
                "y_start": -255,
                "y_end": 255,
                "y_step": 2,
                "step_interval": 10,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "started"}
        registered_device.diagnostics.eye_start.assert_called_once_with(
            lane_mask=[1, 0, 0, 0],
            x_start=-64,
            x_end=64,
            x_step=1,
            y_start=-255,
            y_end=255,
            y_step=2,
            step_interval=10,
        )

    def test_eye_start_defaults(self, client, registered_device):
        """POST eye start with empty body should use default parameters."""
        response = client.post(
            "/api/devices/testdev/diag/eye/start",
            json={},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "started"}
        registered_device.diagnostics.eye_start.assert_called_once()

    def test_eye_cancel_happy_path(self, client, registered_device):
        """POST eye cancel should invoke DiagnosticsManager.eye_cancel."""
        response = client.post("/api/devices/testdev/diag/eye/cancel")
        assert response.status_code == 200
        assert response.json() == {"status": "cancelled"}
        registered_device.diagnostics.eye_cancel.assert_called_once()

    def test_ltssm_log_happy_path(self, client, registered_device):
        """GET LTSSM log should return entries from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import LtssmLogEntry

        mock_entries = [
            LtssmLogEntry(
                timestamp=1000,
                link_rate=32.0,
                link_state=0,
                link_state_str="L0",
                link_width=16,
                tx_minor_state=0,
                rx_minor_state=0,
            ),
        ]
        registered_device.diagnostics.ltssm_log.return_value = mock_entries
        response = client.get("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["timestamp"] == 1000
        assert body[0]["link_state_str"] == "L0"
        assert body[0]["link_width"] == 16
        registered_device.diagnostics.ltssm_log.assert_called_once_with(0, max_entries=64)

    def test_ltssm_log_custom_max_entries(self, client, registered_device):
        """GET LTSSM log should pass custom max_entries query param."""
        registered_device.diagnostics.ltssm_log.return_value = []
        response = client.get(
            "/api/devices/testdev/diag/ltssm/5?max_entries=128"
        )
        assert response.status_code == 200
        registered_device.diagnostics.ltssm_log.assert_called_once_with(5, max_entries=128)

    def test_ltssm_clear_happy_path(self, client, registered_device):
        """DELETE LTSSM log should invoke DiagnosticsManager.ltssm_clear."""
        response = client.delete("/api/devices/testdev/diag/ltssm/3")
        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}
        registered_device.diagnostics.ltssm_clear.assert_called_once_with(3)

    def test_loopback_get_happy_path(self, client, registered_device):
        """GET loopback should return LoopbackStatus from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import LoopbackStatus

        registered_device.diagnostics.loopback_get.return_value = LoopbackStatus(
            port_id=2, enabled=1, ltssm_speed=3,
        )
        response = client.get("/api/devices/testdev/diag/loopback/2")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 2
        assert body["enabled"] == 1
        assert body["ltssm_speed"] == 3
        registered_device.diagnostics.loopback_get.assert_called_once_with(2)

    def test_loopback_set_happy_path(self, client, registered_device):
        """POST loopback set should invoke DiagnosticsManager.loopback_set."""
        response = client.post(
            "/api/devices/testdev/diag/loopback/4",
            json={"enable": True, "ltssm_speed": 3},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.diagnostics.loopback_set.assert_called_once()
        call_kwargs = registered_device.diagnostics.loopback_set.call_args
        assert call_kwargs[0][0] == 4  # port_id positional arg
        assert call_kwargs[1]["enable"] is True

    def test_loopback_set_defaults(self, client, registered_device):
        """POST loopback set with empty body should use defaults."""
        response = client.post(
            "/api/devices/testdev/diag/loopback/0",
            json={},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.diagnostics.loopback_set.assert_called_once()

    def test_pattern_gen_set_happy_path(self, client, registered_device):
        """POST pattern gen should invoke DiagnosticsManager.pattern_gen_set."""
        response = client.post(
            "/api/devices/testdev/diag/patgen/1",
            json={"pattern": 3, "link_speed": 4},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.diagnostics.pattern_gen_set.assert_called_once()
        call_kwargs = registered_device.diagnostics.pattern_gen_set.call_args
        assert call_kwargs[0][0] == 1  # port_id

    def test_pattern_mon_get_happy_path(self, client, registered_device):
        """GET pattern monitor should return PatternMonResult."""
        from serialcables_switchtec.models.diagnostics import PatternMonResult

        registered_device.diagnostics.pattern_mon_get.return_value = PatternMonResult(
            port_id=5, lane_id=2, pattern_type=3, error_count=42,
        )
        response = client.get("/api/devices/testdev/diag/patmon/5/2")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 5
        assert body["lane_id"] == 2
        assert body["pattern_type"] == 3
        assert body["error_count"] == 42
        registered_device.diagnostics.pattern_mon_get.assert_called_once_with(5, 2)

    def test_inject_dllp_happy_path(self, client, registered_device):
        """POST DLLP inject should invoke ErrorInjector.inject_dllp."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/dllp/7",
                json={"data": 0xDEADBEEF},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "injected"}
        mock_injector.inject_dllp.assert_called_once_with(7, 0xDEADBEEF)

    def test_inject_dllp_crc_happy_path(self, client, registered_device):
        """POST DLLP CRC inject should invoke ErrorInjector.inject_dllp_crc."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/dllp-crc/3",
                json={"enable": True, "rate": 10},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_injector.inject_dllp_crc.assert_called_once_with(3, True, 10)

    def test_inject_dllp_crc_defaults(self, client, registered_device):
        """POST DLLP CRC inject with empty body should use defaults."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/dllp-crc/0",
                json={},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_injector.inject_dllp_crc.assert_called_once_with(0, True, 1)

    def test_inject_cto_happy_path(self, client, registered_device):
        """POST CTO inject should invoke ErrorInjector.inject_cto."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/cto/12",
            )
        assert response.status_code == 200
        assert response.json() == {"status": "injected"}
        mock_injector.inject_cto.assert_called_once_with(12)

    def test_inject_tlp_lcrc_happy_path(self, client, registered_device):
        """POST TLP LCRC inject should invoke ErrorInjector.inject_tlp_lcrc."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/tlp-lcrc/4",
                json={"enable": True, "rate": 5},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_injector.inject_tlp_lcrc.assert_called_once_with(4, True, 5)

    def test_inject_tlp_lcrc_defaults(self, client, registered_device):
        """POST TLP LCRC inject with empty body should use defaults."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/tlp-lcrc/0",
                json={},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_injector.inject_tlp_lcrc.assert_called_once_with(0, True, 1)

    def test_inject_tlp_lcrc_disable(self, client, registered_device):
        """POST TLP LCRC inject with enable=False should disable injection."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/tlp-lcrc/2",
                json={"enable": False, "rate": 0},
            )
        assert response.status_code == 200
        mock_injector.inject_tlp_lcrc.assert_called_once_with(2, False, 0)

    def test_inject_tlp_lcrc_not_found(self, client):
        """POST TLP LCRC inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/tlp-lcrc/0",
            json={},
        )
        assert response.status_code == 404

    def test_inject_tlp_lcrc_invalid_port(self, client, registered_device):
        """POST TLP LCRC inject with port > 59 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/tlp-lcrc/100",
            json={},
        )
        assert response.status_code == 422

    def test_inject_tlp_lcrc_invalid_rate(self, client, registered_device):
        """POST TLP LCRC inject with rate > 255 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/tlp-lcrc/0",
            json={"rate": 999},
        )
        assert response.status_code == 422

    def test_inject_seq_num_happy_path(self, client, registered_device):
        """POST seq-num inject should invoke ErrorInjector.inject_tlp_seq_num."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/seq-num/8",
            )
        assert response.status_code == 200
        assert response.json() == {"status": "injected"}
        mock_injector.inject_tlp_seq_num.assert_called_once_with(8)

    def test_inject_seq_num_not_found(self, client):
        """POST seq-num inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/seq-num/0",
        )
        assert response.status_code == 404

    def test_inject_seq_num_invalid_port(self, client, registered_device):
        """POST seq-num inject with port > 59 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/seq-num/60",
        )
        assert response.status_code == 422

    def test_inject_ack_nack_happy_path(self, client, registered_device):
        """POST ack-nack inject should invoke ErrorInjector.inject_ack_nack."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/ack-nack/6",
                json={"seq_num": 100, "count": 3},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "injected"}
        mock_injector.inject_ack_nack.assert_called_once_with(6, 100, 3)

    def test_inject_ack_nack_default_count(self, client, registered_device):
        """POST ack-nack inject should default count to 1."""
        mock_injector = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/ack-nack/0",
                json={"seq_num": 50, "count": 1},
            )
        assert response.status_code == 200
        mock_injector.inject_ack_nack.assert_called_once_with(0, 50, 1)

    def test_inject_ack_nack_not_found(self, client):
        """POST ack-nack inject for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/inject/ack-nack/0",
            json={"seq_num": 0, "count": 1},
        )
        assert response.status_code == 404

    def test_inject_ack_nack_invalid_port(self, client, registered_device):
        """POST ack-nack inject with port > 59 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/ack-nack/100",
            json={"seq_num": 0, "count": 1},
        )
        assert response.status_code == 422

    def test_inject_ack_nack_missing_seq_num(self, client, registered_device):
        """POST ack-nack inject without seq_num should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/ack-nack/0",
            json={"count": 1},
        )
        assert response.status_code == 422

    def test_inject_ack_nack_invalid_count(self, client, registered_device):
        """POST ack-nack inject with count > 255 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/inject/ack-nack/0",
            json={"seq_num": 0, "count": 300},
        )
        assert response.status_code == 422

    def test_rcvr_obj_happy_path(self, client, registered_device):
        """GET receiver object should return ReceiverObject from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import ReceiverObject

        registered_device.diagnostics.rcvr_obj.return_value = ReceiverObject(
            port_id=1,
            lane_id=0,
            ctle=5,
            target_amplitude=100,
            speculative_dfe=3,
            dynamic_dfe=[10, 20, 30, 40, 50, 60, 70],
        )
        response = client.get("/api/devices/testdev/diag/rcvr/1/0")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 1
        assert body["lane_id"] == 0
        assert body["ctle"] == 5
        assert body["target_amplitude"] == 100
        assert body["dynamic_dfe"] == [10, 20, 30, 40, 50, 60, 70]
        registered_device.diagnostics.rcvr_obj.assert_called_once()

    def test_rcvr_obj_previous_link(self, client, registered_device):
        """GET receiver object with link=previous should pass DiagLink.PREVIOUS."""
        from serialcables_switchtec.bindings.constants import DiagLink
        from serialcables_switchtec.models.diagnostics import ReceiverObject

        registered_device.diagnostics.rcvr_obj.return_value = ReceiverObject(
            port_id=0, lane_id=0, ctle=0, target_amplitude=0,
            speculative_dfe=0, dynamic_dfe=[0, 0, 0, 0, 0, 0, 0],
        )
        response = client.get(
            "/api/devices/testdev/diag/rcvr/0/0?link=previous"
        )
        assert response.status_code == 200
        call_kwargs = registered_device.diagnostics.rcvr_obj.call_args
        assert call_kwargs[1]["link"] == DiagLink.PREVIOUS

    def test_port_eq_coeff_happy_path(self, client, registered_device):
        """GET EQ coefficients should return PortEqCoeff from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import EqCursor, PortEqCoeff

        registered_device.diagnostics.port_eq_tx_coeff.return_value = PortEqCoeff(
            lane_count=2,
            cursors=[
                EqCursor(pre=-6, post=-12),
                EqCursor(pre=-4, post=-8),
            ],
        )
        response = client.get("/api/devices/testdev/diag/eq/0")
        assert response.status_code == 200
        body = response.json()
        assert body["lane_count"] == 2
        assert len(body["cursors"]) == 2
        assert body["cursors"][0]["pre"] == -6
        assert body["cursors"][1]["post"] == -8
        registered_device.diagnostics.port_eq_tx_coeff.assert_called_once()

    def test_port_eq_coeff_far_end_previous(self, client, registered_device):
        """GET EQ coefficients with end=far_end and link=previous should pass correct enums."""
        from serialcables_switchtec.bindings.constants import DiagEnd, DiagLink
        from serialcables_switchtec.models.diagnostics import PortEqCoeff

        registered_device.diagnostics.port_eq_tx_coeff.return_value = PortEqCoeff(
            lane_count=0, cursors=[],
        )
        response = client.get(
            "/api/devices/testdev/diag/eq/10?end=far_end&link=previous"
        )
        assert response.status_code == 200
        call_kwargs = registered_device.diagnostics.port_eq_tx_coeff.call_args
        assert call_kwargs[0][0] == 10  # port_id
        assert call_kwargs[1]["end"] == DiagEnd.FAR_END
        assert call_kwargs[1]["link"] == DiagLink.PREVIOUS

    def test_crosshair_enable_happy_path(self, client, registered_device):
        """POST crosshair enable should invoke DiagnosticsManager.cross_hair_enable."""
        response = client.post(
            "/api/devices/testdev/diag/crosshair/enable/5",
        )
        assert response.status_code == 200
        assert response.json() == {"status": "enabled"}
        registered_device.diagnostics.cross_hair_enable.assert_called_once_with(5)

    def test_crosshair_disable_happy_path(self, client, registered_device):
        """POST crosshair disable should invoke DiagnosticsManager.cross_hair_disable."""
        response = client.post(
            "/api/devices/testdev/diag/crosshair/disable",
        )
        assert response.status_code == 200
        assert response.json() == {"status": "disabled"}
        registered_device.diagnostics.cross_hair_disable.assert_called_once()

    def test_crosshair_get_happy_path(self, client, registered_device):
        """GET crosshair should return CrossHairResult list from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import CrossHairResult

        registered_device.diagnostics.cross_hair_get.return_value = [
            CrossHairResult(
                lane_id=0,
                state=2,
                state_name="DONE",
                eye_left_lim=-32,
                eye_right_lim=32,
                eye_bot_left_lim=-100,
                eye_bot_right_lim=-80,
                eye_top_left_lim=100,
                eye_top_right_lim=80,
            ),
        ]
        response = client.get(
            "/api/devices/testdev/diag/crosshair?start_lane=0&num_lanes=1"
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["lane_id"] == 0
        assert body[0]["state_name"] == "DONE"
        assert body[0]["eye_left_lim"] == -32
        assert body[0]["eye_right_lim"] == 32
        registered_device.diagnostics.cross_hair_get.assert_called_once_with(0, 1)

    def test_crosshair_get_defaults(self, client, registered_device):
        """GET crosshair without query params should use defaults."""
        registered_device.diagnostics.cross_hair_get.return_value = []
        response = client.get("/api/devices/testdev/diag/crosshair")
        assert response.status_code == 200
        registered_device.diagnostics.cross_hair_get.assert_called_once_with(0, 1)

    # -- Error-path tests (exception handling in route handlers) -----------

    def test_eye_start_error_maps_to_http(self, client, registered_device):
        """eye_start raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.eye_start.side_effect = InvalidPortError("bad port", error_code=2)
        response = client.post(
            "/api/devices/testdev/diag/eye/start", json={},
        )
        assert response.status_code == 400

    def test_eye_cancel_error_maps_to_http(self, client, registered_device):
        """eye_cancel raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.eye_cancel.side_effect = SwitchtecTimeoutError(
            "timed out", error_code=6
        )
        response = client.post("/api/devices/testdev/diag/eye/cancel")
        assert response.status_code == 504

    def test_ltssm_log_error_maps_to_http(self, client, registered_device):
        """ltssm_log raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.ltssm_log.side_effect = InvalidPortError("bad port", error_code=2)
        response = client.get("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 400

    def test_ltssm_clear_error_maps_to_http(self, client, registered_device):
        """ltssm_clear raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.ltssm_clear.side_effect = InvalidPortError(
            "bad port", error_code=2
        )
        response = client.delete("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 400

    def test_loopback_get_error_maps_to_http(self, client, registered_device):
        """loopback_get raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.loopback_get.side_effect = UnsupportedError(
            "not supported", error_code=7
        )
        response = client.get("/api/devices/testdev/diag/loopback/0")
        assert response.status_code == 501

    def test_loopback_set_error_maps_to_http(self, client, registered_device):
        """loopback_set raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.loopback_set.side_effect = InvalidParameterError(
            "bad param", error_code=4
        )
        response = client.post(
            "/api/devices/testdev/diag/loopback/0", json={},
        )
        assert response.status_code == 400

    def test_pattern_gen_set_error_maps_to_http(self, client, registered_device):
        """pattern_gen_set raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.pattern_gen_set.side_effect = MrpcError(
            "mrpc failed", error_code=9
        )
        response = client.post(
            "/api/devices/testdev/diag/patgen/0", json={},
        )
        assert response.status_code == 502

    def test_pattern_mon_get_error_maps_to_http(self, client, registered_device):
        """pattern_mon_get raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.pattern_mon_get.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        response = client.get("/api/devices/testdev/diag/patmon/0/0")
        assert response.status_code == 400

    def test_inject_dllp_error_maps_to_http(self, client, registered_device):
        """inject_dllp raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_dllp.side_effect = SwitchtecPermissionError(
            "denied", error_code=5
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/dllp/0",
                json={"data": 0},
            )
        assert response.status_code == 403

    def test_inject_dllp_crc_error_maps_to_http(self, client, registered_device):
        """inject_dllp_crc raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_dllp_crc.side_effect = DeviceOpenError(
            "open failed", error_code=8
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/dllp-crc/0", json={},
            )
        assert response.status_code == 502

    def test_inject_cto_error_maps_to_http(self, client, registered_device):
        """inject_cto raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_cto.side_effect = SwitchtecTimeoutError(
            "timed out", error_code=6
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/cto/0",
            )
        assert response.status_code == 504

    def test_inject_tlp_lcrc_error_maps_to_http(
        self, client, registered_device
    ):
        """inject_tlp_lcrc raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_tlp_lcrc.side_effect = MrpcError(
            "mrpc failed", error_code=9
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/tlp-lcrc/0", json={},
            )
        assert response.status_code == 502

    def test_inject_seq_num_error_maps_to_http(
        self, client, registered_device
    ):
        """inject_seq_num raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_tlp_seq_num.side_effect = InvalidPortError(
            "bad port", error_code=2
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/seq-num/0",
            )
        assert response.status_code == 400

    def test_inject_ack_nack_error_maps_to_http(
        self, client, registered_device
    ):
        """inject_ack_nack raising SwitchtecError should be mapped to HTTP error."""
        mock_injector = MagicMock()
        mock_injector.inject_ack_nack.side_effect = SwitchtecPermissionError(
            "denied", error_code=5
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.ErrorInjector",
            return_value=mock_injector,
        ):
            response = client.post(
                "/api/devices/testdev/diag/inject/ack-nack/0",
                json={"seq_num": 0, "count": 1},
            )
        assert response.status_code == 403

    def test_rcvr_obj_error_maps_to_http(self, client, registered_device):
        """rcvr_obj raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.rcvr_obj.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        response = client.get("/api/devices/testdev/diag/rcvr/0/0")
        assert response.status_code == 400

    def test_port_eq_coeff_error_maps_to_http(self, client, registered_device):
        """port_eq_tx_coeff raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.port_eq_tx_coeff.side_effect = UnsupportedError(
            "not supported", error_code=7
        )
        response = client.get("/api/devices/testdev/diag/eq/0")
        assert response.status_code == 501

    def test_crosshair_enable_error_maps_to_http(self, client, registered_device):
        """cross_hair_enable raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.cross_hair_enable.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        response = client.post(
            "/api/devices/testdev/diag/crosshair/enable/0",
        )
        assert response.status_code == 400

    def test_crosshair_disable_error_maps_to_http(self, client, registered_device):
        """cross_hair_disable raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.cross_hair_disable.side_effect = MrpcError(
            "mrpc failed", error_code=9
        )
        response = client.post(
            "/api/devices/testdev/diag/crosshair/disable",
        )
        assert response.status_code == 502

    def test_crosshair_get_error_maps_to_http(self, client, registered_device):
        """cross_hair_get raising SwitchtecError should be mapped to HTTP error."""
        registered_device.diagnostics.cross_hair_get.side_effect = SwitchtecTimeoutError(
            "timed out", error_code=6
        )
        response = client.get("/api/devices/testdev/diag/crosshair")
        assert response.status_code == 504
