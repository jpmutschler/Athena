"""Integration tests for SSE monitor API endpoints."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.models.device import DeviceSummary
from serialcables_switchtec.models.performance import (
    BwCounterDirection,
    BwCounterResult,
)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("SWITCHTEC_API_KEY", "test-key")


@pytest.fixture
def app():
    from serialcables_switchtec.api.app import create_app

    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app, headers={"X-API-Key": "test-key"})


def _make_mock_device():
    dev = MagicMock()
    dev.name = "PSX48XG5"
    dev.partition = 0
    dev.die_temperature = 42.5
    dev.get_summary.return_value = DeviceSummary(
        name="PSX48XG5",
        device_id=0x5A00,
        generation="Gen5",
        variant="PSX",
        boot_phase="BL2",
        partition=0,
        fw_version="4.70B058",
        die_temperature=42.5,
        port_count=48,
    )
    dev.performance.bw_get.return_value = [
        BwCounterResult(
            time_us=1000,
            egress=BwCounterDirection(posted=100, comp=50, nonposted=25),
            ingress=BwCounterDirection(posted=80, comp=40, nonposted=20),
        )
    ]
    dev.evcntr.get_counts.return_value = [42]
    dev.close.return_value = None
    return dev


@pytest.fixture
def registered_device(app):
    from serialcables_switchtec.api.state import get_device_registry

    mock_dev = _make_mock_device()
    registry = get_device_registry()
    registry["testdev"] = (mock_dev, "/dev/switchtec0")
    yield mock_dev
    registry.pop("testdev", None)


# ── Bandwidth SSE ────────────────────────────────────────────────────────


class TestMonitorBwEndpoint:
    """GET /{device_id}/monitor/bw SSE tests."""

    def test_not_found(self, client):
        response = client.get(
            "/api/devices/nonexistent/monitor/bw?port_ids=0&count=1"
        )
        assert response.status_code == 404

    def test_invalid_port_ids(self, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=abc&count=1"
        )
        assert response.status_code == 400

    def test_port_out_of_range(self, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=60&count=1"
        )
        assert response.status_code == 400

    def test_empty_port_ids(self, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=&count=1"
        )
        assert response.status_code == 400

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_streams_sse_events(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=0&count=2"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sse_format(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=0&count=1"
        )
        text = response.text
        assert text.startswith("data: ")
        lines = [l for l in text.strip().split("\n") if l.startswith("data: ")]
        data = json.loads(lines[0].removeprefix("data: "))
        assert "port_id" in data
        assert "egress_total" in data
        assert "ingress_total" in data

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_cache_control_header(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=0&count=1"
        )
        assert response.headers.get("cache-control") == "no-cache"

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_multiple_ports(self, mock_sleep, client, registered_device):
        registered_device.performance.bw_get.return_value = [
            BwCounterResult(
                time_us=1000,
                egress=BwCounterDirection(posted=100, comp=50, nonposted=25),
                ingress=BwCounterDirection(posted=80, comp=40, nonposted=20),
            ),
            BwCounterResult(
                time_us=1000,
                egress=BwCounterDirection(posted=200, comp=100, nonposted=50),
                ingress=BwCounterDirection(posted=160, comp=80, nonposted=40),
            ),
        ]
        response = client.get(
            "/api/devices/testdev/monitor/bw?port_ids=0,4&count=1"
        )
        lines = [l for l in response.text.strip().split("\n") if l.startswith("data: ")]
        assert len(lines) == 2


# ── Event Counter SSE ────────────────────────────────────────────────────


class TestMonitorEvCntrEndpoint:
    """GET /{device_id}/monitor/evcntr SSE tests."""

    def test_not_found(self, client):
        response = client.get(
            "/api/devices/nonexistent/monitor/evcntr?stack_id=0&counter_id=0&count=1"
        )
        assert response.status_code == 404

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_streams_sse_events(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/evcntr?stack_id=0&counter_id=0&count=1"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_sse_format(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/evcntr?stack_id=0&counter_id=0&count=1"
        )
        lines = [l for l in response.text.strip().split("\n") if l.startswith("data: ")]
        data = json.loads(lines[0].removeprefix("data: "))
        assert "stack_id" in data
        assert "counter_id" in data
        assert "count" in data
        assert "delta" in data

    @patch("serialcables_switchtec.core.monitor.time.sleep")
    def test_cache_control_header(self, mock_sleep, client, registered_device):
        response = client.get(
            "/api/devices/testdev/monitor/evcntr?stack_id=0&counter_id=0&count=1"
        )
        assert response.headers.get("cache-control") == "no-cache"
