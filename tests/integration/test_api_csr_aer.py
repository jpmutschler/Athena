"""Integration API tests for CSR read/write and AER event generation endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.exceptions import (
    InvalidParameterError,
    MrpcError,
    SwitchtecError,
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


# -- CSR Read routes ----------------------------------------------------------


class TestCsrReadRoutes:
    """Tests for the CSR read API endpoint."""

    def test_csr_read_not_found(self, client):
        """GET csr read for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/fabric/csr/256?addr=16&width=32"
        )
        assert response.status_code == 404

    def test_csr_read_endpoint(self, client, registered_device):
        """GET csr read should return pdfid, addr, width, and value."""
        registered_device.fabric.csr_read.return_value = 0xDEADBEEF
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=16&width=32"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["pdfid"] == 256
        assert body["addr"] == 16
        assert body["width"] == 32
        assert body["value"] == 0xDEADBEEF
        registered_device.fabric.csr_read.assert_called_once_with(256, 16, 32)

    def test_csr_read_width_8(self, client, registered_device):
        """GET csr read with width=8 should pass 8 to the manager."""
        registered_device.fabric.csr_read.return_value = 0xAB
        response = client.get(
            "/api/devices/testdev/fabric/csr/0?addr=3&width=8"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["value"] == 0xAB
        assert body["width"] == 8

    def test_csr_read_width_16(self, client, registered_device):
        """GET csr read with width=16 should work."""
        registered_device.fabric.csr_read.return_value = 0xCAFE
        response = client.get(
            "/api/devices/testdev/fabric/csr/100?addr=4&width=16"
        )
        assert response.status_code == 200
        assert response.json()["value"] == 0xCAFE

    def test_csr_read_invalid_width(self, client, registered_device):
        """GET csr read with width=64 should return 422."""
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=16&width=64"
        )
        assert response.status_code == 422

    def test_csr_read_default_width(self, client, registered_device):
        """GET csr read without width parameter should default to 32."""
        registered_device.fabric.csr_read.return_value = 0x12345678
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=0"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["width"] == 32
        registered_device.fabric.csr_read.assert_called_once_with(256, 0, 32)

    def test_csr_read_addr_out_of_range(self, client, registered_device):
        """GET csr read with addr > 0xFFF should return 422."""
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=65536&width=32"
        )
        assert response.status_code == 422

    def test_csr_read_mrpc_error_maps_to_502(self, client, registered_device):
        """csr_read raising MrpcError should map to 502."""
        registered_device.fabric.csr_read.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=16&width=32"
        )
        assert response.status_code == 502

    def test_csr_read_generic_error_maps_to_500(self, client, registered_device):
        """csr_read raising SwitchtecError should map to 500."""
        registered_device.fabric.csr_read.side_effect = SwitchtecError(
            "unknown error", error_code=99
        )
        response = client.get(
            "/api/devices/testdev/fabric/csr/256?addr=16&width=32"
        )
        assert response.status_code == 500


# -- CSR Write routes ---------------------------------------------------------


