"""Tests for scripts/build_lib.py."""

from __future__ import annotations

import platform
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import helpers -- build_lib lives outside the package in scripts/
# ---------------------------------------------------------------------------

import importlib
import sys


@pytest.fixture(autouse=True)
def _import_build_lib():
    """Ensure scripts/build_lib is importable."""
    scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)


def _get_build_lib():
    """Import (or reload) build_lib so each test sees a fresh module."""
    if "build_lib" in sys.modules:
        return importlib.reload(sys.modules["build_lib"])
    return importlib.import_module("build_lib")


# ===========================================================================
# _win_path_to_msys
# ===========================================================================


class TestWinPathToMsys:
    """Test Windows-to-MSYS path conversion."""

    def test_converts_c_drive(self) -> None:
        build_lib = _get_build_lib()
        result = build_lib._win_path_to_msys(Path("C:/Users/josh/code"))
        assert result == "/c/Users/josh/code"

    def test_converts_d_drive(self) -> None:
        build_lib = _get_build_lib()
        result = build_lib._win_path_to_msys(Path("D:/projects/test"))
        assert result == "/d/projects/test"

    def test_preserves_posix_path(self) -> None:
        build_lib = _get_build_lib()
        result = build_lib._win_path_to_msys(Path("/usr/local/lib"))
        assert result == "/usr/local/lib"

    def test_lowercases_drive_letter(self) -> None:
        build_lib = _get_build_lib()
        # Path normalises the drive letter on Windows, but as_posix keeps it
        # We test with a known pattern
        result = build_lib._win_path_to_msys(Path("E:/Some/Path"))
        assert result.startswith("/e/")

    def test_deep_nested_path(self) -> None:
        build_lib = _get_build_lib()
        p = Path("C:/a/b/c/d/e/f/g.txt")
        result = build_lib._win_path_to_msys(p)
        assert result == "/c/a/b/c/d/e/f/g.txt"

    def test_root_drive_only(self) -> None:
        build_lib = _get_build_lib()
        result = build_lib._win_path_to_msys(Path("C:/"))
        assert result == "/c/"


# ===========================================================================
# _find_msys2
# ===========================================================================


class TestFindMsys2:
    """Test MSYS2 discovery with mocked filesystem."""

    @patch("pathlib.Path.exists", return_value=False)
    @patch.dict("os.environ", {}, clear=True)
    def test_raises_when_not_found(self, mock_exists) -> None:
        build_lib = _get_build_lib()
        with pytest.raises(FileNotFoundError, match="MSYS2 not found"):
            build_lib._find_msys2()

    def test_finds_c_msys64(self) -> None:
        build_lib = _get_build_lib()

        def _side_effect(self_path=None):
            return str(self_path) == "C:\\msys64\\usr\\bin\\bash.exe"

        with patch.object(Path, "exists", side_effect=lambda: True) as mock_ex:
            # First candidate exists
            with patch.object(
                Path, "exists",
                side_effect=[True],  # first candidate returns True
            ):
                result = build_lib._find_msys2()
                assert "bash" in str(result).lower()

    def test_finds_d_msys64(self) -> None:
        build_lib = _get_build_lib()
        with patch.object(
            Path, "exists",
            side_effect=[False, True],  # C:/ fails, D:/ succeeds
        ):
            result = build_lib._find_msys2()
            assert "bash" in str(result).lower()

    @patch.dict("os.environ", {"MSYS2_ROOT": "F:/msys2"})
    def test_finds_via_env_var(self) -> None:
        build_lib = _get_build_lib()
        with patch.object(
            Path, "exists",
            side_effect=[False, False, True],  # C:/ fails, D:/ fails, env var succeeds
        ):
            result = build_lib._find_msys2()
            assert "bash" in str(result).lower()

    @patch.dict("os.environ", {"MSYS2_ROOT": ""})
    def test_empty_env_var_falls_through(self) -> None:
        build_lib = _get_build_lib()
        with patch.object(
            Path, "exists",
            side_effect=[False, False],  # All candidates fail
        ):
            with pytest.raises(FileNotFoundError, match="MSYS2 not found"):
                build_lib._find_msys2()


# ===========================================================================
# build()
# ===========================================================================


class TestBuild:
    """Test the build() dispatch function."""

    def test_dispatches_to_windows(self) -> None:
        build_lib = _get_build_lib()
        with (
            patch.object(build_lib, "_build_windows", return_value=Path("C:/build/switchtec-0.dll")) as mock_win,
            patch.object(build_lib, "_verify_library") as mock_verify,
            patch.object(build_lib.shutil, "copy2") as mock_copy,
            patch.object(build_lib.platform, "system", return_value="Windows"),
            patch.object(Path, "mkdir"),
        ):
            result = build_lib.build()

        mock_win.assert_called_once()
        mock_copy.assert_called_once()
        mock_verify.assert_called_once()
        assert "switchtec.dll" in str(result)

    def test_dispatches_to_linux(self) -> None:
        build_lib = _get_build_lib()
        with (
            patch.object(build_lib, "_build_linux", return_value=Path("/build/libswitchtec.so")) as mock_linux,
            patch.object(build_lib, "_verify_library") as mock_verify,
            patch.object(build_lib.shutil, "copy2") as mock_copy,
            patch.object(build_lib.platform, "system", return_value="Linux"),
            patch.object(Path, "mkdir"),
        ):
            result = build_lib.build()

        mock_linux.assert_called_once()
        mock_copy.assert_called_once()
        mock_verify.assert_called_once()
        assert "libswitchtec.so" in str(result)

    def test_unsupported_platform_raises(self) -> None:
        build_lib = _get_build_lib()
        with (
            patch.object(build_lib.platform, "system", return_value="Darwin"),
            patch.object(Path, "mkdir"),
        ):
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                build_lib.build()

    def test_creates_vendor_dir(self) -> None:
        build_lib = _get_build_lib()
        with (
            patch.object(build_lib, "_build_windows", return_value=Path("C:/build/switchtec-0.dll")),
            patch.object(build_lib, "_verify_library"),
            patch.object(build_lib.shutil, "copy2"),
            patch.object(build_lib.platform, "system", return_value="Windows"),
            patch.object(Path, "mkdir") as mock_mkdir,
        ):
            build_lib.build()

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)


# ===========================================================================
# _verify_library
# ===========================================================================


class TestVerifyLibrary:
    """Test library verification."""

    def test_verify_succeeds(self) -> None:
        build_lib = _get_build_lib()
        mock_lib = MagicMock()
        mock_lib.switchtec_open = MagicMock()

        lib_path = Path("/some/lib.so")
        with patch.object(build_lib.ctypes, "CDLL", return_value=mock_lib) as mock_cdll:
            # Should not raise
            build_lib._verify_library(lib_path)
            mock_cdll.assert_called_once_with(str(lib_path))

    def test_verify_raises_on_load_failure(self) -> None:
        build_lib = _get_build_lib()
        with patch.object(
            build_lib.ctypes, "CDLL", side_effect=OSError("cannot load")
        ):
            with pytest.raises(RuntimeError, match="Library verification failed"):
                build_lib._verify_library(Path("/bad/lib.so"))
