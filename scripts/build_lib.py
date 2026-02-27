"""Cross-platform build script for the Switchtec C library.

Builds libswitchtec from the vendored C source tree and copies the resulting
shared library to vendor/switchtec/lib/ for the Python bindings to load.

Usage:
    python scripts/build_lib.py
"""

from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
C_SOURCE_DIR = PROJECT_ROOT / "resources" / "switchtec-user-4.4-rc2"
VENDOR_LIB_DIR = PROJECT_ROOT / "vendor" / "switchtec" / "lib"


def _find_msys2() -> Path:
    """Find the MSYS2 bash executable on Windows."""
    candidates = [
        Path("C:/msys64/usr/bin/bash.exe"),
        Path("D:/msys64/usr/bin/bash.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    msys2_root = Path(__import__("os").environ.get("MSYS2_ROOT", ""))
    if msys2_root.name:
        bash = msys2_root / "usr" / "bin" / "bash.exe"
        if bash.exists():
            return bash

    raise FileNotFoundError(
        "MSYS2 not found. Install MSYS2 or run: powershell scripts/setup_msys2.ps1\n"
        "Searched: C:\\msys64, D:\\msys64, MSYS2_ROOT env var"
    )


def _win_path_to_msys(p: Path) -> str:
    """Convert a Windows path to MSYS2 path notation."""
    posix = p.as_posix()
    if len(posix) >= 2 and posix[1] == ":":
        drive = posix[0].lower()
        return f"/{drive}{posix[2:]}"
    return posix


def _build_windows() -> Path:
    """Build on Windows using MSYS2/MinGW."""
    bash = _find_msys2()
    mingw_bin = bash.parent.parent.parent / "mingw64" / "bin"

    if not (mingw_bin / "gcc.exe").exists():
        raise FileNotFoundError(
            f"MinGW64 GCC not found at {mingw_bin}. "
            "Run: powershell scripts/setup_msys2.ps1"
        )

    source_dir = _win_path_to_msys(C_SOURCE_DIR)
    env_path = f"/mingw64/bin:/usr/bin:/bin"

    build_cmd = (
        f"export PATH='{env_path}' && "
        f"cd '{source_dir}' && "
        f"./configure --host=x86_64-w64-mingw32 && "
        f"make -j$(nproc) clean && "
        f"make -j$(nproc)"
    )

    print(f"[build_lib] Building with MSYS2 bash: {bash}")
    print(f"[build_lib] Source dir: {C_SOURCE_DIR}")

    result = subprocess.run(
        [str(bash), "-lc", build_cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[build_lib] STDOUT:", result.stdout[-2000:] if result.stdout else "")
        print("[build_lib] STDERR:", result.stderr[-2000:] if result.stderr else "")
        raise RuntimeError(
            f"Build failed with exit code {result.returncode}. "
            "See output above for details."
        )

    # MinGW autotools produces switchtec-0.dll in lib/.libs/
    dll_candidates = [
        C_SOURCE_DIR / "lib" / ".libs" / "switchtec-0.dll",
        C_SOURCE_DIR / "lib" / ".libs" / "libswitchtec-0.dll",
        C_SOURCE_DIR / "lib" / ".libs" / "switchtec.dll",
    ]
    for candidate in dll_candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Built DLL not found. Expected one of:\n"
        + "\n".join(f"  {c}" for c in dll_candidates)
    )


def _build_linux() -> Path:
    """Build on Linux using system GCC."""
    print(f"[build_lib] Building with system GCC")
    print(f"[build_lib] Source dir: {C_SOURCE_DIR}")

    result = subprocess.run(
        ["bash", "-c", f"cd '{C_SOURCE_DIR}' && ./configure && make -j$(nproc)"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("[build_lib] STDOUT:", result.stdout[-2000:] if result.stdout else "")
        print("[build_lib] STDERR:", result.stderr[-2000:] if result.stderr else "")
        raise RuntimeError(f"Build failed with exit code {result.returncode}")

    so_candidates = [
        C_SOURCE_DIR / "lib" / ".libs" / "libswitchtec.so",
        C_SOURCE_DIR / "lib" / ".libs" / "libswitchtec.so.0",
        C_SOURCE_DIR / "lib" / ".libs" / "libswitchtec.so.0.0.0",
    ]
    for candidate in so_candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Built .so not found. Expected one of:\n"
        + "\n".join(f"  {c}" for c in so_candidates)
    )


def _verify_library(path: Path) -> None:
    """Verify the library can be loaded with ctypes."""
    try:
        lib = ctypes.CDLL(str(path))
        print(f"[build_lib] Library loaded successfully: {path}")
        if hasattr(lib, "switchtec_open"):
            print("[build_lib] Verified: switchtec_open symbol found")
    except OSError as e:
        raise RuntimeError(f"Library verification failed: {e}") from e


def build() -> Path:
    """Build the Switchtec C library and copy to vendor directory.

    Returns:
        Path to the installed library in vendor/switchtec/lib/.
    """
    VENDOR_LIB_DIR.mkdir(parents=True, exist_ok=True)

    system = platform.system()
    if system == "Windows":
        built_lib = _build_windows()
        dest_name = "switchtec.dll"
    elif system == "Linux":
        built_lib = _build_linux()
        dest_name = "libswitchtec.so"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    dest = VENDOR_LIB_DIR / dest_name
    print(f"[build_lib] Copying {built_lib} -> {dest}")
    shutil.copy2(str(built_lib), str(dest))

    _verify_library(dest)

    print(f"[build_lib] Build complete: {dest}")
    return dest


if __name__ == "__main__":
    try:
        build()
    except Exception as e:
        print(f"[build_lib] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
