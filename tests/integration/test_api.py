"""API route integration tests."""

from __future__ import annotations

import os

import pytest

from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _no_api_key(monkeypatch):
    """Ensure SWITCHTEC_API_KEY is not set so auth is skipped."""
    monkeypatch.delenv("SWITCHTEC_API_KEY", raising=False)


@pytest.fixture
def app():
    """Create a test FastAPI app."""
    from serialcables_switchtec.api.app import create_app
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


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
