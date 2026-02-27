"""API route integration tests (health, auth, device, port, path validation, lifespan)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.api.state import DEVICE_PATH_PATTERN
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


# -- Auth ---------------------------------------------------------------


class TestAuth:
    """API key authentication tests."""

    def test_api_key_not_configured(self, monkeypatch, app):
        """Requests should succeed when SWITCHTEC_API_KEY is not set (auth disabled)."""
        monkeypatch.delenv("SWITCHTEC_API_KEY", raising=False)
        with TestClient(app) as tc:
            response = tc.get("/api/health")
            assert response.status_code == 200
            # Device routes should pass through when auth is disabled
            response = tc.get("/api/devices/")
            assert response.status_code == 200

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


# -- Device routes -------------------------------------------------------


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


# -- Port routes ---------------------------------------------------------


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


# -- Device path validation ----------------------------------------------


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


# -- Lifespan shutdown ----------------------------------------------------


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
