"""Custom Hatchling build hook for platform-tagged wheels.

Forces non-pure-Python wheel tags so that the resulting wheel is
platform-specific (e.g., cp310-win_amd64, cp310-manylinux_x86_64).
Native shared libraries placed in src/serialcables_switchtec/_native/
by the CI build step are automatically included via the ``artifacts``
configuration in pyproject.toml.
"""

from __future__ import annotations

import sys
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Mark the wheel as platform-specific so it gets correct tags."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Setting pure_python to False makes Hatch generate a platform-
        # tagged wheel (e.g. cp310-cp310-win_amd64.whl) instead of a
        # universal py3-none-any.whl.
        build_data["pure_python"] = False

        # Use stable ABI tag so a single wheel works across Python
        # versions on the same platform. The shared library is loaded
        # via ctypes (not the Python C API), so ABI compatibility is
        # not a concern.
        build_data["tag"] = f"py3-none-{_platform_tag()}"


def _platform_tag() -> str:
    """Return the platform tag for the current build environment."""
    import platform

    machine = platform.machine().lower()

    if sys.platform == "win32":
        if machine in ("amd64", "x86_64"):
            return "win_amd64"
        if machine == "arm64":
            return "win_arm64"
        raise RuntimeError(f"Unsupported Windows architecture: {machine}")

    if sys.platform == "linux":
        # auditwheel repair in CI will fix the manylinux version tag.
        if machine == "x86_64":
            return "manylinux_2_17_x86_64"
        if machine == "aarch64":
            return "manylinux_2_17_aarch64"
        raise RuntimeError(f"Unsupported Linux architecture: {machine}")

    if sys.platform == "darwin":
        if machine == "arm64":
            return "macosx_11_0_arm64"
        if machine == "x86_64":
            return "macosx_11_0_x86_64"
        raise RuntimeError(f"Unsupported macOS architecture: {machine}")

    raise RuntimeError(
        f"Unsupported platform: {sys.platform}. "
        f"Cannot determine wheel platform tag."
    )
