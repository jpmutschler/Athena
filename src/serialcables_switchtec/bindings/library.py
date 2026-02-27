"""Platform-aware Switchtec shared library loader.

Uses CDLL (cdecl calling convention) on all platforms.
Searches: vendor/switchtec, SWITCHTEC_LIB_DIR env, system paths.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from serialcables_switchtec.exceptions import LibraryLoadError
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)

_lib_instance: ctypes.CDLL | None = None


def _find_library_paths() -> list[Path]:
    """Build a list of candidate paths for the Switchtec shared library.

    Search order:
    1. SWITCHTEC_LIB_DIR environment variable (explicit override)
    2. Vendored build in vendor/switchtec/lib/ (built by scripts/build_lib.py)
    3. System library paths (LD_LIBRARY_PATH / PATH)
    """
    candidates: list[Path] = []

    # 1. SWITCHTEC_LIB_DIR environment variable (explicit override)
    env_dir = os.environ.get("SWITCHTEC_LIB_DIR")
    if env_dir:
        p = Path(env_dir)
        if sys.platform == "win32":
            candidates.append(p / "switchtec.dll")
        else:
            for so in sorted(p.glob("libswitchtec*.so*"), reverse=True):
                candidates.append(so)
            candidates.append(p / "libswitchtec.so")

    # 2. Vendored build (relative to this package)
    pkg_dir = Path(__file__).resolve().parent.parent.parent.parent
    vendor_dir = pkg_dir / "vendor" / "switchtec"

    if sys.platform == "win32":
        candidates.append(vendor_dir / "lib" / "switchtec.dll")
        candidates.append(vendor_dir / "switchtec.dll")
    else:
        candidates.append(vendor_dir / "lib" / "libswitchtec.so")
        candidates.append(vendor_dir / "libswitchtec.so")
        candidates.append(vendor_dir / ".libs" / "libswitchtec.so")

    # 3. System library paths
    if sys.platform != "win32":
        for lib_dir in ["/usr/local/lib", "/usr/lib", "/usr/lib64", "/opt/switchtec/lib"]:
            p = Path(lib_dir)
            for so in sorted(p.glob("libswitchtec*.so*"), reverse=True):
                candidates.append(so)
            candidates.append(p / "libswitchtec.so")

    return candidates


def load_library(path: str | Path | None = None) -> ctypes.CDLL:
    """Load the Switchtec shared library.

    Args:
        path: Explicit path to the shared library. If None, searches
              standard locations.

    Returns:
        Loaded ctypes CDLL handle.

    Raises:
        LibraryLoadError: If the library cannot be found or loaded.
    """
    global _lib_instance

    if _lib_instance is not None:
        return _lib_instance

    if path is not None:
        lib_path = Path(path)
        if not lib_path.exists():
            raise LibraryLoadError(f"Library not found at: {lib_path}")
        try:
            _lib_instance = ctypes.CDLL(str(lib_path), use_errno=True)
            logger.info("switchtec_library_loaded", path=str(lib_path))
            return _lib_instance
        except OSError as exc:
            raise LibraryLoadError(
                f"Failed to load library at {lib_path}: {exc}"
            ) from exc

    candidates = _find_library_paths()
    errors: list[str] = []

    for candidate in candidates:
        if candidate.exists():
            try:
                _lib_instance = ctypes.CDLL(str(candidate), use_errno=True)
                logger.info("switchtec_library_loaded", path=str(candidate))
                return _lib_instance
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

    # Try loading by name (relies on system PATH/LD_LIBRARY_PATH)
    lib_name = "switchtec.dll" if sys.platform == "win32" else "libswitchtec.so"
    try:
        _lib_instance = ctypes.CDLL(lib_name, use_errno=True)
        logger.info("switchtec_library_loaded", path=lib_name)
        return _lib_instance
    except OSError as exc:
        errors.append(f"{lib_name}: {exc}")

    searched = "\n  ".join(str(c) for c in candidates)
    error_details = "\n  ".join(errors) if errors else "No candidates found"
    raise LibraryLoadError(
        f"Switchtec library not found. Set SWITCHTEC_LIB_DIR environment variable "
        f"or provide explicit path.\n"
        f"Searched:\n  {searched}\n"
        f"Errors:\n  {error_details}"
    )


def get_library() -> ctypes.CDLL:
    """Get the loaded Switchtec library instance.

    Returns:
        Previously loaded ctypes CDLL handle.

    Raises:
        LibraryLoadError: If the library has not been loaded yet.
    """
    if _lib_instance is None:
        raise LibraryLoadError(
            "Switchtec library not loaded. Call load_library() first."
        )
    return _lib_instance


def reset_library() -> None:
    """Reset the cached library instance. Used for testing."""
    global _lib_instance
    _lib_instance = None
