"""E2E CLI tests for Phase 8 commands: perf, diag eye-fetch/cancel, fw write."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from serialcables_switchtec.cli.main import cli
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.performance import (
    BwCounterDirection,
    BwCounterResult,
    LatencyResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_device(**overrides: object) -> MagicMock:
    """Build a MagicMock that behaves like a SwitchtecDevice context manager."""
    mock_dev = MagicMock()
    mock_dev.name = overrides.get("name", "switchtec0")
    mock_dev.__enter__ = MagicMock(return_value=mock_dev)
    mock_dev.__exit__ = MagicMock(return_value=False)

    # Setup lazy property mocks
    mock_dev.diagnostics = MagicMock()
    mock_dev.injector = MagicMock()
    mock_dev.performance = MagicMock()
    mock_dev.monitor = MagicMock()

    return mock_dev


# ===========================================================================
# Help text tests
# ===========================================================================


class TestPhase8Help:
    """Verify --help renders for all new Phase 8 commands."""

    def test_perf_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "--help"])
        assert result.exit_code == 0
        assert "bw" in result.output
        assert "latency-setup" in result.output
        assert "latency" in result.output

    def test_perf_bw_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "bw", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "--ports" in result.output
        assert "--clear" in result.output

    def test_perf_latency_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "latency", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "--egress" in result.output
        assert "--clear" in result.output

    def test_perf_latency_setup_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "latency-setup", "--help"])
        assert result.exit_code == 0
        assert "--egress" in result.output
        assert "--ingress" in result.output
        assert "--clear" in result.output

    def test_diag_eye_fetch_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "eye-fetch", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "--pixels" in result.output

    def test_diag_eye_cancel_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "eye-cancel", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output

    def test_fw_write_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fw", "write", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "IMAGE_PATH" in result.output
        assert "--no-activate" in result.output
        assert "--force" in result.output


# ===========================================================================
# perf bw -- full E2E
# ===========================================================================


class TestPerfBwE2E:
    """End-to-end tests for perf bw command."""

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_table_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.performance.bw_get.return_value = [
            BwCounterResult(
                time_us=5000,
                egress=BwCounterDirection(posted=1000, comp=2000, nonposted=500),
                ingress=BwCounterDirection(posted=1500, comp=2500, nonposted=750),
            ),
        ]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "0"]
        )

        assert result.exit_code == 0
        assert "Port 0" in result.output
        assert "time=5000" in result.output
        assert "posted=1000" in result.output
        assert "comp=2000" in result.output
        assert "nonposted=500" in result.output

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_json_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.performance.bw_get.return_value = [
            BwCounterResult(
                time_us=3000,
                egress=BwCounterDirection(posted=10, comp=20, nonposted=5),
                ingress=BwCounterDirection(posted=15, comp=25, nonposted=7),
            ),
        ]

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "perf", "bw", "/dev/switchtec0", "--ports", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["time_us"] == 3000

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_error_handling(self, mock_cls) -> None:
        mock_cls.open.side_effect = SwitchtecError("no device")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec99", "--ports", "0"]
        )

        assert result.exit_code != 0
        assert "no device" in result.output


# ===========================================================================
# perf latency-setup -- full E2E
# ===========================================================================


class TestPerfLatencySetupE2E:
    """End-to-end tests for perf latency-setup command."""

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_setup_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "perf", "latency-setup", "/dev/switchtec0",
                "--egress", "3", "--ingress", "7",
            ],
        )

        assert result.exit_code == 0
        assert "configured" in result.output.lower()
        assert "egress=3" in result.output
        assert "ingress=7" in result.output

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_setup_error(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.performance.lat_setup.side_effect = SwitchtecError("invalid port combination")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "perf", "latency-setup", "/dev/switchtec0",
                "--egress", "1", "--ingress", "2",
            ],
        )

        assert result.exit_code != 0
        assert "invalid port combination" in result.output


# ===========================================================================
# perf latency -- full E2E
# ===========================================================================


class TestPerfLatencyE2E:
    """End-to-end tests for perf latency command."""

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_table_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.performance.lat_get.return_value = LatencyResult(
            egress_port_id=2,
            current_ns=55,
            max_ns=200,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "latency", "/dev/switchtec0", "--egress", "2"]
        )

        assert result.exit_code == 0
        assert "Port 2" in result.output
        assert "current=55" in result.output
        assert "max=200" in result.output

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_json_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.performance.lat_get.return_value = LatencyResult(
            egress_port_id=4,
            current_ns=99,
            max_ns=300,
        )

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json-output", "perf", "latency", "/dev/switchtec0", "--egress", "4"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["egress_port_id"] == 4
        assert parsed["current_ns"] == 99
        assert parsed["max_ns"] == 300


# ===========================================================================
# diag eye-fetch -- full E2E
# ===========================================================================


class TestDiagEyeFetchE2E:
    """End-to-end tests for diag eye-fetch command."""

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_fetch_text_output(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_result = MagicMock()
        mock_result.lane_id = 0
        mock_result.pixels = [0.0] * 100 + [1.0] * 50
        mock_result.model_dump_json.return_value = json.dumps({
            "lane_id": 0,
            "pixels": [0.0] * 100 + [1.0] * 50,
        })

        mock_dev.diagnostics.eye_fetch.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eye-fetch", "/dev/switchtec0", "--pixels", "150"]
        )

        assert result.exit_code == 0
        assert "Lane: 0" in result.output
        assert "Pixels fetched: 150" in result.output
        assert "Non-zero pixels: 50" in result.output
        mock_dev.diagnostics.eye_fetch.assert_called_once_with(150)

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_fetch_error(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.diagnostics.eye_fetch.side_effect = SwitchtecError("no capture in progress")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eye-fetch", "/dev/switchtec0"]
        )

        assert result.exit_code != 0
        assert "no capture in progress" in result.output


# ===========================================================================
# diag eye-cancel -- full E2E
# ===========================================================================


class TestDiagEyeCancelE2E:
    """End-to-end tests for diag eye-cancel command."""

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_cancel_success(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eye-cancel", "/dev/switchtec0"]
        )

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()
        mock_dev.diagnostics.eye_cancel.assert_called_once()

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_eye_cancel_error(self, mock_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_dev.diagnostics.eye_cancel.side_effect = SwitchtecError("cancel failed")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["diag", "eye-cancel", "/dev/switchtec0"]
        )

        assert result.exit_code != 0
        assert "cancel failed" in result.output


# ===========================================================================
# fw write -- full E2E
# ===========================================================================


class TestFwWriteE2E:
    """End-to-end tests for fw write command."""

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_success(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "write", "/dev/switchtec0", str(fw_file)]
        )

        assert result.exit_code == 0
        assert "written" in result.output.lower()
        mock_dev.firmware.write_firmware.assert_called_once()

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_json_output(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "fw", "write", "/dev/switchtec0", str(fw_file)]
        )

        assert result.exit_code == 0
        # The JSON output line should be parseable
        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        # Find the JSON line (may have a progress line before it)
        json_found = False
        for line in lines:
            try:
                parsed = json.loads(line)
                assert parsed["status"] == "written"
                json_found = True
                break
            except json.JSONDecodeError:
                continue
        assert json_found, f"No JSON found in output: {result.output}"

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_with_no_activate(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fw", "write", "/dev/switchtec0", str(fw_file), "--no-activate"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_dev.firmware.write_firmware.call_args
        assert call_kwargs[1]["dont_activate"] is True

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_with_force(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["fw", "write", "/dev/switchtec0", str(fw_file), "--force"],
        )

        assert result.exit_code == 0
        call_kwargs = mock_dev.firmware.write_firmware.call_args
        assert call_kwargs[1]["force"] is True

    def test_fw_write_nonexistent_image(self) -> None:
        """Click's exists=True should reject nonexistent paths."""
        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "write", "/dev/switchtec0", "/nonexistent/firmware.img"]
        )
        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_error(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_dev = _make_mock_device()
        mock_dev.firmware.write_firmware.side_effect = SwitchtecError("write failed")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "write", "/dev/switchtec0", str(fw_file)]
        )

        assert result.exit_code != 0
        assert "write failed" in result.output

    @patch("serialcables_switchtec.cli.firmware.SwitchtecDevice")
    def test_fw_write_device_open_error(self, mock_cls, tmp_path) -> None:
        fw_file = tmp_path / "firmware.img"
        fw_file.write_bytes(b"\x00" * 1024)

        mock_cls.open.side_effect = SwitchtecError("device busy")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["fw", "write", "/dev/switchtec0", str(fw_file)]
        )

        assert result.exit_code != 0
        assert "device busy" in result.output
