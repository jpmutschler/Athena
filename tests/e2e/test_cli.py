"""CLI smoke tests using Click's CliRunner."""

from __future__ import annotations

from click.testing import CliRunner

from serialcables_switchtec.cli.main import cli


class TestCliHelp:
    def test_root_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
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
