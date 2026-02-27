"""Tests for FirmwareManager.write_firmware functionality."""

from __future__ import annotations

import ctypes
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from serialcables_switchtec.core.firmware import FirmwareManager
from serialcables_switchtec.exceptions import InvalidParameterError, SwitchtecError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fw_manager(device, mock_library):
    """Create a FirmwareManager with a mocked device."""
    # Add the write_fd function that FakeLibrary doesn't include
    mock_library.switchtec_fw_write_fd = MagicMock(return_value=0)
    return FirmwareManager(device)


@pytest.fixture
def tmp_firmware_file(tmp_path):
    """Create a temporary firmware image file for testing."""
    fw_file = tmp_path / "firmware.img"
    fw_file.write_bytes(b"\x00" * 4096)
    return fw_file


# ===========================================================================
# write_firmware -- path validation
# ===========================================================================


class TestWriteFirmwarePathValidation:
    """Test that write_firmware validates the image path exists."""

    def test_raises_when_file_not_found(self, fw_manager) -> None:
        with pytest.raises(InvalidParameterError, match="Firmware image not found"):
            fw_manager.write_firmware("/nonexistent/path/firmware.img")

    def test_raises_with_nonexistent_relative_path(self, fw_manager) -> None:
        with pytest.raises(InvalidParameterError, match="Firmware image not found"):
            fw_manager.write_firmware("definitely_not_a_real_file_12345.bin")

    def test_raises_with_directory_path(self, fw_manager, tmp_path) -> None:
        # tmp_path is a directory, not a file -- Path.exists() is True
        # but write_firmware should still attempt, the C library decides
        # This tests the path exists check only
        nonexistent = tmp_path / "does_not_exist.bin"
        with pytest.raises(InvalidParameterError, match="Firmware image not found"):
            fw_manager.write_firmware(str(nonexistent))


# ===========================================================================
# write_firmware -- successful operation with fd
# ===========================================================================


class TestWriteFirmwareSuccess:
    """Test firmware write succeeds with correct fd handling."""

    def test_calls_lib_with_fd(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(str(tmp_firmware_file))

        mock_library.switchtec_fw_write_fd.assert_called_once()
        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        # handle
        assert call_args[0] == 0xDEADBEEF
        # fd -- an integer file descriptor
        assert isinstance(call_args[1], int)
        assert call_args[1] >= 0
        # dont_activate = False -> 0
        assert call_args[2] == 0
        # force = False -> 0
        assert call_args[3] == 0

    def test_passes_dont_activate_flag(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(
            str(tmp_firmware_file), dont_activate=True
        )

        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        assert call_args[2] == 1  # dont_activate=True -> 1

    def test_passes_force_flag(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(
            str(tmp_firmware_file), force=True
        )

        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        assert call_args[3] == 1  # force=True -> 1

    def test_passes_both_flags(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(
            str(tmp_firmware_file), dont_activate=True, force=True
        )

        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        assert call_args[2] == 1  # dont_activate
        assert call_args[3] == 1  # force

    def test_accepts_path_object(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(tmp_firmware_file)
        mock_library.switchtec_fw_write_fd.assert_called_once()

    def test_fd_is_closed_after_success(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        """Verify the file descriptor is properly closed after a successful write."""
        opened_fds: list[int] = []

        original_open = os.open
        original_close = os.close

        def tracking_open(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            opened_fds.append(fd)
            return fd

        closed_fds: list[int] = []

        def tracking_close(fd):
            closed_fds.append(fd)
            return original_close(fd)

        with patch("os.open", side_effect=tracking_open):
            with patch("os.close", side_effect=tracking_close):
                fw_manager.write_firmware(str(tmp_firmware_file))

        assert len(opened_fds) == 1
        assert len(closed_fds) == 1
        assert opened_fds[0] == closed_fds[0]


# ===========================================================================
# write_firmware -- progress callback
# ===========================================================================


class TestWriteFirmwareCallback:
    """Test that the progress callback is wired through to the C library."""

    def test_callback_passed_to_lib(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        callback = MagicMock()
        fw_manager.write_firmware(
            str(tmp_firmware_file), progress_callback=callback
        )

        mock_library.switchtec_fw_write_fd.assert_called_once()
        # The 5th positional arg (index 4) is the ctypes callback wrapper
        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        assert call_args[4] is not None

    def test_no_callback_uses_noop(
        self, fw_manager, mock_library, tmp_firmware_file
    ) -> None:
        fw_manager.write_firmware(
            str(tmp_firmware_file), progress_callback=None
        )

        mock_library.switchtec_fw_write_fd.assert_called_once()
        call_args = mock_library.switchtec_fw_write_fd.call_args[0]
        # Should still have a callback (the noop wrapper), not None
        assert call_args[4] is not None


# ===========================================================================
# write_firmware -- error handling
# ===========================================================================


class TestWriteFirmwareErrors:
    """Test firmware write error paths."""

    def test_raises_on_lib_error(
        self, fw_manager, mock_library, tmp_firmware_file, monkeypatch
    ) -> None:
        mock_library.switchtec_fw_write_fd.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)

        with pytest.raises(SwitchtecError):
            fw_manager.write_firmware(str(tmp_firmware_file))

    def test_fd_closed_on_lib_error(
        self, fw_manager, mock_library, tmp_firmware_file, monkeypatch
    ) -> None:
        """File descriptor must be closed even when the C library returns an error."""
        mock_library.switchtec_fw_write_fd.return_value = -1
        monkeypatch.setattr(ctypes, "get_errno", lambda: 0)

        closed_fds: list[int] = []
        original_close = os.close

        def tracking_close(fd):
            closed_fds.append(fd)
            return original_close(fd)

        with patch("os.close", side_effect=tracking_close):
            with pytest.raises(SwitchtecError):
                fw_manager.write_firmware(str(tmp_firmware_file))

        assert len(closed_fds) == 1
