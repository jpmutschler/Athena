"""Tests for the ``perf`` CLI command group."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
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
    return mock_dev


def _sample_bw_results(port_ids: list[int]) -> list[BwCounterResult]:
    """Create sample BwCounterResult objects for the given port IDs."""
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
# Help text tests
# ===========================================================================


class TestPerfHelp:
    """Verify --help renders for all perf commands."""

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

    def test_perf_latency_setup_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "latency-setup", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "--egress" in result.output
        assert "--ingress" in result.output
        assert "--clear" in result.output

    def test_perf_latency_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["perf", "latency", "--help"])
        assert result.exit_code == 0
        assert "DEVICE_PATH" in result.output
        assert "--egress" in result.output
        assert "--clear" in result.output


# ===========================================================================
# perf bw
# ===========================================================================


class TestPerfBw:
    """Test the ``perf bw`` command."""

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_single_port(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.bw_get.return_value = _sample_bw_results([0])
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "0"]
        )

        assert result.exit_code == 0
        assert "Port 0" in result.output
        assert "Egress" in result.output
        assert "Ingress" in result.output
        mock_mgr.bw_get.assert_called_once_with([0], clear=False)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_multiple_ports(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.bw_get.return_value = _sample_bw_results([0, 1, 2])
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "0,1,2"]
        )

        assert result.exit_code == 0
        assert "Port 0" in result.output
        assert "Port 1" in result.output
        assert "Port 2" in result.output
        mock_mgr.bw_get.assert_called_once_with([0, 1, 2], clear=False)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_with_clear(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.bw_get.return_value = _sample_bw_results([5])
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "5", "--clear"]
        )

        assert result.exit_code == 0
        mock_mgr.bw_get.assert_called_once_with([5], clear=True)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_json_output(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.bw_get.return_value = _sample_bw_results([0])
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json-output", "perf", "bw", "/dev/switchtec0", "--ports", "0"]
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["time_us"] == 1000
        assert parsed[0]["egress"]["posted"] == 100

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_shows_counter_details(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.bw_get.return_value = _sample_bw_results([0])
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "0"]
        )

        assert result.exit_code == 0
        assert "posted=100" in result.output
        assert "comp=200" in result.output
        assert "nonposted=50" in result.output
        assert "time=1000" in result.output

    def test_bw_invalid_ports_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0", "--ports", "abc"]
        )
        # Should fail with non-zero exit code
        assert result.exit_code != 0

    def test_bw_missing_ports_option(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec0"]
        )
        # --ports is required
        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_bw_device_error(self, mock_cls) -> None:
        mock_cls.open.side_effect = SwitchtecError("device not found")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "bw", "/dev/switchtec99", "--ports", "0"]
        )

        assert result.exit_code != 0
        assert "device not found" in result.output


# ===========================================================================
# perf latency-setup
# ===========================================================================


class TestPerfLatencySetup:
    """Test the ``perf latency-setup`` command."""

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_setup(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "perf", "latency-setup", "/dev/switchtec0",
                "--egress", "1", "--ingress", "2",
            ],
        )

        assert result.exit_code == 0
        assert "configured" in result.output.lower()
        assert "egress=1" in result.output
        assert "ingress=2" in result.output
        mock_mgr.lat_setup.assert_called_once_with(1, 2, clear=False)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_setup_with_clear(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "perf", "latency-setup", "/dev/switchtec0",
                "--egress", "3", "--ingress", "4", "--clear",
            ],
        )

        assert result.exit_code == 0
        mock_mgr.lat_setup.assert_called_once_with(3, 4, clear=True)

    def test_latency_setup_missing_egress(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency-setup", "/dev/switchtec0", "--ingress", "2"],
        )
        # --egress is required
        assert result.exit_code != 0

    def test_latency_setup_missing_ingress(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency-setup", "/dev/switchtec0", "--egress", "1"],
        )
        # --ingress is required
        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_setup_error(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.lat_setup.side_effect = SwitchtecError("setup failed")
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "perf", "latency-setup", "/dev/switchtec0",
                "--egress", "1", "--ingress", "2",
            ],
        )

        assert result.exit_code != 0
        assert "setup failed" in result.output


# ===========================================================================
# perf latency
# ===========================================================================


class TestPerfLatency:
    """Test the ``perf latency`` command."""

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_get(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.lat_get.return_value = _sample_latency_result(5)
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency", "/dev/switchtec0", "--egress", "5"],
        )

        assert result.exit_code == 0
        assert "Port 5" in result.output
        assert "current=42" in result.output
        assert "max=128" in result.output
        mock_mgr.lat_get.assert_called_once_with(5, clear=False)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_get_with_clear(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.lat_get.return_value = _sample_latency_result(2)
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency", "/dev/switchtec0", "--egress", "2", "--clear"],
        )

        assert result.exit_code == 0
        mock_mgr.lat_get.assert_called_once_with(2, clear=True)

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_json_output(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.lat_get.return_value = _sample_latency_result(7)
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["--json-output", "perf", "latency", "/dev/switchtec0", "--egress", "7"],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["egress_port_id"] == 7
        assert parsed["current_ns"] == 42
        assert parsed["max_ns"] == 128

    def test_latency_missing_egress(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["perf", "latency", "/dev/switchtec0"]
        )
        # --egress is required
        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.perf.PerformanceManager")
    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_error(self, mock_cls, mock_perf_cls) -> None:
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        mock_mgr = MagicMock()
        mock_mgr.lat_get.side_effect = SwitchtecError("read failed")
        mock_perf_cls.return_value = mock_mgr

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency", "/dev/switchtec0", "--egress", "0"],
        )

        assert result.exit_code != 0
        assert "read failed" in result.output

    @patch("serialcables_switchtec.cli.perf.SwitchtecDevice")
    def test_latency_device_open_error(self, mock_cls) -> None:
        mock_cls.open.side_effect = SwitchtecError("cannot open device")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["perf", "latency", "/dev/switchtec99", "--egress", "0"],
        )

        assert result.exit_code != 0
        assert "cannot open device" in result.output
