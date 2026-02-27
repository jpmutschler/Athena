"""Phase 6 API route integration tests: firmware, events, and fabric."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from serialcables_switchtec.exceptions import (
    InvalidParameterError,
    InvalidPortError,
    MrpcError,
    SwitchtecError,
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


# -- Firmware routes ----------------------------------------------------------


class TestFirmwareRoutes:
    """Tests for firmware management API endpoints."""

    # -- 404 not found tests --------------------------------------------------

    def test_fw_version_not_found(self, client):
        """GET fw version for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/firmware/version")
        assert response.status_code == 404

    def test_fw_toggle_not_found(self, client):
        """POST toggle for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/firmware/toggle",
            json={},
        )
        assert response.status_code == 404

    def test_fw_boot_ro_get_not_found(self, client):
        """GET boot-ro for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/firmware/boot-ro")
        assert response.status_code == 404

    def test_fw_boot_ro_set_not_found(self, client):
        """POST boot-ro for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/firmware/boot-ro",
            json={"read_only": True},
        )
        assert response.status_code == 404

    def test_fw_summary_not_found(self, client):
        """GET summary for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/firmware/summary")
        assert response.status_code == 404

    # -- Happy path tests -----------------------------------------------------

    def test_fw_version_happy_path(self, client, registered_device):
        """GET fw version should return version string from dev.firmware."""
        registered_device.firmware.get_fw_version.return_value = "4.70B058"
        response = client.get("/api/devices/testdev/firmware/version")
        assert response.status_code == 200
        assert response.json() == {"version": "4.70B058"}
        registered_device.firmware.get_fw_version.assert_called_once()

    def test_fw_toggle_happy_path(self, client, registered_device):
        """POST toggle should invoke dev.firmware.toggle_active_partition."""
        response = client.post(
            "/api/devices/testdev/firmware/toggle",
            json={
                "toggle_bl2": False,
                "toggle_key": False,
                "toggle_fw": True,
                "toggle_cfg": True,
                "toggle_riotcore": False,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "toggled"}
        registered_device.firmware.toggle_active_partition.assert_called_once_with(
            toggle_bl2=False,
            toggle_key=False,
            toggle_fw=True,
            toggle_cfg=True,
            toggle_riotcore=False,
        )

    def test_fw_toggle_defaults(self, client, registered_device):
        """POST toggle with empty body should use default toggle values."""
        response = client.post(
            "/api/devices/testdev/firmware/toggle",
            json={},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "toggled"}
        registered_device.firmware.toggle_active_partition.assert_called_once_with(
            toggle_bl2=False,
            toggle_key=False,
            toggle_fw=True,
            toggle_cfg=True,
            toggle_riotcore=False,
        )

    def test_fw_boot_ro_get_happy_path(self, client, registered_device):
        """GET boot-ro should return read_only status."""
        registered_device.firmware.is_boot_ro.return_value = True
        response = client.get("/api/devices/testdev/firmware/boot-ro")
        assert response.status_code == 200
        assert response.json() == {"read_only": True}
        registered_device.firmware.is_boot_ro.assert_called_once()

    def test_fw_boot_ro_get_false(self, client, registered_device):
        """GET boot-ro should return false when not read-only."""
        registered_device.firmware.is_boot_ro.return_value = False
        response = client.get("/api/devices/testdev/firmware/boot-ro")
        assert response.status_code == 200
        assert response.json() == {"read_only": False}

    def test_fw_boot_ro_set_happy_path(self, client, registered_device):
        """POST boot-ro should invoke dev.firmware.set_boot_ro."""
        response = client.post(
            "/api/devices/testdev/firmware/boot-ro",
            json={"read_only": True},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.firmware.set_boot_ro.assert_called_once_with(
            read_only=True,
        )

    def test_fw_boot_ro_set_false(self, client, registered_device):
        """POST boot-ro with read_only=false should disable read-only."""
        response = client.post(
            "/api/devices/testdev/firmware/boot-ro",
            json={"read_only": False},
        )
        assert response.status_code == 200
        registered_device.firmware.set_boot_ro.assert_called_once_with(
            read_only=False,
        )

    def test_fw_boot_ro_set_defaults(self, client, registered_device):
        """POST boot-ro with empty body should default to read_only=True."""
        response = client.post(
            "/api/devices/testdev/firmware/boot-ro",
            json={},
        )
        assert response.status_code == 200
        registered_device.firmware.set_boot_ro.assert_called_once_with(
            read_only=True,
        )

    def test_fw_summary_happy_path(self, client, registered_device):
        """GET summary should return FwPartSummary from dev.firmware."""
        from serialcables_switchtec.models.firmware import FwPartSummary

        registered_device.firmware.get_part_summary.return_value = (
            FwPartSummary(
                is_boot_ro=True,
            )
        )
        response = client.get("/api/devices/testdev/firmware/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["is_boot_ro"] is True
        registered_device.firmware.get_part_summary.assert_called_once()

    # -- Error-path tests -----------------------------------------------------

    def test_fw_version_error_maps_to_http(self, client, registered_device):
        """fw version raising SwitchtecError should map to HTTP error."""
        registered_device.firmware.get_fw_version.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.get("/api/devices/testdev/firmware/version")
        assert response.status_code == 502

    def test_fw_toggle_error_maps_to_http(self, client, registered_device):
        """toggle raising UnsupportedError should map to 501."""
        registered_device.firmware.toggle_active_partition.side_effect = (
            UnsupportedError("unsupported", error_code=1)
        )
        response = client.post(
            "/api/devices/testdev/firmware/toggle", json={}
        )
        assert response.status_code == 501

    def test_fw_boot_ro_get_error_maps_to_http(
        self, client, registered_device
    ):
        """is_boot_ro raising SwitchtecError should map to 500."""
        registered_device.firmware.is_boot_ro.side_effect = SwitchtecError(
            "unknown error", error_code=99
        )
        response = client.get("/api/devices/testdev/firmware/boot-ro")
        assert response.status_code == 500

    def test_fw_boot_ro_set_error_maps_to_http(
        self, client, registered_device
    ):
        """set_boot_ro raising InvalidParameterError should map to 400."""
        registered_device.firmware.set_boot_ro.side_effect = (
            InvalidParameterError("bad param", error_code=1)
        )
        response = client.post(
            "/api/devices/testdev/firmware/boot-ro",
            json={"read_only": True},
        )
        assert response.status_code == 400

    def test_fw_summary_error_maps_to_http(self, client, registered_device):
        """get_part_summary raising SwitchtecTimeoutError should map to 504."""
        registered_device.firmware.get_part_summary.side_effect = (
            SwitchtecTimeoutError("timeout", error_code=1)
        )
        response = client.get("/api/devices/testdev/firmware/summary")
        assert response.status_code == 504


# -- Event routes -------------------------------------------------------------


class TestEventRoutes:
    """Tests for event management API endpoints."""

    # -- 404 not found tests --------------------------------------------------

    def test_event_summary_not_found(self, client):
        """GET event summary for nonexistent device should return 404."""
        response = client.get("/api/devices/nonexistent/events/summary")
        assert response.status_code == 404

    def test_event_clear_not_found(self, client):
        """POST clear events for nonexistent device should return 404."""
        response = client.post("/api/devices/nonexistent/events/clear")
        assert response.status_code == 404

    def test_event_wait_not_found(self, client):
        """POST wait for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/events/wait",
            json={"timeout_ms": 1000},
        )
        assert response.status_code == 404

    # -- Happy path tests -----------------------------------------------------

    def test_event_summary_happy_path(self, client, registered_device):
        """GET event summary should return EventSummaryResult."""
        from serialcables_switchtec.models.events import EventSummaryResult

        registered_device.events.get_summary.return_value = (
            EventSummaryResult(
                global_events=2,
                partition_events=5,
                pff_events=3,
                total_count=10,
            )
        )
        response = client.get("/api/devices/testdev/events/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["global_events"] == 2
        assert body["partition_events"] == 5
        assert body["pff_events"] == 3
        assert body["total_count"] == 10
        registered_device.events.get_summary.assert_called_once()

    def test_event_clear_happy_path(self, client, registered_device):
        """POST clear events should invoke dev.events.clear_all."""
        response = client.post("/api/devices/testdev/events/clear")
        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}
        registered_device.events.clear_all.assert_called_once()

    def test_event_wait_happy_path(self, client, registered_device):
        """POST wait should invoke dev.events.wait_for_event with timeout."""
        response = client.post(
            "/api/devices/testdev/events/wait",
            json={"timeout_ms": 5000},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "event_received"}
        registered_device.events.wait_for_event.assert_called_once_with(
            timeout_ms=5000,
        )

    def test_event_wait_defaults(self, client, registered_device):
        """POST wait with empty body should use default timeout_ms=-1."""
        response = client.post(
            "/api/devices/testdev/events/wait",
            json={},
        )
        assert response.status_code == 200
        registered_device.events.wait_for_event.assert_called_once_with(
            timeout_ms=-1,
        )

    def test_event_wait_validation_rejects_invalid_timeout(self, client):
        """POST wait with timeout below -1 should be rejected."""
        from serialcables_switchtec.api.state import get_device_registry

        mock_dev = _make_mock_device()
        registry = get_device_registry()
        registry["valdev"] = (mock_dev, "/dev/switchtec0")
        try:
            response = client.post(
                "/api/devices/valdev/events/wait",
                json={"timeout_ms": -2},
            )
            assert response.status_code == 422
        finally:
            registry.pop("valdev", None)

    # -- Error-path tests -----------------------------------------------------

    def test_event_summary_error_maps_to_http(
        self, client, registered_device
    ):
        """get_summary raising MrpcError should map to 502."""
        registered_device.events.get_summary.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.get("/api/devices/testdev/events/summary")
        assert response.status_code == 502

    def test_event_clear_error_maps_to_http(self, client, registered_device):
        """clear_all raising SwitchtecError should map to HTTP error."""
        registered_device.events.clear_all.side_effect = SwitchtecError(
            "error", error_code=99
        )
        response = client.post("/api/devices/testdev/events/clear")
        assert response.status_code == 500

    def test_event_wait_timeout_error(self, client, registered_device):
        """wait_for_event raising SwitchtecTimeoutError should map to 504."""
        registered_device.events.wait_for_event.side_effect = (
            SwitchtecTimeoutError("timeout", error_code=1)
        )
        response = client.post(
            "/api/devices/testdev/events/wait",
            json={"timeout_ms": 1000},
        )
        assert response.status_code == 504


# -- Fabric routes ------------------------------------------------------------


class TestFabricRoutes:
    """Tests for fabric topology management API endpoints."""

    # -- 404 not found tests --------------------------------------------------

    def test_port_control_not_found(self, client):
        """POST port control for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/port-control",
            json={"phys_port_id": 0, "control_type": 1},
        )
        assert response.status_code == 404

    def test_get_port_config_not_found(self, client):
        """GET port config for nonexistent device should return 404."""
        response = client.get(
            "/api/devices/nonexistent/fabric/port-config/0"
        )
        assert response.status_code == 404

    def test_set_port_config_not_found(self, client):
        """POST port config for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/port-config/0",
            json={},
        )
        assert response.status_code == 404

    def test_bind_not_found(self, client):
        """POST bind for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/bind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 0,
                "host_log_port_id": 0,
                "ep_sw_idx": 0,
                "ep_phys_port_id": 1,
            },
        )
        assert response.status_code == 404

    def test_unbind_not_found(self, client):
        """POST unbind for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/unbind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 0,
                "host_log_port_id": 0,
            },
        )
        assert response.status_code == 404

    def test_clear_events_not_found(self, client):
        """POST clear events for nonexistent device should return 404."""
        response = client.post(
            "/api/devices/nonexistent/fabric/clear-events"
        )
        assert response.status_code == 404

    # -- Happy path tests -----------------------------------------------------

    def test_port_control_happy_path(self, client, registered_device):
        """POST port control should invoke dev.fabric.port_control."""
        from serialcables_switchtec.bindings.constants import (
            FabHotResetFlag,
            FabPortControlType,
        )

        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={
                "phys_port_id": 5,
                "control_type": 1,
                "hot_reset_flag": 0,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.fabric.port_control.assert_called_once_with(
            phys_port_id=5,
            control_type=FabPortControlType.ENABLE,
            hot_reset_flag=FabHotResetFlag.NONE,
        )

    def test_port_control_hot_reset(self, client, registered_device):
        """POST port control with hot reset should pass correct flags."""
        from serialcables_switchtec.bindings.constants import (
            FabHotResetFlag,
            FabPortControlType,
        )

        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={
                "phys_port_id": 3,
                "control_type": 2,
                "hot_reset_flag": 1,
            },
        )
        assert response.status_code == 200
        registered_device.fabric.port_control.assert_called_once_with(
            phys_port_id=3,
            control_type=FabPortControlType.HOT_RESET,
            hot_reset_flag=FabHotResetFlag.PERST,
        )

    def test_port_control_defaults(self, client, registered_device):
        """POST port control with minimal body should use default hot_reset_flag."""
        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={"phys_port_id": 0, "control_type": 0},
        )
        assert response.status_code == 200
        call_kwargs = registered_device.fabric.port_control.call_args[1]
        assert call_kwargs["hot_reset_flag"].value == 0

    def test_get_port_config_happy_path(self, client, registered_device):
        """GET port config should return FabPortConfig."""
        from serialcables_switchtec.models.fabric import FabPortConfig

        registered_device.fabric.get_port_config.return_value = FabPortConfig(
            phys_port_id=7,
            port_type=2,
            clock_source=1,
            clock_sris=0,
            hvd_inst=3,
        )
        response = client.get(
            "/api/devices/testdev/fabric/port-config/7"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["phys_port_id"] == 7
        assert body["port_type"] == 2
        assert body["clock_source"] == 1
        assert body["clock_sris"] == 0
        assert body["hvd_inst"] == 3
        registered_device.fabric.get_port_config.assert_called_once_with(7)

    def test_set_port_config_happy_path(self, client, registered_device):
        """POST port config should invoke dev.fabric.set_port_config."""
        response = client.post(
            "/api/devices/testdev/fabric/port-config/4",
            json={
                "port_type": 1,
                "clock_source": 2,
                "clock_sris": 1,
                "hvd_inst": 0,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        registered_device.fabric.set_port_config.assert_called_once()
        config_arg = registered_device.fabric.set_port_config.call_args[0][0]
        assert config_arg.phys_port_id == 4
        assert config_arg.port_type == 1
        assert config_arg.clock_source == 2
        assert config_arg.clock_sris == 1
        assert config_arg.hvd_inst == 0

    def test_set_port_config_defaults(self, client, registered_device):
        """POST port config with empty body should use defaults."""
        response = client.post(
            "/api/devices/testdev/fabric/port-config/0",
            json={},
        )
        assert response.status_code == 200
        config_arg = registered_device.fabric.set_port_config.call_args[0][0]
        assert config_arg.phys_port_id == 0
        assert config_arg.port_type == 0
        assert config_arg.clock_source == 0

    def test_bind_happy_path(self, client, registered_device):
        """POST bind should invoke dev.fabric.bind with GfmsBindRequest."""
        response = client.post(
            "/api/devices/testdev/fabric/bind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 1,
                "host_log_port_id": 2,
                "ep_sw_idx": 1,
                "ep_phys_port_id": 3,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "bound"}
        registered_device.fabric.bind.assert_called_once()
        bind_req = registered_device.fabric.bind.call_args[0][0]
        assert bind_req.host_sw_idx == 0
        assert bind_req.host_phys_port_id == 1
        assert bind_req.host_log_port_id == 2
        assert bind_req.ep_sw_idx == 1
        assert bind_req.ep_phys_port_id == 3

    def test_bind_missing_required_fields(self, client, registered_device):
        """POST bind without required fields should return 422."""
        response = client.post(
            "/api/devices/testdev/fabric/bind",
            json={"host_sw_idx": 0},
        )
        assert response.status_code == 422

    def test_unbind_happy_path(self, client, registered_device):
        """POST unbind should invoke dev.fabric.unbind."""
        response = client.post(
            "/api/devices/testdev/fabric/unbind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 1,
                "host_log_port_id": 2,
                "opt": 1,
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "unbound"}
        registered_device.fabric.unbind.assert_called_once()
        unbind_req = registered_device.fabric.unbind.call_args[0][0]
        assert unbind_req.host_sw_idx == 0
        assert unbind_req.host_phys_port_id == 1
        assert unbind_req.host_log_port_id == 2
        assert unbind_req.opt == 1

    def test_unbind_defaults(self, client, registered_device):
        """POST unbind with minimal body should default opt=0."""
        response = client.post(
            "/api/devices/testdev/fabric/unbind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 1,
                "host_log_port_id": 2,
            },
        )
        assert response.status_code == 200
        unbind_req = registered_device.fabric.unbind.call_args[0][0]
        assert unbind_req.opt == 0

    def test_clear_gfms_events_happy_path(self, client, registered_device):
        """POST clear events should invoke dev.fabric.clear_gfms_events."""
        response = client.post(
            "/api/devices/testdev/fabric/clear-events"
        )
        assert response.status_code == 200
        assert response.json() == {"status": "cleared"}
        registered_device.fabric.clear_gfms_events.assert_called_once()

    # -- Validation tests -----------------------------------------------------

    def test_port_control_invalid_port_id(self, client, registered_device):
        """POST port control with port_id > 59 should be rejected."""
        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={"phys_port_id": 100, "control_type": 1},
        )
        assert response.status_code == 422

    def test_port_control_invalid_control_type(
        self, client, registered_device
    ):
        """POST port control with control_type > 2 should be rejected."""
        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={"phys_port_id": 0, "control_type": 5},
        )
        assert response.status_code == 422

    def test_get_port_config_invalid_port_id(self, client):
        """GET port config with port_id > 59 should be rejected."""
        response = client.get(
            "/api/devices/testdev/fabric/port-config/100"
        )
        assert response.status_code == 422

    # -- Error-path tests -----------------------------------------------------

    def test_port_control_error_maps_to_http(
        self, client, registered_device
    ):
        """port_control raising InvalidPortError should map to 400."""
        registered_device.fabric.port_control.side_effect = InvalidPortError(
            "bad port", error_code=1
        )
        response = client.post(
            "/api/devices/testdev/fabric/port-control",
            json={"phys_port_id": 0, "control_type": 1},
        )
        assert response.status_code == 400

    def test_get_port_config_error_maps_to_http(
        self, client, registered_device
    ):
        """get_port_config raising MrpcError should map to 502."""
        registered_device.fabric.get_port_config.side_effect = MrpcError(
            "mrpc failed", error_code=1
        )
        response = client.get(
            "/api/devices/testdev/fabric/port-config/0"
        )
        assert response.status_code == 502

    def test_set_port_config_error_maps_to_http(
        self, client, registered_device
    ):
        """set_port_config raising InvalidParameterError should map to 400."""
        registered_device.fabric.set_port_config.side_effect = (
            InvalidParameterError("invalid", error_code=1)
        )
        response = client.post(
            "/api/devices/testdev/fabric/port-config/0",
            json={},
        )
        assert response.status_code == 400

    def test_bind_error_maps_to_http(self, client, registered_device):
        """bind raising MrpcError should map to 502."""
        registered_device.fabric.bind.side_effect = MrpcError(
            "bind failed", error_code=1
        )
        response = client.post(
            "/api/devices/testdev/fabric/bind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 0,
                "host_log_port_id": 0,
                "ep_sw_idx": 0,
                "ep_phys_port_id": 1,
            },
        )
        assert response.status_code == 502

    def test_unbind_error_maps_to_http(self, client, registered_device):
        """unbind raising UnsupportedError should map to 501."""
        registered_device.fabric.unbind.side_effect = UnsupportedError(
            "unsupported", error_code=1
        )
        response = client.post(
            "/api/devices/testdev/fabric/unbind",
            json={
                "host_sw_idx": 0,
                "host_phys_port_id": 0,
                "host_log_port_id": 0,
            },
        )
        assert response.status_code == 501

    def test_clear_gfms_events_error_maps_to_http(
        self, client, registered_device
    ):
        """clear_gfms_events raising SwitchtecError should map to HTTP error."""
        registered_device.fabric.clear_gfms_events.side_effect = (
            SwitchtecError("error", error_code=99)
        )
        response = client.post(
            "/api/devices/testdev/fabric/clear-events"
        )
        assert response.status_code == 500
