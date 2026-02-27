"""Tests for performance monitoring API routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.device import DeviceSummary, PortId, PortStatus
from serialcables_switchtec.models.performance import (
    BwCounterDirection,
    BwCounterResult,
    LatencyResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


def _sample_bw_results(port_ids: list[int]) -> list[BwCounterResult]:
    """Create sample BwCounterResult objects."""
    return [
        BwCounterResult(
            time_us=1000 * (i + 1),
            egress=BwCounterDirection(posted=100, comp=200, nonposted=50),
            ingress=BwCounterDirection(posted=150, comp=250, nonposted=75),
        )
        for i in range(len(port_ids))
    ]


def _sample_latency_result(port_id: int) -> LatencyResult:
    return LatencyResult(
        egress_port_id=port_id,
        current_ns=42,
        max_ns=128,
    )


# ===========================================================================
# POST /perf/bw
# ===========================================================================


class TestBandwidthRoute:
    """Tests for POST /{device_id}/perf/bw endpoint."""

    def test_bw_device_not_found(self, client) -> None:
        """POST bw for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/perf/bw",
            json={"port_ids": [0, 1]},
        )
        assert response.status_code == 404

    def test_bw_success(self, client, registered_device) -> None:
        registered_device.performance.bw_get.return_value = _sample_bw_results([0, 1])

        response = client.post(
            "/api/devices/testdev/perf/bw",
            json={"port_ids": [0, 1], "clear": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["time_us"] == 1000
        assert data[0]["egress"]["posted"] == 100
        assert data[1]["time_us"] == 2000
        registered_device.performance.bw_get.assert_called_once_with([0, 1], clear=False)

    def test_bw_with_clear(self, client, registered_device) -> None:
        registered_device.performance.bw_get.return_value = _sample_bw_results([5])

        response = client.post(
            "/api/devices/testdev/perf/bw",
            json={"port_ids": [5], "clear": True},
        )

        assert response.status_code == 200
        registered_device.performance.bw_get.assert_called_once_with([5], clear=True)

    def test_bw_empty_port_ids_rejected(self, client, registered_device) -> None:
        """Empty port_ids list should be rejected by validation (min_length=1)."""
        response = client.post(
            "/api/devices/testdev/perf/bw",
            json={"port_ids": []},
        )
        assert response.status_code == 422

    def test_bw_missing_port_ids_rejected(self, client, registered_device) -> None:
        """Missing port_ids field should be rejected by validation."""
        response = client.post(
            "/api/devices/testdev/perf/bw",
            json={},
        )
        assert response.status_code == 422

    def test_bw_error_returns_500(self, client, registered_device) -> None:
        registered_device.performance.bw_get.side_effect = SwitchtecError("hardware failure")

        response = client.post(
            "/api/devices/testdev/perf/bw",
            json={"port_ids": [0]},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Operation failed"


# ===========================================================================
# POST /perf/latency/setup
# ===========================================================================


class TestLatencySetupRoute:
    """Tests for POST /{device_id}/perf/latency/setup endpoint."""

    def test_latency_setup_device_not_found(self, client) -> None:
        response = client.post(
            "/api/devices/nonexistent/perf/latency/setup",
            json={"egress_port_id": 0, "ingress_port_id": 1},
        )
        assert response.status_code == 404

    def test_latency_setup_success(self, client, registered_device) -> None:
        response = client.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": 1, "ingress_port_id": 2, "clear": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "configured"
        registered_device.performance.lat_setup.assert_called_once_with(1, 2, clear=False)

    def test_latency_setup_with_clear(self, client, registered_device) -> None:
        response = client.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": 3, "ingress_port_id": 4, "clear": True},
        )

        assert response.status_code == 200
        registered_device.performance.lat_setup.assert_called_once_with(3, 4, clear=True)

    def test_latency_setup_invalid_port_range(
        self, client, registered_device
    ) -> None:
        """Port IDs outside 0-59 should be rejected by validation."""
        response = client.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": 60, "ingress_port_id": 0},
        )
        assert response.status_code == 422

    def test_latency_setup_negative_port(
        self, client, registered_device
    ) -> None:
        """Negative port IDs should be rejected."""
        response = client.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": -1, "ingress_port_id": 0},
        )
        assert response.status_code == 422

    def test_latency_setup_error_returns_500(self, client, registered_device) -> None:
        registered_device.performance.lat_setup.side_effect = SwitchtecError("setup failed")

        response = client.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": 1, "ingress_port_id": 2},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Operation failed"


# ===========================================================================
# GET /perf/latency/{egress_port_id}
# ===========================================================================


class TestLatencyGetRoute:
    """Tests for GET /{device_id}/perf/latency/{egress_port_id} endpoint."""

    def test_latency_get_device_not_found(self, client) -> None:
        response = client.get(
            "/api/devices/nonexistent/perf/latency/5"
        )
        assert response.status_code == 404

    def test_latency_get_success(self, client, registered_device) -> None:
        registered_device.performance.lat_get.return_value = _sample_latency_result(5)

        response = client.get(
            "/api/devices/testdev/perf/latency/5"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["egress_port_id"] == 5
        assert data["current_ns"] == 42
        assert data["max_ns"] == 128
        registered_device.performance.lat_get.assert_called_once_with(5, clear=False)

    def test_latency_get_with_clear_query(self, client, registered_device) -> None:
        registered_device.performance.lat_get.return_value = _sample_latency_result(3)

        response = client.get(
            "/api/devices/testdev/perf/latency/3?clear=true"
        )

        assert response.status_code == 200
        registered_device.performance.lat_get.assert_called_once_with(3, clear=True)

    def test_latency_get_invalid_port_range(
        self, client, registered_device
    ) -> None:
        """Port ID outside 0-59 should return 422."""
        response = client.get(
            "/api/devices/testdev/perf/latency/60"
        )
        assert response.status_code == 422

    def test_latency_get_negative_port(
        self, client, registered_device
    ) -> None:
        """Negative port ID should return 422."""
        response = client.get(
            "/api/devices/testdev/perf/latency/-1"
        )
        assert response.status_code == 422

    def test_latency_get_error_returns_500(self, client, registered_device) -> None:
        registered_device.performance.lat_get.side_effect = SwitchtecError("read failed")

        response = client.get(
            "/api/devices/testdev/perf/latency/0"
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Operation failed"

    def test_latency_get_invalid_device_id_pattern(self, client) -> None:
        """Device IDs with invalid characters should fail validation."""
        response = client.get(
            "/api/devices/inv@lid!/perf/latency/0"
        )
        assert response.status_code == 422


# ===========================================================================
# Auth tests
# ===========================================================================


class TestPerfAuthRequired:
    """Test that performance routes require authentication."""

    def test_bw_requires_api_key(self, app) -> None:
        """POST bw without API key should return 403."""
        client_no_auth = TestClient(app)
        response = client_no_auth.post(
            "/api/devices/testdev/perf/bw",
            json={"port_ids": [0]},
        )
        assert response.status_code == 403

    def test_latency_setup_requires_api_key(self, app) -> None:
        client_no_auth = TestClient(app)
        response = client_no_auth.post(
            "/api/devices/testdev/perf/latency/setup",
            json={"egress_port_id": 0, "ingress_port_id": 1},
        )
        assert response.status_code == 403

    def test_latency_get_requires_api_key(self, app) -> None:
        client_no_auth = TestClient(app)
        response = client_no_auth.get(
            "/api/devices/testdev/perf/latency/0"
        )
        assert response.status_code == 403
