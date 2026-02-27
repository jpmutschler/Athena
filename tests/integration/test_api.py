"""API route integration tests."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from serialcables_switchtec.api.error_handlers import _STATUS_MAP, raise_on_error
from serialcables_switchtec.api.state import DEVICE_PATH_PATTERN
from serialcables_switchtec.exceptions import (
    DeviceNotFoundError,
    DeviceOpenError,
    InvalidLaneError,
    InvalidParameterError,
    InvalidPortError,
    MrpcError,
    SwitchtecError,
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


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ── Auth ────────────────────────────────────────────────────────────────


class TestAuth:
    """API key authentication tests."""

    def test_api_key_not_configured(self, monkeypatch, app):
        """Requests should get 503 when SWITCHTEC_API_KEY is not set."""
        monkeypatch.delenv("SWITCHTEC_API_KEY", raising=False)
        with TestClient(app) as tc:
            response = tc.get("/api/health")
            # Health endpoint has no auth dependency, so it passes
            assert response.status_code == 200
            # Device routes should return 503 when API key is not configured
            response = tc.get("/api/devices/")
            assert response.status_code == 503

    def test_api_key_required(self, monkeypatch, app):
        """Requests without an API key header should be rejected when key is set."""
        monkeypatch.setenv("SWITCHTEC_API_KEY", "secret-key-123")
        with TestClient(app) as tc:
            response = tc.get("/api/health")
            # Health endpoint has no auth dependency, so it passes
            assert response.status_code == 200
            # Device routes DO require auth
            response = tc.get("/api/devices/")
            assert response.status_code == 403

    def test_api_key_valid(self, monkeypatch, app):
        """Correct API key header should allow access."""
        monkeypatch.setenv("SWITCHTEC_API_KEY", "secret-key-123")
        with TestClient(app) as tc:
            response = tc.get(
                "/api/devices/",
                headers={"X-API-Key": "secret-key-123"},
            )
            assert response.status_code == 200

    def test_api_key_invalid(self, monkeypatch, app):
        """Wrong API key header should be rejected."""
        monkeypatch.setenv("SWITCHTEC_API_KEY", "secret-key-123")
        with TestClient(app) as tc:
            response = tc.get(
                "/api/devices/",
                headers={"X-API-Key": "wrong-key"},
            )
            assert response.status_code == 403


# ── Device routes ───────────────────────────────────────────────────────


class TestDeviceRoutes:
    def test_list_empty(self, client):
        response = client.get("/api/devices/")
        assert response.status_code == 200
        assert response.json() == []

    def test_close_not_found(self, client):
        response = client.delete("/api/devices/nonexistent")
        assert response.status_code == 404

    def test_get_not_found(self, client):
        response = client.get("/api/devices/nonexistent")
        assert response.status_code == 404

    def test_temperature_not_found(self, client):
        response = client.get("/api/devices/nonexistent/temperature")
        assert response.status_code == 404

    def test_invalid_device_id(self, client):
        """Device IDs with special characters should be rejected."""
        response = client.post(
            "/api/devices/bad%20id/open",
            json={"path": "/dev/switchtec0"},
        )
        assert response.status_code == 422

    def test_open_device_invalid_path(self, client):
        """Path traversal attempts should be rejected by validation."""
        response = client.post(
            "/api/devices/dev1/open",
            json={"path": "../../etc/passwd"},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "path",
        [
            "/dev/switchtec0",
            "\\\\.\\switchtec0",
            "0",
        ],
    )
    def test_open_device_valid_path_formats(self, path):
        """Valid device path formats should match DEVICE_PATH_PATTERN."""
        assert DEVICE_PATH_PATTERN.match(path) is not None

    def test_get_device_happy_path(self, client, registered_device):
        """GET device info should return a DeviceSummary for a registered device."""
        response = client.get("/api/devices/testdev")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "PSX48XG5"
        assert body["generation"] == "Gen5"
        assert body["port_count"] == 48
        registered_device.get_summary.assert_called_once()

    def test_temperature_happy_path(self, client, registered_device):
        """GET temperature should return die temperature for a registered device."""
        response = client.get("/api/devices/testdev/temperature")
        assert response.status_code == 200
        body = response.json()
        assert body["temperature_c"] == 42.5

    def test_open_device_happy_path(self, client):
        """POST open should register a device and return its summary."""
        summary = DeviceSummary(
            name="PSX48XG5",
            device_id=0x5A00,
            generation="Gen5",
            variant="PSX",
            boot_phase="BL2",
            partition=0,
            fw_version="4.70B058",
            die_temperature=40.0,
            port_count=48,
        )
        mock_dev = MagicMock()
        mock_dev.get_summary.return_value = summary

        with patch(
            "serialcables_switchtec.api.routes.devices.SwitchtecDevice.open",
            return_value=mock_dev,
        ):
            response = client.post(
                "/api/devices/mydev/open",
                json={"path": "/dev/switchtec0"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["name"] == "PSX48XG5"
            assert body["fw_version"] == "4.70B058"

        # Cleanup: remove from registry
        from serialcables_switchtec.api.state import get_device_registry

        get_device_registry().pop("mydev", None)

    def test_open_device_conflict(self, client, registered_device):
        """Opening an already-open device should return 409."""
        response = client.post(
            "/api/devices/testdev/open",
            json={"path": "/dev/switchtec0"},
        )
        assert response.status_code == 409

    def test_close_device_happy_path(self, client, registered_device):
        """DELETE should close the device and remove it from the registry."""
        response = client.delete("/api/devices/testdev")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "closed"
        registered_device.close.assert_called_once()

    def test_list_with_registered_device(self, client, registered_device):
        """GET list should include a registered device."""
        response = client.get("/api/devices/")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == "testdev"
        assert body[0]["path"] == "/dev/switchtec0"


# ── Port routes ─────────────────────────────────────────────────────────


class TestPortRoutes:
    def test_ports_not_found(self, client):
        """GET ports for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/ports")
        assert response.status_code == 404

    def test_ports_happy_path(self, client, registered_device):
        """GET ports should return port status list for a registered device."""
        response = client.get("/api/devices/testdev/ports")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        port = body[0]
        assert port["port"]["phys_id"] == 0
        assert port["link_up"] is True
        assert port["neg_lnk_width"] == 16
        registered_device.get_status.assert_called_once()

    def test_port_pff_not_found(self, client):
        """GET PFF for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/ports/0/pff")
        assert response.status_code == 404

    def test_port_pff_happy_path(self, client, registered_device):
        """GET PFF should return the PFF index for a port."""
        response = client.get("/api/devices/testdev/ports/0/pff")
        assert response.status_code == 200
        body = response.json()
        assert body["phys_port_id"] == 0
        assert body["pff"] == 3


# ── Diagnostic routes ───────────────────────────────────────────────────


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

    # ── Success-path tests (registered device) ──────────────────────────

    def test_eye_start_happy_path(self, client, registered_device):
        """POST eye start should invoke DiagnosticsManager.eye_start and return started."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
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
        mock_diag.eye_start.assert_called_once_with(
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
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/eye/start",
                json={},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "started"}
        mock_diag.eye_start.assert_called_once()

    def test_eye_cancel_happy_path(self, client, registered_device):
        """POST eye cancel should invoke DiagnosticsManager.eye_cancel."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post("/api/devices/testdev/diag/eye/cancel")
        assert response.status_code == 200
        assert response.json() == {"status": "cancelled"}
        mock_diag.eye_cancel.assert_called_once()

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
        mock_diag = MagicMock()
        mock_diag.ltssm_log.return_value = mock_entries
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["timestamp"] == 1000
        assert body[0]["link_state_str"] == "L0"
        assert body[0]["link_width"] == 16
        mock_diag.ltssm_log.assert_called_once_with(0, max_entries=64)

    def test_ltssm_log_custom_max_entries(self, client, registered_device):
        """GET LTSSM log should pass custom max_entries query param."""
        mock_diag = MagicMock()
        mock_diag.ltssm_log.return_value = []
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get(
                "/api/devices/testdev/diag/ltssm/5?max_entries=128"
            )
        assert response.status_code == 200
        mock_diag.ltssm_log.assert_called_once_with(5, max_entries=128)

    def test_ltssm_clear_happy_path(self, client, registered_device):
        """DELETE LTSSM log should invoke DiagnosticsManager.ltssm_clear."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.delete("/api/devices/testdev/diag/ltssm/3")
        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}
        mock_diag.ltssm_clear.assert_called_once_with(3)

    def test_loopback_get_happy_path(self, client, registered_device):
        """GET loopback should return LoopbackStatus from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import LoopbackStatus

        mock_diag = MagicMock()
        mock_diag.loopback_get.return_value = LoopbackStatus(
            port_id=2, enabled=1, ltssm_speed=3,
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/loopback/2")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 2
        assert body["enabled"] == 1
        assert body["ltssm_speed"] == 3
        mock_diag.loopback_get.assert_called_once_with(2)

    def test_loopback_set_happy_path(self, client, registered_device):
        """POST loopback set should invoke DiagnosticsManager.loopback_set."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/loopback/4",
                json={"enable": True, "ltssm_speed": 3},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_diag.loopback_set.assert_called_once()
        call_kwargs = mock_diag.loopback_set.call_args
        assert call_kwargs[0][0] == 4  # port_id positional arg
        assert call_kwargs[1]["enable"] is True

    def test_loopback_set_defaults(self, client, registered_device):
        """POST loopback set with empty body should use defaults."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/loopback/0",
                json={},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_diag.loopback_set.assert_called_once()

    def test_pattern_gen_set_happy_path(self, client, registered_device):
        """POST pattern gen should invoke DiagnosticsManager.pattern_gen_set."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/patgen/1",
                json={"pattern": 3, "link_speed": 4},
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_diag.pattern_gen_set.assert_called_once()
        call_kwargs = mock_diag.pattern_gen_set.call_args
        assert call_kwargs[0][0] == 1  # port_id

    def test_pattern_mon_get_happy_path(self, client, registered_device):
        """GET pattern monitor should return PatternMonResult."""
        from serialcables_switchtec.models.diagnostics import PatternMonResult

        mock_diag = MagicMock()
        mock_diag.pattern_mon_get.return_value = PatternMonResult(
            port_id=5, lane_id=2, pattern_type=3, error_count=42,
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/patmon/5/2")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 5
        assert body["lane_id"] == 2
        assert body["pattern_type"] == 3
        assert body["error_count"] == 42
        mock_diag.pattern_mon_get.assert_called_once_with(5, 2)

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

    def test_rcvr_obj_happy_path(self, client, registered_device):
        """GET receiver object should return ReceiverObject from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import ReceiverObject

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.return_value = ReceiverObject(
            port_id=1,
            lane_id=0,
            ctle=5,
            target_amplitude=100,
            speculative_dfe=3,
            dynamic_dfe=[10, 20, 30, 40, 50, 60, 70],
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/rcvr/1/0")
        assert response.status_code == 200
        body = response.json()
        assert body["port_id"] == 1
        assert body["lane_id"] == 0
        assert body["ctle"] == 5
        assert body["target_amplitude"] == 100
        assert body["dynamic_dfe"] == [10, 20, 30, 40, 50, 60, 70]
        mock_diag.rcvr_obj.assert_called_once()

    def test_rcvr_obj_previous_link(self, client, registered_device):
        """GET receiver object with link=previous should pass DiagLink.PREVIOUS."""
        from serialcables_switchtec.bindings.constants import DiagLink
        from serialcables_switchtec.models.diagnostics import ReceiverObject

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.return_value = ReceiverObject(
            port_id=0, lane_id=0, ctle=0, target_amplitude=0,
            speculative_dfe=0, dynamic_dfe=[0, 0, 0, 0, 0, 0, 0],
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get(
                "/api/devices/testdev/diag/rcvr/0/0?link=previous"
            )
        assert response.status_code == 200
        call_kwargs = mock_diag.rcvr_obj.call_args
        assert call_kwargs[1]["link"] == DiagLink.PREVIOUS

    def test_port_eq_coeff_happy_path(self, client, registered_device):
        """GET EQ coefficients should return PortEqCoeff from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import EqCursor, PortEqCoeff

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.return_value = PortEqCoeff(
            lane_count=2,
            cursors=[
                EqCursor(pre=-6, post=-12),
                EqCursor(pre=-4, post=-8),
            ],
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/eq/0")
        assert response.status_code == 200
        body = response.json()
        assert body["lane_count"] == 2
        assert len(body["cursors"]) == 2
        assert body["cursors"][0]["pre"] == -6
        assert body["cursors"][1]["post"] == -8
        mock_diag.port_eq_tx_coeff.assert_called_once()

    def test_port_eq_coeff_far_end_previous(self, client, registered_device):
        """GET EQ coefficients with end=far_end and link=previous should pass correct enums."""
        from serialcables_switchtec.bindings.constants import DiagEnd, DiagLink
        from serialcables_switchtec.models.diagnostics import PortEqCoeff

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.return_value = PortEqCoeff(
            lane_count=0, cursors=[],
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get(
                "/api/devices/testdev/diag/eq/10?end=far_end&link=previous"
            )
        assert response.status_code == 200
        call_kwargs = mock_diag.port_eq_tx_coeff.call_args
        assert call_kwargs[0][0] == 10  # port_id
        assert call_kwargs[1]["end"] == DiagEnd.FAR_END
        assert call_kwargs[1]["link"] == DiagLink.PREVIOUS

    def test_crosshair_enable_happy_path(self, client, registered_device):
        """POST crosshair enable should invoke DiagnosticsManager.cross_hair_enable."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/crosshair/enable/5",
            )
        assert response.status_code == 200
        assert response.json() == {"status": "enabled"}
        mock_diag.cross_hair_enable.assert_called_once_with(5)

    def test_crosshair_disable_happy_path(self, client, registered_device):
        """POST crosshair disable should invoke DiagnosticsManager.cross_hair_disable."""
        mock_diag = MagicMock()
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/crosshair/disable",
            )
        assert response.status_code == 200
        assert response.json() == {"status": "disabled"}
        mock_diag.cross_hair_disable.assert_called_once()

    def test_crosshair_get_happy_path(self, client, registered_device):
        """GET crosshair should return CrossHairResult list from DiagnosticsManager."""
        from serialcables_switchtec.models.diagnostics import CrossHairResult

        mock_diag = MagicMock()
        mock_diag.cross_hair_get.return_value = [
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
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
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
        mock_diag.cross_hair_get.assert_called_once_with(0, 1)

    def test_crosshair_get_defaults(self, client, registered_device):
        """GET crosshair without query params should use defaults."""
        mock_diag = MagicMock()
        mock_diag.cross_hair_get.return_value = []
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/crosshair")
        assert response.status_code == 200
        mock_diag.cross_hair_get.assert_called_once_with(0, 1)

    # ── Error-path tests (exception handling in route handlers) ─────────

    def test_eye_start_error_maps_to_http(self, client, registered_device):
        """eye_start raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.eye_start.side_effect = InvalidPortError("bad port", error_code=2)
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/eye/start", json={},
            )
        assert response.status_code == 400

    def test_eye_cancel_error_maps_to_http(self, client, registered_device):
        """eye_cancel raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.eye_cancel.side_effect = SwitchtecTimeoutError(
            "timed out", error_code=6
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post("/api/devices/testdev/diag/eye/cancel")
        assert response.status_code == 504

    def test_ltssm_log_error_maps_to_http(self, client, registered_device):
        """ltssm_log raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.ltssm_log.side_effect = InvalidPortError("bad port", error_code=2)
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 400

    def test_ltssm_clear_error_maps_to_http(self, client, registered_device):
        """ltssm_clear raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.ltssm_clear.side_effect = InvalidPortError(
            "bad port", error_code=2
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.delete("/api/devices/testdev/diag/ltssm/0")
        assert response.status_code == 400

    def test_loopback_get_error_maps_to_http(self, client, registered_device):
        """loopback_get raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.loopback_get.side_effect = UnsupportedError(
            "not supported", error_code=7
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/loopback/0")
        assert response.status_code == 501

    def test_loopback_set_error_maps_to_http(self, client, registered_device):
        """loopback_set raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.loopback_set.side_effect = InvalidParameterError(
            "bad param", error_code=4
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/loopback/0", json={},
            )
        assert response.status_code == 400

    def test_pattern_gen_set_error_maps_to_http(self, client, registered_device):
        """pattern_gen_set raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.pattern_gen_set.side_effect = MrpcError(
            "mrpc failed", error_code=9
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/patgen/0", json={},
            )
        assert response.status_code == 502

    def test_pattern_mon_get_error_maps_to_http(self, client, registered_device):
        """pattern_mon_get raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.pattern_mon_get.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
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

    def test_rcvr_obj_error_maps_to_http(self, client, registered_device):
        """rcvr_obj raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.rcvr_obj.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/rcvr/0/0")
        assert response.status_code == 400

    def test_port_eq_coeff_error_maps_to_http(self, client, registered_device):
        """port_eq_tx_coeff raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.side_effect = UnsupportedError(
            "not supported", error_code=7
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/eq/0")
        assert response.status_code == 501

    def test_crosshair_enable_error_maps_to_http(self, client, registered_device):
        """cross_hair_enable raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.cross_hair_enable.side_effect = InvalidLaneError(
            "bad lane", error_code=3
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/crosshair/enable/0",
            )
        assert response.status_code == 400

    def test_crosshair_disable_error_maps_to_http(self, client, registered_device):
        """cross_hair_disable raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.cross_hair_disable.side_effect = MrpcError(
            "mrpc failed", error_code=9
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.post(
                "/api/devices/testdev/diag/crosshair/disable",
            )
        assert response.status_code == 502

    def test_crosshair_get_error_maps_to_http(self, client, registered_device):
        """cross_hair_get raising SwitchtecError should be mapped to HTTP error."""
        mock_diag = MagicMock()
        mock_diag.cross_hair_get.side_effect = SwitchtecTimeoutError(
            "timed out", error_code=6
        )
        with patch(
            "serialcables_switchtec.api.routes.diagnostics.DiagnosticsManager",
            return_value=mock_diag,
        ):
            response = client.get("/api/devices/testdev/diag/crosshair")
        assert response.status_code == 504


# ── Error handlers ──────────────────────────────────────────────────────


class TestErrorHandlers:
    """Tests for the raise_on_error function and _STATUS_MAP."""

    def test_raise_on_error_switchtec_error_base(self):
        """Base SwitchtecError should map to 500."""
        exc = SwitchtecError("generic failure", error_code=99)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "test_op")
        assert exc_info.value.status_code == 500
        assert "generic failure" in exc_info.value.detail

    def test_raise_on_error_device_not_found(self):
        """DeviceNotFoundError should map to 404."""
        exc = DeviceNotFoundError("device missing", error_code=1)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "lookup")
        assert exc_info.value.status_code == 404

    def test_raise_on_error_invalid_port(self):
        """InvalidPortError should map to 400."""
        exc = InvalidPortError("bad port", error_code=2)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "port_check")
        assert exc_info.value.status_code == 400

    def test_raise_on_error_invalid_lane(self):
        """InvalidLaneError should map to 400."""
        exc = InvalidLaneError("bad lane", error_code=3)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "lane_check")
        assert exc_info.value.status_code == 400

    def test_raise_on_error_invalid_parameter(self):
        """InvalidParameterError should map to 400."""
        exc = InvalidParameterError("bad param", error_code=4)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "param_check")
        assert exc_info.value.status_code == 400

    def test_raise_on_error_permission(self):
        """SwitchtecPermissionError should map to 403."""
        exc = SwitchtecPermissionError("denied", error_code=5)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "auth_check")
        assert exc_info.value.status_code == 403

    def test_raise_on_error_timeout(self):
        """SwitchtecTimeoutError should map to 504."""
        exc = SwitchtecTimeoutError("timed out", error_code=6)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "timeout_op")
        assert exc_info.value.status_code == 504

    def test_raise_on_error_unsupported(self):
        """UnsupportedError should map to 501."""
        exc = UnsupportedError("not supported", error_code=7)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "unsupported_op")
        assert exc_info.value.status_code == 501

    def test_raise_on_error_device_open(self):
        """DeviceOpenError should map to 502."""
        exc = DeviceOpenError("open failed", error_code=8)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "open_check")
        assert exc_info.value.status_code == 502

    def test_raise_on_error_mrpc(self):
        """MrpcError should map to 502."""
        exc = MrpcError("mrpc failed", error_code=9)
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "mrpc_op")
        assert exc_info.value.status_code == 502

    def test_raise_on_error_unexpected_exception(self):
        """Non-SwitchtecError should map to 500 with generic message."""
        exc = RuntimeError("something broke")
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc, "unexpected_op")
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"

    def test_raise_on_error_no_operation_label(self):
        """raise_on_error works without an operation label."""
        exc = DeviceNotFoundError("missing")
        with pytest.raises(HTTPException) as exc_info:
            raise_on_error(exc)
        assert exc_info.value.status_code == 404

    def test_status_map_completeness(self):
        """All expected exception types should be present in _STATUS_MAP."""
        expected_types = {
            DeviceNotFoundError,
            InvalidPortError,
            InvalidLaneError,
            InvalidParameterError,
            SwitchtecPermissionError,
            SwitchtecTimeoutError,
            UnsupportedError,
            DeviceOpenError,
            MrpcError,
        }
        assert set(_STATUS_MAP.keys()) == expected_types


# ── Device path validation ──────────────────────────────────────────────


class TestDevicePathValidation:
    """Tests for DEVICE_PATH_PATTERN regex from api.state."""

    @pytest.mark.parametrize(
        "path",
        [
            "/dev/switchtec0",
            "/dev/switchtec99",
            "\\\\.\\switchtec0",
            "\\\\.\\switchtec12",
            "0",
            "42",
        ],
    )
    def test_valid_paths(self, path):
        """Valid device paths should match DEVICE_PATH_PATTERN."""
        assert DEVICE_PATH_PATTERN.match(path) is not None

    @pytest.mark.parametrize(
        "path",
        [
            "../etc/passwd",
            "hello world",
            "/dev/../etc/passwd",
            "",
            "/dev/switchtec",
            "switchtec0",
            "/dev/ switchtec0",
            "abc",
            "-1",
        ],
    )
    def test_invalid_paths(self, path):
        """Invalid device paths should not match DEVICE_PATH_PATTERN."""
        assert DEVICE_PATH_PATTERN.match(path) is None


# ── Lifespan shutdown ───────────────────────────────────────────────────


class TestLifespan:
    """Tests for application lifespan shutdown logic."""

    def test_shutdown_closes_devices(self):
        """Devices in the registry should be closed on app shutdown."""
        from serialcables_switchtec.api.app import create_app
        from serialcables_switchtec.api.state import get_device_registry

        app = create_app()
        mock_dev = _make_mock_device()
        registry = get_device_registry()

        with TestClient(app) as tc:
            # Register the device while the app is running
            registry["shutdown-test"] = (mock_dev, "/dev/switchtec0")
            assert "shutdown-test" in registry

        # After exiting the context manager, lifespan shutdown runs
        mock_dev.close.assert_called_once()
        assert len(registry) == 0

    def test_shutdown_handles_close_failure(self):
        """Shutdown should continue even if a device close raises."""
        from serialcables_switchtec.api.app import create_app
        from serialcables_switchtec.api.state import get_device_registry

        app = create_app()
        mock_dev = _make_mock_device()
        mock_dev.close.side_effect = RuntimeError("close failed")
        registry = get_device_registry()

        with TestClient(app) as tc:
            registry["fail-close"] = (mock_dev, "/dev/switchtec0")

        # Registry should be cleared even if close raised
        mock_dev.close.assert_called_once()
        assert len(registry) == 0
