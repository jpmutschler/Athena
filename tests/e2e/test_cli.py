"""CLI tests using Click's CliRunner with mocked device interactions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from serialcables_switchtec.cli.main import cli
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.device import (
    DeviceInfo,
    DeviceSummary,
    PortId,
    PortStatus,
)
from serialcables_switchtec.models.diagnostics import (
    CrossHairResult,
    EqCursor,
    LtssmLogEntry,
    PatternMonResult,
    PortEqCoeff,
    ReceiverObject,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_device(**overrides: object) -> MagicMock:
    """Build a MagicMock that behaves like a SwitchtecDevice context manager.

    Keyword arguments override default attribute values on the mock device.
    """
    mock_dev = MagicMock()
    mock_dev.name = overrides.get("name", "switchtec0")
    mock_dev.die_temperature = overrides.get("die_temperature", 45.5)
    mock_dev.__enter__ = MagicMock(return_value=mock_dev)
    mock_dev.__exit__ = MagicMock(return_value=False)
    return mock_dev


def _sample_device_info() -> DeviceInfo:
    return DeviceInfo(
        name="switchtec0",
        description="Microchip PFX 100xG6",
        pci_dev="0000:03:00.0",
        product_id="8264",
        product_rev="B1",
        fw_version="4.40",
        path="/dev/switchtec0",
    )


def _sample_device_summary() -> DeviceSummary:
    return DeviceSummary(
        name="switchtec0",
        device_id=0x8264,
        generation="GEN6",
        variant="PFX",
        boot_phase="Main Firmware",
        partition=0,
        fw_version="4.40",
        die_temperature=45.5,
        port_count=4,
    )


def _sample_port_status() -> PortStatus:
    return PortStatus(
        port=PortId(
            partition=0,
            stack=0,
            upstream=False,
            stk_id=0,
            phys_id=1,
            log_id=1,
        ),
        cfg_lnk_width=16,
        neg_lnk_width=16,
        link_up=True,
        link_rate=4,
        ltssm=0x0103,
        ltssm_str="L0 (L0)",
        lane_reversal=0,
        lane_reversal_str="Normal",
        first_act_lane=0,
    )


def _sample_ltssm_entry() -> LtssmLogEntry:
    return LtssmLogEntry(
        timestamp=100,
        link_rate=16.0,
        link_state=0x0103,
        link_state_str="L0 (L0)",
        link_width=16,
        tx_minor_state=0,
        rx_minor_state=0,
    )


def _sample_pattern_mon_result() -> PatternMonResult:
    return PatternMonResult(
        port_id=0,
        lane_id=0,
        pattern_type=3,
        error_count=42,
    )


def _sample_receiver_object() -> ReceiverObject:
    return ReceiverObject(
        port_id=0,
        lane_id=0,
        ctle=5,
        target_amplitude=120,
        speculative_dfe=3,
        dynamic_dfe=[1, 2, 3, 4, 5, 6, 7],
    )


def _sample_port_eq_coeff() -> PortEqCoeff:
    return PortEqCoeff(
        lane_count=2,
        cursors=[
            EqCursor(pre=-6, post=-12),
            EqCursor(pre=-4, post=-10),
        ],
    )


def _sample_crosshair_result() -> CrossHairResult:
    return CrossHairResult(
        lane_id=0,
        state=21,
        state_name="DONE",
        eye_left_lim=-32,
        eye_right_lim=32,
    )


# ===========================================================================
# Help text tests (existing)
# ===========================================================================


class TestCliHelp:
    def test_root_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Athena" in result.output
        assert "Serial Cables" in result.output

    def test_device_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["device", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "info" in result.output

    def test_diag_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "--help"])
        assert result.exit_code == 0
        assert "eye" in result.output
        assert "ltssm" in result.output
        assert "loopback" in result.output

    def test_inject_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "inject", "--help"])
        assert result.exit_code == 0
        assert "dllp" in result.output
        assert "cto" in result.output

    def test_serve_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "host" in result.output
        assert "port" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_serve_default_host(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "127.0.0.1" in result.output

    def test_diag_loopback_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "loopback", "--help"])
        assert result.exit_code == 0
        assert "gen1" in result.output
        assert "gen2" in result.output

    def test_diag_patgen_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "patgen", "--help"])
        assert result.exit_code == 0
        assert "prbs7" in result.output
        assert "prbs31" in result.output


# ===========================================================================
# Device commands
# ===========================================================================


class TestDeviceCommands:
    """Test the ``device`` sub-command group with mocked core classes."""

    # ── device list ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list(self, mock_cls):
        mock_cls.list_devices.return_value = [_sample_device_info()]

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "list"])

        assert result.exit_code == 0
        assert "switchtec0" in result.output
        assert "Microchip PFX 100xG6" in result.output
        assert "/dev/switchtec0" in result.output
        mock_cls.list_devices.assert_called_once()

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list_multiple(self, mock_cls):
        second = DeviceInfo(
            name="switchtec1",
            description="Microchip PSX 48xG6",
            pci_dev="0000:04:00.0",
            product_id="8265",
            product_rev="C0",
            fw_version="4.41",
            path="/dev/switchtec1",
        )
        mock_cls.list_devices.return_value = [_sample_device_info(), second]

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "list"])

        assert result.exit_code == 0
        assert "switchtec0" in result.output
        assert "switchtec1" in result.output

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list_json(self, mock_cls):
        mock_cls.list_devices.return_value = [_sample_device_info()]

        runner = CliRunner()
        result = runner.invoke(cli, ["--json-output", "device", "list"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "switchtec0"
        assert parsed[0]["path"] == "/dev/switchtec0"

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list_empty(self, mock_cls):
        mock_cls.list_devices.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "list"])

        assert result.exit_code == 0
        assert "No Switchtec devices found" in result.output

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list_empty_json(self, mock_cls):
        mock_cls.list_devices.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["--json-output", "device", "list"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed == []

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_list_error(self, mock_cls):
        mock_cls.list_devices.side_effect = SwitchtecError("cannot enumerate")

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "list"])

        assert result.exit_code != 0
        assert "cannot enumerate" in result.output

    # ── device info ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_info(self, mock_cls):
        mock_dev = _make_mock_device()
        mock_dev.get_summary.return_value = _sample_device_summary()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "info", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "switchtec0" in result.output
        assert "0x8264" in result.output
        assert "GEN6" in result.output
        assert "PFX" in result.output
        assert "Main Firmware" in result.output
        assert "4.40" in result.output
        assert "45.5" in result.output
        assert "4" in result.output  # port_count

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_info_json(self, mock_cls):
        mock_dev = _make_mock_device()
        mock_dev.get_summary.return_value = _sample_device_summary()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "device", "info", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["name"] == "switchtec0"
        assert parsed["device_id"] == 0x8264
        assert parsed["generation"] == "GEN6"
        assert parsed["die_temperature"] == 45.5

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_info_error(self, mock_cls):
        mock_cls.open.side_effect = SwitchtecError("device not found")

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "info", "/dev/switchtec99"])

        assert result.exit_code != 0
        assert "device not found" in result.output

    # ── device temp ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_temp(self, mock_cls):
        mock_dev = _make_mock_device(die_temperature=45.5)
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "temp", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "45.5" in result.output

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_temp_json(self, mock_cls):
        mock_dev = _make_mock_device(die_temperature=62.3)
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "device", "temp", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["temperature_c"] == 62.3

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_temp_error(self, mock_cls):
        mock_cls.open.side_effect = SwitchtecError("timeout")

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "temp", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "timeout" in result.output

    # ── device status ──────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_status(self, mock_cls):
        mock_dev = _make_mock_device()
        mock_dev.get_status.return_value = [_sample_port_status()]
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "status", "/dev/switchtec0"])

        assert result.exit_code == 0
        # Header columns
        assert "Port" in result.output
        assert "Link" in result.output
        assert "Width" in result.output
        # Data values
        assert "UP" in result.output
        assert "L0 (L0)" in result.output

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_status_json(self, mock_cls):
        mock_dev = _make_mock_device()
        mock_dev.get_status.return_value = [_sample_port_status()]
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "device", "status", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["link_up"] is True
        assert parsed[0]["link_rate"] == 4
        assert parsed[0]["port"]["phys_id"] == 1

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_status_link_down(self, mock_cls):
        port_down = PortStatus(
            port=PortId(
                partition=0, stack=0, upstream=False,
                stk_id=0, phys_id=2, log_id=2,
            ),
            cfg_lnk_width=16,
            neg_lnk_width=0,
            link_up=False,
            link_rate=0,
            ltssm=0x0000,
            ltssm_str="Detect (INACTIVE)",
            lane_reversal=0,
            lane_reversal_str="Normal",
            first_act_lane=0,
        )
        mock_dev = _make_mock_device()
        mock_dev.get_status.return_value = [port_down]
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "status", "/dev/switchtec0"])

        assert result.exit_code == 0
        assert "DOWN" in result.output

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_device_status_error(self, mock_cls):
        mock_cls.open.side_effect = SwitchtecError("permission denied")

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "status", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "permission denied" in result.output


# ===========================================================================
# Diagnostic commands
# ===========================================================================


class TestDiagCommands:
    """Test the ``diag`` sub-command group with mocked diagnostics."""

    # ── ltssm ──────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_ltssm(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.ltssm_log.return_value = [_sample_ltssm_entry()]
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "ltssm", "/dev/switchtec0", "0"])

        assert result.exit_code == 0
        assert "L0 (L0)" in result.output
        assert "100" in result.output  # timestamp
        mock_diag.ltssm_log.assert_called_once_with(0)

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_ltssm_json(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.ltssm_log.return_value = [_sample_ltssm_entry()]
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "diag", "ltssm", "/dev/switchtec0", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]["link_state_str"] == "L0 (L0)"
        assert parsed[0]["timestamp"] == 100

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_ltssm_empty(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.ltssm_log.return_value = []
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "ltssm", "/dev/switchtec0", "0"])

        assert result.exit_code == 0

    def test_ltssm_error(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "ltssm", "/dev/switchtec0", "99"])

        assert result.exit_code != 0
        assert "not in the range" in result.output

    # ── ltssm-clear ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_ltssm_clear(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "ltssm-clear", "/dev/switchtec0", "0"]
        )

        assert result.exit_code == 0
        assert "cleared" in result.output.lower()
        mock_diag.ltssm_clear.assert_called_once_with(0)

    # ── loopback ───────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_loopback_enable(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "loopback", "/dev/switchtec0", "0",
             "--enable", "--ltssm-speed", "gen4"],
        )

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        mock_diag.loopback_set.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_loopback_disable(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "loopback", "/dev/switchtec0", "0", "--disable"],
        )

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        mock_diag.loopback_set.assert_called_once()
        # Verify enable=False was passed
        call_kwargs = mock_diag.loopback_set.call_args
        assert call_kwargs[1].get("enable") is False or call_kwargs[0][1] is False

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_loopback_default_speed(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "loopback", "/dev/switchtec0", "0"]
        )

        assert result.exit_code == 0
        mock_diag.loopback_set.assert_called_once()

    # ── patgen ─────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patgen(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "patgen", "/dev/switchtec0", "0",
             "--pattern", "prbs31", "--speed", "gen4"],
        )

        assert result.exit_code == 0
        assert "prbs31" in result.output.lower()
        assert "gen4" in result.output.lower()
        mock_diag.pattern_gen_set.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patgen_prbs7(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "patgen", "/dev/switchtec0", "0",
             "--pattern", "prbs7", "--speed", "gen1"],
        )

        assert result.exit_code == 0
        assert "prbs7" in result.output.lower()
        mock_diag.pattern_gen_set.assert_called_once()

    # ── patmon ─────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patmon(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.pattern_mon_get.return_value = _sample_pattern_mon_result()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "patmon", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code == 0
        assert "42" in result.output  # error_count
        mock_diag.pattern_mon_get.assert_called_once_with(0, 0)

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patmon_json(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.pattern_mon_get.return_value = _sample_pattern_mon_result()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "diag", "patmon", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["error_count"] == 42
        assert parsed["pattern_type"] == 3

    # ── rcvr ───────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_rcvr(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.return_value = _sample_receiver_object()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "rcvr", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code == 0
        assert "CTLE" in result.output
        assert "5" in result.output  # ctle value
        assert "120" in result.output  # target_amplitude
        mock_diag.rcvr_obj.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_rcvr_json(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.return_value = _sample_receiver_object()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "diag", "rcvr", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["ctle"] == 5
        assert parsed["target_amplitude"] == 120

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_rcvr_previous_link(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.return_value = _sample_receiver_object()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "rcvr", "/dev/switchtec0", "0", "0",
             "--link", "previous"],
        )

        assert result.exit_code == 0
        mock_diag.rcvr_obj.assert_called_once()

    # ── eq ─────────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eq(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.return_value = _sample_port_eq_coeff()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eq", "/dev/switchtec0", "0"]
        )

        assert result.exit_code == 0
        assert "Lane count: 2" in result.output
        assert "pre=" in result.output
        assert "post=" in result.output
        mock_diag.port_eq_tx_coeff.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eq_json(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.return_value = _sample_port_eq_coeff()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "diag", "eq", "/dev/switchtec0", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["lane_count"] == 2
        assert len(parsed["cursors"]) == 2
        assert parsed["cursors"][0]["pre"] == -6

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eq_far_end(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.return_value = _sample_port_eq_coeff()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "eq", "/dev/switchtec0", "0",
             "--end", "far_end", "--link", "previous"],
        )

        assert result.exit_code == 0
        mock_diag.port_eq_tx_coeff.assert_called_once()

    # ── crosshair ──────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_enable(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "crosshair", "/dev/switchtec0",
             "--lane", "0", "--action", "enable"],
        )

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        mock_diag.cross_hair_enable.assert_called_once_with(0)

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_disable(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "crosshair", "/dev/switchtec0", "--action", "disable"],
        )

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        mock_diag.cross_hair_disable.assert_called_once()

    @patch("serialcables_switchtec.bindings.constants.DIAG_CROSS_HAIR_MAX_LANES", 64)
    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_get(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.cross_hair_get.return_value = [_sample_crosshair_result()]
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "crosshair", "/dev/switchtec0",
             "--lane", "0", "--action", "get"],
        )

        assert result.exit_code == 0
        assert "DONE" in result.output
        mock_diag.cross_hair_get.assert_called_once_with(0, 1)

    @patch("serialcables_switchtec.bindings.constants.DIAG_CROSS_HAIR_MAX_LANES", 64)
    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_get_all_lanes(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.cross_hair_get.return_value = [_sample_crosshair_result()]
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        # Default --lane is -1 which means all lanes
        result = runner.invoke(
            cli,
            ["diag", "crosshair", "/dev/switchtec0", "--action", "get"],
        )

        assert result.exit_code == 0
        mock_diag.cross_hair_get.assert_called_once_with(0, 64)

    @patch("serialcables_switchtec.bindings.constants.DIAG_CROSS_HAIR_MAX_LANES", 64)
    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_get_json(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.cross_hair_get.return_value = [_sample_crosshair_result()]
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json-output", "diag", "crosshair", "/dev/switchtec0",
             "--lane", "0", "--action", "get"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]["state_name"] == "DONE"
        assert parsed[0]["lane_id"] == 0

    # ── eye ────────────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "eye", "/dev/switchtec0",
             "--lanes", "1,0,0,0", "--x-step", "2", "--y-step", "4"],
        )

        assert result.exit_code == 0
        assert "started" in result.output.lower()
        mock_diag.eye_start.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_default_lanes(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "eye", "/dev/switchtec0"])

        assert result.exit_code == 0
        mock_diag.eye_start.assert_called_once()

    # ── diag error handling ────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_diag_error(self, mock_dev_cls):
        mock_dev_cls.open.side_effect = SwitchtecError("MRPC error")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "ltssm", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0
        assert "MRPC error" in result.output


# ===========================================================================
# Error injection commands
# ===========================================================================


class TestInjectCommands:
    """Test the ``diag inject`` sub-command group."""

    # ── inject dllp ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp", "/dev/switchtec0", "0",
             "--data", "57005"],  # 0xDEAD = 57005
        )

        assert result.exit_code == 0
        assert "injected" in result.output.lower()
        mock_inj.inject_dllp.assert_called_once_with(0, 57005)

    # ── inject dllp-crc ───────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp_crc_enable(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp-crc", "/dev/switchtec0", "0", "--enable"],
        )

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        mock_inj.inject_dllp_crc.assert_called_once_with(0, True, 1)

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp_crc_disable(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp-crc", "/dev/switchtec0", "0", "--disable"],
        )

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        mock_inj.inject_dllp_crc.assert_called_once_with(0, False, 1)

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp_crc_custom_rate(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp-crc", "/dev/switchtec0", "0",
             "--enable", "--rate", "100"],
        )

        assert result.exit_code == 0
        mock_inj.inject_dllp_crc.assert_called_once_with(0, True, 100)

    # ── inject tlp-lcrc ───────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_tlp_lcrc_enable(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "tlp-lcrc", "/dev/switchtec0", "0", "--enable"],
        )

        assert result.exit_code == 0
        assert "enabled" in result.output.lower()
        mock_inj.inject_tlp_lcrc.assert_called_once_with(0, True, 1)

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_tlp_lcrc_disable(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "tlp-lcrc", "/dev/switchtec0", "0", "--disable"],
        )

        assert result.exit_code == 0
        assert "disabled" in result.output.lower()
        mock_inj.inject_tlp_lcrc.assert_called_once_with(0, False, 1)

    # ── inject seq-num ─────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_seq_num(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "seq-num", "/dev/switchtec0", "0"],
        )

        assert result.exit_code == 0
        assert "injected" in result.output.lower()
        mock_inj.inject_tlp_seq_num.assert_called_once_with(0)

    # ── inject ack-nack ────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_ack_nack(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "ack-nack", "/dev/switchtec0", "0",
             "--seq-num", "42", "--count", "3"],
        )

        assert result.exit_code == 0
        assert "injected" in result.output.lower()
        mock_inj.inject_ack_nack.assert_called_once_with(0, 42, 3)

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_ack_nack_default_count(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "ack-nack", "/dev/switchtec0", "0",
             "--seq-num", "10"],
        )

        assert result.exit_code == 0
        mock_inj.inject_ack_nack.assert_called_once_with(0, 10, 1)

    # ── inject cto ─────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_cto(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "cto", "/dev/switchtec0", "0"],
        )

        assert result.exit_code == 0
        assert "injected" in result.output.lower()
        mock_inj.inject_cto.assert_called_once_with(0)

    # ── inject error handling ──────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_error(self, mock_dev_cls):
        mock_dev_cls.open.side_effect = SwitchtecError("access refused")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "cto", "/dev/switchtec0", "0"],
        )

        assert result.exit_code != 0
        assert "access refused" in result.output

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp_injector_error(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj.inject_dllp.side_effect = SwitchtecError("inject failed")
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp", "/dev/switchtec0", "0",
             "--data", "1234"],
        )

        assert result.exit_code != 0
        assert "inject failed" in result.output


# ===========================================================================
# Debug flag tests
# ===========================================================================


class TestDebugFlag:
    """Verify that the --debug flag propagates through the context."""

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_debug_flag_with_device_list(self, mock_cls):
        mock_cls.list_devices.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["--debug", "device", "list"])

        assert result.exit_code == 0

    @patch("serialcables_switchtec.cli.device.SwitchtecDevice")
    def test_no_debug_flag(self, mock_cls):
        mock_cls.list_devices.return_value = []

        runner = CliRunner()
        result = runner.invoke(cli, ["device", "list"])

        assert result.exit_code == 0


# ===========================================================================
# Missing argument validation
# ===========================================================================


class TestArgumentValidation:
    """Verify that missing required arguments produce usage errors."""

    def test_device_info_missing_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["device", "info"])

        assert result.exit_code != 0

    def test_device_temp_missing_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["device", "temp"])

        assert result.exit_code != 0

    def test_device_status_missing_path(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["device", "status"])

        assert result.exit_code != 0

    def test_diag_ltssm_missing_port(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "ltssm", "/dev/switchtec0"])

        assert result.exit_code != 0

    def test_diag_ltssm_missing_device(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "ltssm"])

        assert result.exit_code != 0

    def test_diag_patgen_missing_port(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "patgen", "/dev/switchtec0"])

        assert result.exit_code != 0

    def test_diag_patmon_missing_lane(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "patmon", "/dev/switchtec0", "0"])

        assert result.exit_code != 0

    def test_diag_inject_dllp_missing_data(self):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "inject", "dllp", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0

    def test_diag_inject_ack_nack_missing_seq_num(self):
        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "inject", "ack-nack", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0

    def test_diag_loopback_invalid_speed(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "loopback", "/dev/switchtec0", "0",
             "--ltssm-speed", "gen99"],
        )

        assert result.exit_code != 0

    def test_diag_patgen_invalid_pattern(self):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "patgen", "/dev/switchtec0", "0",
             "--pattern", "invalid_pattern"],
        )

        assert result.exit_code != 0

    def test_unknown_subcommand(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["device", "nonexistent"])

        assert result.exit_code != 0


# ===========================================================================
# Serve command
# ===========================================================================


class TestServeCommand:
    """Test the ``serve`` command with mocked uvicorn."""

    @patch("serialcables_switchtec.api.app.create_app")
    def test_serve_default(self, mock_create_app):
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_uvicorn = MagicMock()

        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            result = runner.invoke(cli, ["serve"])

        assert result.exit_code == 0
        mock_create_app.assert_called_once()
        mock_uvicorn.run.assert_called_once_with(mock_app, host="127.0.0.1", port=8000)

    @patch("serialcables_switchtec.api.app.create_app")
    def test_serve_custom_host_port(self, mock_create_app):
        mock_app = MagicMock()
        mock_create_app.return_value = mock_app
        mock_uvicorn = MagicMock()

        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            runner = CliRunner()
            result = runner.invoke(
                cli, ["serve", "--host", "0.0.0.0", "--port", "9090"]
            )

        assert result.exit_code == 0
        mock_uvicorn.run.assert_called_once_with(mock_app, host="0.0.0.0", port=9090)

    def test_serve_import_error(self):
        import builtins

        original_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)

        runner = CliRunner()
        with patch("builtins.__import__", side_effect=_fake_import):
            result = runner.invoke(cli, ["serve"])

        assert result.exit_code != 0
        assert "API dependencies not installed" in result.output



# ===========================================================================
# Diagnostic command error paths
# ===========================================================================


class TestDiagErrorPaths:
    """Test SwitchtecError handling for every diag command."""

    # ── eye error ─────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.eye_start.side_effect = SwitchtecError("eye capture failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "eye", "/dev/switchtec0"])

        assert result.exit_code != 0
        assert "eye capture failed" in result.output

    # ── ltssm-clear error ─────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_ltssm_clear_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.ltssm_clear.side_effect = SwitchtecError("clear failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "ltssm-clear", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0
        assert "clear failed" in result.output

    # ── loopback error ────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_loopback_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.loopback_set.side_effect = SwitchtecError("loopback failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "loopback", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0
        assert "loopback failed" in result.output

    # ── patgen error ──────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patgen_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.pattern_gen_set.side_effect = SwitchtecError("patgen failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "patgen", "/dev/switchtec0", "0",
             "--pattern", "prbs31", "--speed", "gen4"],
        )

        assert result.exit_code != 0
        assert "patgen failed" in result.output

    # ── patmon error ──────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_patmon_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.pattern_mon_get.side_effect = SwitchtecError("patmon failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "patmon", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code != 0
        assert "patmon failed" in result.output

    # ── rcvr error ────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_rcvr_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.rcvr_obj.side_effect = SwitchtecError("rcvr failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "rcvr", "/dev/switchtec0", "0", "0"]
        )

        assert result.exit_code != 0
        assert "rcvr failed" in result.output

    # ── eq error ──────────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eq_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.port_eq_tx_coeff.side_effect = SwitchtecError("eq failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eq", "/dev/switchtec0", "0"]
        )

        assert result.exit_code != 0
        assert "eq failed" in result.output

    # ── crosshair error ───────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.DiagnosticsManager")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_crosshair_error(self, mock_dev_cls, mock_diag_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_diag = MagicMock()
        mock_diag.cross_hair_enable.side_effect = SwitchtecError("crosshair failed")
        mock_diag_cls.return_value = mock_diag

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "crosshair", "/dev/switchtec0",
             "--lane", "0", "--action", "enable"],
        )

        assert result.exit_code != 0
        assert "crosshair failed" in result.output


# ===========================================================================
# Inject command error paths
# ===========================================================================


class TestInjectErrorPaths:
    """Test SwitchtecError handling for every inject command."""

    # ── dllp-crc error ────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_dllp_crc_error(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj.inject_dllp_crc.side_effect = SwitchtecError("dllp crc failed")
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "dllp-crc", "/dev/switchtec0", "0", "--enable"],
        )

        assert result.exit_code != 0
        assert "dllp crc failed" in result.output

    # ── tlp-lcrc error ────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_tlp_lcrc_error(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj.inject_tlp_lcrc.side_effect = SwitchtecError("tlp lcrc failed")
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "tlp-lcrc", "/dev/switchtec0", "0", "--enable"],
        )

        assert result.exit_code != 0
        assert "tlp lcrc failed" in result.output

    # ── seq-num error ─────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_seq_num_error(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj.inject_tlp_seq_num.side_effect = SwitchtecError("seq num failed")
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "seq-num", "/dev/switchtec0", "0"],
        )

        assert result.exit_code != 0
        assert "seq num failed" in result.output

    # ── ack-nack error ────────────────────────────────────────────────

    @patch("serialcables_switchtec.cli.diag.ErrorInjector")
    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_inject_ack_nack_error(self, mock_dev_cls, mock_inj_cls):
        mock_dev = _make_mock_device()
        mock_dev_cls.open.return_value = mock_dev

        mock_inj = MagicMock()
        mock_inj.inject_ack_nack.side_effect = SwitchtecError("ack nack failed")
        mock_inj_cls.return_value = mock_inj

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "inject", "ack-nack", "/dev/switchtec0", "0",
             "--seq-num", "10"],
        )

        assert result.exit_code != 0
        assert "ack nack failed" in result.output