class TestCsrWriteRoutes:
    """Tests for the CSR write API endpoint."""

    def test_csr_write_not_found(self, client):
        """POST csr write for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/csr/256",
            json={"addr": 4, "value": 6, "width": 16},
        )
        assert response.status_code == 404

    def test_csr_write_endpoint(self, client, registered_device):
        """POST csr write should invoke csr_write and return written status."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 4, "value": 6, "width": 16},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "written"}
        registered_device.fabric.csr_write.assert_called_once_with(
            256, 4, 6, 16
        )

    def test_csr_write_default_width(self, client, registered_device):
        """POST csr write without width should default to 32."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0, "value": 1},
        )
        assert response.status_code == 200
        registered_device.fabric.csr_write.assert_called_once_with(
            256, 0, 1, 32
        )

    def test_csr_write_value_overflow(self, client, registered_device):
        """POST csr write with value exceeding width should return 422."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0, "value": 0xFFFF, "width": 8},
        )
        assert response.status_code == 422

    def test_csr_write_value_fits_width_boundary(self, client, registered_device):
        """POST csr write with max value for width should succeed."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0, "value": 0xFF, "width": 8},
        )
        assert response.status_code == 200

    def test_csr_write_invalid_width(self, client, registered_device):
        """POST csr write with width=64 should return 422."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0, "value": 1, "width": 64},
        )
        assert response.status_code == 422

    def test_csr_write_addr_out_of_range(self, client, registered_device):
        """POST csr write with addr > 0xFFF should return 422."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0x10000, "value": 1, "width": 32},
        )
        assert response.status_code == 422

    def test_csr_write_rate_limited(self, client, registered_device):
        """Calling csr write 6 times rapidly should trigger 429 on the 6th."""
        for i in range(5):
            response = client.post(
                "/api/devices/testdev/fabric/csr/256",
                json={"addr": 0, "value": i, "width": 32},
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 0, "value": 99, "width": 32},
        )
        assert response.status_code == 429

    def test_csr_write_mrpc_error_maps_to_502(self, client, registered_device):
        """csr_write raising MrpcError should map to 502."""
        registered_device.fabric.csr_write.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 4, "value": 6, "width": 16},
        )
        assert response.status_code == 502

    def test_csr_write_invalid_param_error_maps_to_400(
        self, client, registered_device
    ):
        """csr_write raising InvalidParameterError should map to 400."""
        registered_device.fabric.csr_write.side_effect = (
            InvalidParameterError("bad param", error_code=1)
        )
        response = client.post(
            "/api/devices/testdev/fabric/csr/256",
            json={"addr": 4, "value": 6, "width": 16},
        )
        assert response.status_code == 400

    def test_csr_write_pdfid_out_of_range(self, client, registered_device):
        """POST csr write with pdfid > 0xFFFF should return 422."""
        response = client.post(
            "/api/devices/testdev/fabric/csr/100000",
            json={"addr": 0, "value": 1, "width": 32},
        )
        assert response.status_code == 422


# -- AER Event Generation routes -----------------------------------------------


class TestAerGenRoutes:
    """Tests for the AER event generation API endpoint."""

    def test_aer_gen_not_found(self, client):
        """POST aer-gen for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/diag/aer-gen/0",
            json={"error_id": 1, "trigger": 0},
        )
        assert response.status_code == 404

    def test_aer_gen_endpoint(self, client, registered_device):
        """POST aer-gen should invoke aer_event_gen and return generated."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 1, "trigger": 0},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "generated"}
        registered_device.diagnostics.aer_event_gen.assert_called_once_with(
            0, 1, 0
        )

    def test_aer_gen_with_trigger(self, client, registered_device):
        """POST aer-gen with custom trigger should pass it through."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/5",
            json={"error_id": 42, "trigger": 7},
        )
        assert response.status_code == 200
        registered_device.diagnostics.aer_event_gen.assert_called_once_with(
            5, 42, 7
        )

    def test_aer_gen_default_trigger(self, client, registered_device):
        """POST aer-gen without trigger should default to 0."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 1},
        )
        assert response.status_code == 200
        registered_device.diagnostics.aer_event_gen.assert_called_once_with(
            0, 1, 0
        )

    def test_aer_gen_port_out_of_range(self, client, registered_device):
        """POST aer-gen with port_id > 59 should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/60",
            json={"error_id": 1, "trigger": 0},
        )
        assert response.status_code == 422

    def test_aer_gen_error_id_out_of_range(self, client, registered_device):
        """POST aer-gen with error_id > 0xFFFF should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 0x10000, "trigger": 0},
        )
        assert response.status_code == 422

    def test_aer_gen_missing_error_id(self, client, registered_device):
        """POST aer-gen without error_id should return 422."""
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"trigger": 0},
        )
        assert response.status_code == 422

    def test_aer_gen_mrpc_error_maps_to_502(self, client, registered_device):
        """aer_event_gen raising MrpcError should map to 502."""
        registered_device.diagnostics.aer_event_gen.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 1, "trigger": 0},
        )
        assert response.status_code == 502

    def test_aer_gen_generic_error_maps_to_500(self, client, registered_device):
        """aer_event_gen raising SwitchtecError should map to 500."""
        registered_device.diagnostics.aer_event_gen.side_effect = (
            SwitchtecError("unknown error", error_code=99)
        )
        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 1, "trigger": 0},
        )
        assert response.status_code == 500

    def test_aer_gen_rate_limited(self, client, registered_device):
        """Calling aer-gen 11 times rapidly should trigger 429 on the 11th."""
        for i in range(10):
            response = client.post(
                "/api/devices/testdev/diag/aer-gen/0",
                json={"error_id": i, "trigger": 0},
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

        response = client.post(
            "/api/devices/testdev/diag/aer-gen/0",
            json={"error_id": 99, "trigger": 0},
        )
        assert response.status_code == 429
