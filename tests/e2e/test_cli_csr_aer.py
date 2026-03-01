"""E2E CLI tests for CSR read/write and AER event generation commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from serialcables_switchtec.cli.main import cli
from serialcables_switchtec.exceptions import SwitchtecError


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


class TestCsrAerHelp:
    """Verify --help renders for CSR and AER commands."""

    def test_fabric_csr_read_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fabric", "csr-read", "--help"])
        assert result.exit_code == 0
        assert "--pdfid" in result.output
        assert "--addr" in result.output
        assert "--width" in result.output

    def test_fabric_csr_write_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["fabric", "csr-write", "--help"])
        assert result.exit_code == 0
        assert "--pdfid" in result.output
        assert "--addr" in result.output
        assert "--value" in result.output
        assert "--width" in result.output

    def test_diag_aer_gen_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["diag", "aer-gen", "--help"])
        assert result.exit_code == 0
        assert "--error-id" in result.output
        assert "--trigger" in result.output


# ===========================================================================
# CSR Read commands
# ===========================================================================


class TestCsrReadCli:
    """Test the ``fabric csr-read`` sub-command with mocked core classes."""

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_read_happy_path(self, mock_cls: MagicMock) -> None:
        """Read a 32-bit register at 0x10, verify output contains the value."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_read.return_value = 0xDEADBEEF
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x10", "--width", "32",
            ],
        )

        assert result.exit_code == 0
        assert "deadbeef" in result.output.lower()
        mock_dev.fabric.csr_read.assert_called_once_with(256, 0x10, 32)

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_read_json_output(self, mock_cls: MagicMock) -> None:
        """JSON output should contain pdfid, addr, width, and value fields."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_read.return_value = 0x42
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x10", "--width", "32",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["pdfid"] == 256
        assert parsed["addr"] == "0x10"
        assert parsed["width"] == 32
        assert parsed["value"] == "0x42"

    def test_csr_read_invalid_addr(self) -> None:
        """Non-numeric --addr should produce a BadParameter error."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "garbage", "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "invalid address" in result.output.lower()

    def test_csr_read_addr_out_of_range(self) -> None:
        """Address above 0xFFF should be rejected."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x10000", "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "0x000-0xFFF" in result.output or "addr" in result.output.lower()

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_read_width_8(self, mock_cls: MagicMock) -> None:
        """8-bit read should work at any byte-aligned address."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_read.return_value = 0xAB
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "0", "--addr", "0x03", "--width", "8",
            ],
        )

        assert result.exit_code == 0
        assert "ab" in result.output.lower()
        mock_dev.fabric.csr_read.assert_called_once_with(0, 0x03, 8)

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_read_width_16(self, mock_cls: MagicMock) -> None:
        """16-bit read should work at even address."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_read.return_value = 0xCAFE
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "100", "--addr", "0x04", "--width", "16",
            ],
        )

        assert result.exit_code == 0
        assert "cafe" in result.output.lower()

    def test_csr_read_unaligned_32bit(self) -> None:
        """32-bit read at non-4-byte-aligned address should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x03", "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "aligned" in result.output.lower() or "4-byte" in result.output

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_read_device_error(self, mock_cls: MagicMock) -> None:
        """SwitchtecError during csr_read should abort with error message."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_read.side_effect = SwitchtecError("mrpc failed")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-read", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x10", "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "mrpc failed" in result.output


# ===========================================================================
# CSR Write commands
# ===========================================================================


class TestCsrWriteCli:
    """Test the ``fabric csr-write`` sub-command with mocked core classes."""

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_write_happy_path(self, mock_cls: MagicMock) -> None:
        """Write 0x06 at 0x04 with width 16, verify device call."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x04", "--value", "0x06",
                "--width", "16",
            ],
        )

        assert result.exit_code == 0
        assert "0x4" in result.output or "0x04" in result.output
        mock_dev.fabric.csr_write.assert_called_once_with(256, 0x04, 0x06, 16)

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_write_json_output(self, mock_cls: MagicMock) -> None:
        """JSON output should contain written=True and all parameters."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x04", "--value", "0x06",
                "--width", "16",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["written"] is True
        assert parsed["pdfid"] == 256
        assert parsed["addr"] == "0x4"
        assert parsed["width"] == 16
        assert parsed["value"] == "0x6"

    def test_csr_write_value_overflow(self) -> None:
        """Writing 0xFFFF to an 8-bit register should be rejected."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x00", "--value", "0xFFFF",
                "--width", "8",
            ],
        )

        assert result.exit_code != 0
        assert "exceeds" in result.output.lower() or "max" in result.output.lower()

    def test_csr_write_unaligned_32bit(self) -> None:
        """Writing with 32-bit width at 0x03 (non-aligned) should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x03", "--value", "0x01",
                "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "aligned" in result.output.lower() or "4-byte" in result.output

    def test_csr_write_unaligned_16bit(self) -> None:
        """Writing with 16-bit width at 0x01 (odd) should fail."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x01", "--value", "0x01",
                "--width", "16",
            ],
        )

        assert result.exit_code != 0
        assert "even" in result.output.lower() or "16-bit" in result.output

    def test_csr_write_invalid_value(self) -> None:
        """Non-numeric --value should produce a BadParameter error."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x00", "--value", "notavalue",
                "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "invalid value" in result.output.lower()

    def test_csr_write_addr_out_of_range(self) -> None:
        """Address above 0xFFF should be rejected for writes too."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x10000", "--value", "0x01",
                "--width", "32",
            ],
        )

        assert result.exit_code != 0

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_write_device_error(self, mock_cls: MagicMock) -> None:
        """SwitchtecError during csr_write should abort with error message."""
        mock_dev = _make_mock_device()
        mock_dev.fabric.csr_write.side_effect = SwitchtecError("write failed")
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x04", "--value", "0x01",
                "--width", "32",
            ],
        )

        assert result.exit_code != 0
        assert "write failed" in result.output

    @patch("serialcables_switchtec.cli.fabric.SwitchtecDevice")
    def test_csr_write_max_8bit_value(self, mock_cls: MagicMock) -> None:
        """Writing 0xFF to an 8-bit register should succeed (boundary)."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "fabric", "csr-write", "/dev/switchtec0",
                "--pdfid", "256", "--addr", "0x00", "--value", "0xFF",
                "--width", "8",
            ],
        )

        assert result.exit_code == 0
        mock_dev.fabric.csr_write.assert_called_once_with(256, 0x00, 0xFF, 8)


# ===========================================================================
# AER Event Generation commands
# ===========================================================================


class TestAerGenCli:
    """Test the ``diag aer-gen`` sub-command with mocked core classes."""

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_aer_gen_happy_path(self, mock_cls: MagicMock) -> None:
        """Generate AER event on port 0 with error_id 1."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "aer-gen", "/dev/switchtec0", "0", "--error-id", "1"],
        )

        assert result.exit_code == 0
        assert "AER event generated" in result.output
        assert "port 0" in result.output
        mock_dev.diagnostics.aer_event_gen.assert_called_once_with(0, 1, 0)

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_aer_gen_json_output(self, mock_cls: MagicMock) -> None:
        """JSON output should contain port_id, error_id, trigger, generated."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "--json-output", "diag", "aer-gen", "/dev/switchtec0", "0",
                "--error-id", "1",
            ],
        )

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["port_id"] == 0
        assert parsed["error_id"] == 1
        assert parsed["trigger"] == 0
        assert parsed["generated"] is True

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_aer_gen_with_trigger(self, mock_cls: MagicMock) -> None:
        """AER gen with custom trigger value should pass it through."""
        mock_dev = _make_mock_device()
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "diag", "aer-gen", "/dev/switchtec0", "5",
                "--error-id", "42", "--trigger", "7",
            ],
        )

        assert result.exit_code == 0
        mock_dev.diagnostics.aer_event_gen.assert_called_once_with(5, 42, 7)

    @patch("serialcables_switchtec.cli.diag.SwitchtecDevice")
    def test_aer_gen_device_error(self, mock_cls: MagicMock) -> None:
        """SwitchtecError during aer_event_gen should abort with error."""
        mock_dev = _make_mock_device()
        mock_dev.diagnostics.aer_event_gen.side_effect = SwitchtecError(
            "aer gen failed"
        )
        mock_cls.open.return_value = mock_dev

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "aer-gen", "/dev/switchtec0", "0", "--error-id", "1"],
        )

        assert result.exit_code != 0
        assert "aer gen failed" in result.output

    def test_aer_gen_port_out_of_range(self) -> None:
        """Port 60 should be rejected by the IntRange(0, 59) constraint."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["diag", "aer-gen", "/dev/switchtec0", "60", "--error-id", "1"],
        )

        assert result.exit_code != 0
