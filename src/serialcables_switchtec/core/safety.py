"""Hardware safety interlocks with rate limiting for core operations.

Provides a ``SafetyMode``-aware rate limiter that can warn, enforce, or
stay silent depending on the operational mode.  Pre-configured limiters
protect destructive operations (hard reset, error injection, port control,
loopback) from accidental rapid-fire invocation.
"""

from __future__ import annotations

import threading
import time
from enum import StrEnum

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.utils.logging import get_logger

logger = get_logger(__name__)


# ---- Safety mode ---------------------------------------------------------


class SafetyMode(StrEnum):
    """Operational safety mode for hardware interlocks.

    Attributes:
        DISABLED: All safety checks are skipped.
        WARN: Checks run but only emit log warnings.
        ENFORCE: Checks run and raise on violations.
    """

    DISABLED = "disabled"
    WARN = "warn"
    ENFORCE = "enforce"


# ---- Core rate limiter ---------------------------------------------------


class CoreRateLimiter:
    """Token-bucket rate limiter for core (non-HTTP) operations.

    Unlike the API-layer ``RateLimiter``, this class is safety-mode-aware
    and operates on a single global bucket rather than per-key buckets.

    Args:
        max_calls: Maximum number of calls allowed within *window_s*.
        window_s: Sliding window duration in seconds.
    """

    def __init__(self, max_calls: int, window_s: float) -> None:
        self._max_calls = max_calls
        self._window_s = window_s
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    @property
    def max_calls(self) -> int:
        """Maximum calls allowed per window."""
        return self._max_calls

    @property
    def window_s(self) -> float:
        """Window duration in seconds."""
        return self._window_s

    def check(self, operation: str, safety_mode: SafetyMode) -> None:
        """Check whether *operation* is within its rate limit.

        Args:
            operation: Human-readable name for logging/error messages.
            safety_mode: Current safety mode.

        Raises:
            SwitchtecError: In ``ENFORCE`` mode when the limit is exceeded.
        """
        if safety_mode == SafetyMode.DISABLED:
            return

        with self._lock:
            self._prune_old()

            if len(self._timestamps) >= self._max_calls:
                message = (
                    f"Rate limit exceeded for {operation!r}: "
                    f"max {self._max_calls} call(s) per "
                    f"{self._window_s:.0f}s window"
                )
                if safety_mode == SafetyMode.ENFORCE:
                    logger.error("rate_limit_enforced", operation=operation)
                    raise SwitchtecError(message)
                # WARN mode
                logger.warning("rate_limit_warning", operation=operation)
                return

            self._timestamps.append(time.monotonic())

    def reset(self) -> None:
        """Clear all recorded timestamps.  Useful for testing."""
        with self._lock:
            self._timestamps = []

    def _prune_old(self) -> None:
        """Remove timestamps outside the sliding window.

        Must be called while ``self._lock`` is held.
        """
        now = time.monotonic()
        self._timestamps = [
            ts for ts in self._timestamps
            if (now - ts) < self._window_s
        ]


# ---- Pre-configured safety limiters -------------------------------------

SAFETY_LIMITS: dict[str, CoreRateLimiter] = {
    "hard_reset": CoreRateLimiter(max_calls=1, window_s=60.0),
    "error_injection": CoreRateLimiter(max_calls=10, window_s=60.0),
    "port_control": CoreRateLimiter(max_calls=5, window_s=60.0),
    "loopback": CoreRateLimiter(max_calls=3, window_s=60.0),
}


# ---- Convenience validators ----------------------------------------------


def validate_injection_rate(
    port_id: int,
    injection_type: str,
    safety_mode: SafetyMode,
) -> None:
    """Validate that an error-injection call is within its rate limit.

    Args:
        port_id: Physical port targeted by the injection.
        injection_type: Kind of injection (e.g. ``"dllp_crc"``).
        safety_mode: Current safety mode.

    Raises:
        SwitchtecError: In ``ENFORCE`` mode when the limit is exceeded.
    """
    limiter = SAFETY_LIMITS["error_injection"]
    operation = f"error_injection:{injection_type}:port_{port_id}"
    limiter.check(operation, safety_mode)
    logger.debug(
        "injection_validated",
        port_id=port_id,
        injection_type=injection_type,
        safety_mode=str(safety_mode),
    )


def validate_hard_reset(safety_mode: SafetyMode) -> None:
    """Validate that a hard-reset call is within its rate limit.

    Args:
        safety_mode: Current safety mode.

    Raises:
        SwitchtecError: In ``ENFORCE`` mode when the limit is exceeded.
    """
    limiter = SAFETY_LIMITS["hard_reset"]
    limiter.check("hard_reset", safety_mode)
    logger.debug("hard_reset_validated", safety_mode=str(safety_mode))


def validate_port_control(
    port_id: int,
    safety_mode: SafetyMode,
) -> None:
    """Validate that a port-control call is within its rate limit.

    Args:
        port_id: Physical port being controlled.
        safety_mode: Current safety mode.

    Raises:
        SwitchtecError: In ``ENFORCE`` mode when the limit is exceeded.
    """
    limiter = SAFETY_LIMITS["port_control"]
    operation = f"port_control:port_{port_id}"
    limiter.check(operation, safety_mode)
    logger.debug(
        "port_control_validated",
        port_id=port_id,
        safety_mode=str(safety_mode),
    )


def validate_loopback(
    port_id: int,
    safety_mode: SafetyMode,
) -> None:
    """Validate that a loopback-control call is within its rate limit.

    Args:
        port_id: Physical port for loopback configuration.
        safety_mode: Current safety mode.

    Raises:
        SwitchtecError: In ``ENFORCE`` mode when the limit is exceeded.
    """
    limiter = SAFETY_LIMITS["loopback"]
    operation = f"loopback:port_{port_id}"
    limiter.check(operation, safety_mode)
    logger.debug(
        "loopback_validated",
        port_id=port_id,
        safety_mode=str(safety_mode),
    )


def reset_all_limits() -> None:
    """Reset every safety limiter.  Intended for test teardown only."""
    for limiter in SAFETY_LIMITS.values():
        limiter.reset()
