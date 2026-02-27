"""CLI tests for firmware, events, and fabric command groups (Phase 6)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from serialcables_switchtec.cli.main import cli
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.events import EventSummaryResult
from serialcables_switchtec.models.fabric import FabPortConfig
from serialcables_switchtec.models.firmware import FwPartSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_device(**overrides: object) -> MagicMock:
    """Build a MagicMock that behaves like a SwitchtecDevice context manager."""
    mock_dev = MagicMock()
    mock_dev.name = overrides.get("name", "switchtec0")
    mock_dev.__enter__ = MagicMock(return_value=mock_dev)
    mock_dev.__exit__ = MagicMock(return_value=False)
    return mock_dev


# ===========================================================================
# Help text tests
# ===========================================================================


class TestPhase6Help:
    """Verify --help renders for all new groups and commands."""

    def test_fw_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "--help"])
        assert result.exit_code == 0
        assert "version" in result.output
        assert "toggle" in result.output
        assert "boot-ro" in result.output
        assert "read" in result.output
        assert "summary" in result.output

    def test_events_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["events", "--help"])
        assert result.exit_code == 0
        assert "summary" in result.output
        assert "clear" in result.output
        assert "wait" in result.output

    def test_fabric_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fabric", "--help"])
        assert result.exit_code == 0
        assert "port-control" in result.output
        assert "port-config" in result.output
        assert "bind" in result.output
        assert "unbind" in result.output
        assert "clear-events" in result.output

    def test_fw_version_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "version", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output

    def test_fw_toggle_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "toggle", "--help"])
        assert result.exit_code == 0
        assert "--bl2" in result.output
        assert "--fw" in result.output
        assert "--cfg" in result.output

    def test_events_wait_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["events", "wait", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in result.output

    def test_fabric_port_control_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fabric", "port-control", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--action" in result.output
        assert "enable" in result.output
        assert "disable" in result.output
        assert "hot-reset" in result.output

    def test_fabric_bind_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fabric", "bind", "--help"])
        assert result.exit_code == 0
        assert "--host-sw-idx" in result.output
        assert "--ep-phys-port" in result.output


# ===========================================================================
# Firmware commands
# ===========================================================================


class TestFirmwareCommands:
    """Test the ``fw`` sub-command group with mocked core classes."""

    # -- fw version ---------------------------------------------------------

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_version(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.get_fw_version.return_value = "4.40"
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "version", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "4.40" in result.output
        mock_dev.firmware.get_fw_version.assert_called_once()

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_version_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.get_fw_version.return_value = "4.40"
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fw", "version", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["fw_version"] == "4.40"

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_version_error(self, mock_cls: MagicMock) -> None:
        mock_cls.open.side_effect = SwitchtecError("device not found")

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "version", "/dev/switchtec99"])

        assert result.exit_code != 0
        assert "device not found" in result.output

    # -- fw toggle ----------------------------------------------------------

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_toggle(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "toggle", "/dev/switchtec0", "--fw", "--cfg"]
        )

        assert result.exit_code == 0
        assert "FW" in result.output
        assert "CFG" in result.output
        mock_dev.firmware.toggle_active_partition.assert_called_once_with(
            toggle_bl2=False,
            toggle_key=False,
            toggle_fw=True,
            toggle_cfg=True,
            toggle_riotcore=False,
        )

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_toggle_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fw", "toggle", "/dev/switchtec0", "--fw"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "FW" in parsed["toggled"]

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_toggle_none(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "toggle", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "none" in result.output

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_toggle_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.toggle_active_partition.side_effect = SwitchtecError(
            "toggle failed"
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "toggle", "/dev/switchtec0", "--fw"]
        )

        assert result.exit_code != 0
        assert "toggle failed" in result.output

    # -- fw boot-ro ---------------------------------------------------------

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_query(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.is_boot_ro.return_value = True
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "boot-ro", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "read-only" in result.output
        mock_dev.firmware.is_boot_ro.assert_called_once()

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_query_rw(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.is_boot_ro.return_value = False
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "boot-ro", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "read-write" in result.output

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.is_boot_ro.return_value = True
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fw", "boot-ro", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["boot_ro"] is True

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_set(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "boot-ro", "/dev/switchtec0", "--set"]
        )

        assert result.exit_code == 0
        assert "read-only" in result.output
        mock_dev.firmware.set_boot_ro.assert_called_once_with(read_only=True)

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_clear(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "boot-ro", "/dev/switchtec0", "--clear"]
        )

        assert result.exit_code == 0
        assert "cleared" in result.output
        mock_dev.firmware.set_boot_ro.assert_called_once_with(read_only=False)

    def test_fw_boot_ro_mutually_exclusive(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "boot-ro", "/dev/switchtec0", "--set", "--clear"]
        )

        # Should exit with usage error (code 2) or at least non-zero
        assert "mutually exclusive" in result.output or result.exit_code != 0

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_boot_ro_error(self, mock_cls: MagicMock) -> None:
        mock_cls.open.side_effect = SwitchtecError("permission denied")

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "boot-ro", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "permission denied" in result.output

    # -- fw read ------------------------------------------------------------

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_read(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.read_firmware.return_value = b"\xde\xad\xbe\xef"
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fw", "read", "/dev/switchtec0", "--address", "0x1000", "--length", "4"],
        )

        assert result.exit_code == 0
        assert "de ad be ef" in result.output
        mock_dev.firmware.read_firmware.assert_called_once_with(0x1000, 4)

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_read_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.read_firmware.return_value = b"\xca\xfe"
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fw", "read", "/dev/switchtec0",
                "--address", "0x2000", "--length", "2",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["hex"] == "cafe"
        assert parsed["address"] == "0x00002000"
        assert parsed["length"] == 2

    def test_fw_read_invalid_address(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fw", "read", "/dev/switchtec0", "--address", "notanumber", "--length", "4"],
        )

        assert "invalid address" in result.output

    # -- fw summary ---------------------------------------------------------

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_summary(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.get_part_summary.return_value = FwPartSummary(is_boot_ro=True)
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "summary", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "True" in result.output

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_summary_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.get_part_summary.return_value = FwPartSummary(
            is_boot_ro=False
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fw", "summary", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["is_boot_ro"] is False

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_summary_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.firmware.get_part_summary.side_effect = SwitchtecError("read failed")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "summary", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "read failed" in result.output


# ===========================================================================
# Events commands
# ===========================================================================


class TestEventsCommands:
    """Test the ``events`` sub-command group with mocked core classes."""

    # -- events summary -----------------------------------------------------

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_summary(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.events.get_summary.return_value = EventSummaryResult(
            global_events=3,
            partition_events=5,
            pff_events=2,
            total_count=10,
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["events", "summary", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "3" in result.output
        assert "5" in result.output
        assert "2" in result.output
        assert "10" in result.output

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_summary_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.events.get_summary.return_value = EventSummaryResult(
            global_events=1,
            partition_events=0,
            pff_events=0,
            total_count=1,
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "events", "summary", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["global_events"] == 1
        assert parsed["total_count"] == 1

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_summary_error(self, mock_cls: MagicMock) -> None:
        mock_cls.open.side_effect = SwitchtecError("device not found")

        runner = CliRunner()
        result = runner.invoke(cli, ["events", "summary", "/dev/switchtec99"])

        assert result.exit_code != 0
        assert "device not found" in result.output

    # -- events clear -------------------------------------------------------

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_clear(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["events", "clear", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "cleared" in result.output.lower()
        mock_dev.events.clear_all.assert_called_once()

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_clear_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "events", "clear", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["cleared"] is True

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_clear_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.events.clear_all.side_effect = SwitchtecError("clear failed")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["events", "clear", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "clear failed" in result.output

    # -- events wait --------------------------------------------------------

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_wait(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["events", "wait", "/dev/switchtec0", "--timeout", "1000"]
        )

        assert result.exit_code == 0
        assert "Event received" in result.output
        mock_dev.events.wait_for_event.assert_called_once_with(timeout_ms=1000)

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_wait_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json-output", "events", "wait", "/dev/switchtec0", "--timeout", "500"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["event_received"] is True

    @patch("serialcables_switchtec.cli.events.SwitchtecDevice")
    def test_events_wait_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.events.wait_for_event.side_effect = SwitchtecError("timeout")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["events", "wait", "/dev/switchtec0", "--timeout", "100"]
        )

        assert result.exit_code != 0
        assert "timeout" in result.output


# ===========================================================================
# Fabric commands
# ===========================================================================


class TestFabricCommands:
    """Test the ``fabric`` sub-command group with mocked core classes."""

    # -- fabric port-control ------------------------------------------------

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_enable(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fabric", "port-control", "/dev/switchtec0", "--port", "0", "--action", "enable"],
        )

        assert result.exit_code == 0
        assert "enable" in result.output.lower()
        assert "Port 0" in result.output
        mock_dev.fabric.port_control.assert_called_once()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_disable(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fabric", "port-control", "/dev/switchtec0", "--port", "1", "--action", "disable"],
        )

        assert result.exit_code == 0
        assert "disable" in result.output.lower()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fabric", "port-control", "/dev/switchtec0",
                "--port", "0", "--action", "enable",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["port"] == 0
        assert parsed["action"] == "enable"

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.port_control.side_effect = SwitchtecError("port disabled")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fabric", "port-control", "/dev/switchtec0", "--port", "0", "--action", "enable"],
        )

        assert result.exit_code != 0
        assert "port disabled" in result.output

    # -- fabric port-config -------------------------------------------------

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_config(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.get_port_config.return_value = FabPortConfig(
            phys_port_id=0,
            port_type=1,
            clock_source=2,
            clock_sris=0,
            hvd_inst=3,
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fabric", "port-config", "/dev/switchtec0", "--port", "0"]
        )

        assert result.exit_code == 0
        assert "Port 0" in result.output
        assert "1" in result.output  # port_type
        assert "2" in result.output  # clock_source
        assert "3" in result.output  # hvd_inst

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_config_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.get_port_config.return_value = FabPortConfig(
            phys_port_id=2,
            port_type=0,
            clock_source=1,
            clock_sris=1,
            hvd_inst=0,
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json-output", "fabric", "port-config", "/dev/switchtec0", "--port", "2"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["phys_port_id"] == 2
        assert parsed["clock_source"] == 1

    def test_fabric_port_config_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["fabric", "port-config", "/dev/switchtec0", "--port", "99"]
        )

        assert result.exit_code != 0
        assert "not in the range" in result.output

    # -- fabric port validation (P2) ----------------------------------------

    def test_fabric_port_control_rejects_port_60(self) -> None:
        """Port 60 is out of range (max is 59)."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "port-control", "/dev/switchtec0",
                "--port", "60", "--action", "enable",
            ],
        )
        assert result.exit_code != 0
        assert "not in the range" in result.output

    def test_fabric_port_control_rejects_negative_port(self) -> None:
        """Negative port IDs should be rejected."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "port-control", "/dev/switchtec0",
                "--port", "-1", "--action", "enable",
            ],
        )
        assert result.exit_code != 0

    def test_fabric_port_config_rejects_port_60(self) -> None:
        """Port 60 is out of range for port-config (max is 59)."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fabric", "port-config", "/dev/switchtec0", "--port", "60"],
        )
        assert result.exit_code != 0
        assert "not in the range" in result.output

    def test_fabric_port_config_rejects_negative_port(self) -> None:
        """Negative port IDs should be rejected for port-config."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fabric", "port-config", "/dev/switchtec0", "--port", "-1"],
        )
        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_accepts_port_0(
        self, mock_cls: MagicMock
    ) -> None:
        """Port 0 is the minimum valid value."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "port-control", "/dev/switchtec0",
                "--port", "0", "--action", "enable",
            ],
        )
        assert result.exit_code == 0

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_port_control_accepts_port_59(
        self, mock_cls: MagicMock
    ) -> None:
        """Port 59 is the maximum valid value."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "port-control", "/dev/switchtec0",
                "--port", "59", "--action", "enable",
            ],
        )
        assert result.exit_code == 0

    def test_fabric_bind_rejects_host_phys_port_60(self) -> None:
        """Host physical port 60 is out of range for bind (max is 59)."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "bind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "60",
                "--host-log-port", "0",
                "--ep-sw-idx", "0",
                "--ep-phys-port", "0",
            ],
        )
        assert result.exit_code != 0

    def test_fabric_bind_rejects_ep_phys_port_60(self) -> None:
        """Endpoint physical port 60 is out of range for bind (max is 59)."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "bind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "0",
                "--host-log-port", "0",
                "--ep-sw-idx", "0",
                "--ep-phys-port", "60",
            ],
        )
        assert result.exit_code != 0

    def test_fabric_unbind_rejects_host_phys_port_60(self) -> None:
        """Host physical port 60 is out of range for unbind (max is 59)."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "unbind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "60",
                "--host-log-port", "0",
            ],
        )
        assert result.exit_code != 0

    # -- fabric bind --------------------------------------------------------

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_bind(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "bind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "1",
                "--host-log-port", "2",
                "--ep-sw-idx", "0",
                "--ep-phys-port", "3",
            ],
        )

        assert result.exit_code == 0
        assert "Bound" in result.output
        assert "1" in result.output  # host port
        assert "3" in result.output  # ep port
        mock_dev.fabric.bind.assert_called_once()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_bind_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fabric", "bind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "1",
                "--host-log-port", "2",
                "--ep-sw-idx", "0",
                "--ep-phys-port", "3",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["bound"] is True
        assert parsed["host_phys_port"] == 1
        assert parsed["ep_phys_port"] == 3

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_bind_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.bind.side_effect = SwitchtecError("already bound")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "bind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "1",
                "--host-log-port", "2",
                "--ep-sw-idx", "0",
                "--ep-phys-port", "3",
            ],
        )

        assert result.exit_code != 0
        assert "already bound" in result.output

    # -- fabric unbind ------------------------------------------------------

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_unbind(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "unbind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "1",
                "--host-log-port", "2",
            ],
        )

        assert result.exit_code == 0
        assert "Unbound" in result.output
        mock_dev.fabric.unbind.assert_called_once()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_unbind_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fabric", "unbind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "4",
                "--host-log-port", "5",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["unbound"] is True
        assert parsed["host_phys_port"] == 4

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_unbind_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.unbind.side_effect = SwitchtecError("not bound")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "unbind", "/dev/switchtec0",
                "--host-sw-idx", "0",
                "--host-phys-port", "1",
                "--host-log-port", "2",
            ],
        )

        assert result.exit_code != 0
        assert "not bound" in result.output

    # -- fabric clear-events ------------------------------------------------

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_clear_events(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fabric", "clear-events", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        assert "cleared" in result.output.lower()
        mock_dev.fabric.clear_gfms_events.assert_called_once()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_clear_events_json(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fabric", "clear-events", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["cleared"] is True

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_fabric_clear_events_error(self, mock_cls: MagicMock) -> None:
        mock_dev = _make_mock_device()
        mock_dev.fabric.clear_gfms_events.side_effect = SwitchtecError(
            "operation failed"
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fabric", "clear-events", "/dev/switchtec0"]
        )

        assert result.exit_code != 0
        assert "operation failed" in result.output
