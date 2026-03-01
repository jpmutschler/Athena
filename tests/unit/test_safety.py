"""Tests for safety interlocks: rate limiting, validation, and safety modes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from serialcables_switchtec.core.safety import (
    CoreRateLimiter,
    SAFETY_LIMITS,
    SafetyMode,
    reset_all_limits,
    validate_hard_reset,
    validate_injection_rate,
    validate_loopback,
    validate_port_control,
)
from serialcables_switchtec.exceptions import SwitchtecError


# ---------------------------------------------------------------------------
# SafetyMode enum
# ---------------------------------------------------------------------------


class TestSafetyMode:
    """Tests for the SafetyMode enumeration values."""

    def test_safety_mode_values(self):
        assert SafetyMode.DISABLED == "disabled"
        assert SafetyMode.WARN == "warn"
        assert SafetyMode.ENFORCE == "enforce"

    def test_safety_mode_is_str_enum(self):
        assert isinstance(SafetyMode.DISABLED, str)
        assert isinstance(SafetyMode.WARN, str)
        assert isinstance(SafetyMode.ENFORCE, str)


# ---------------------------------------------------------------------------
# CoreRateLimiter
# ---------------------------------------------------------------------------


class TestCoreRateLimiter:
    """Tests for the CoreRateLimiter class."""

    def test_rate_limiter_allows_within_limit(self):
        limiter = CoreRateLimiter(max_calls=5, window_s=60.0)
        for _ in range(5):
            limiter.check("test_op", SafetyMode.ENFORCE)

    def test_rate_limiter_blocks_over_limit_enforce(self):
        limiter = CoreRateLimiter(max_calls=3, window_s=60.0)
        for _ in range(3):
            limiter.check("test_op", SafetyMode.ENFORCE)
        with pytest.raises(SwitchtecError):
            limiter.check("test_op", SafetyMode.ENFORCE)

    def test_rate_limiter_warns_over_limit_warn(self):
        limiter = CoreRateLimiter(max_calls=2, window_s=60.0)
        for _ in range(2):
            limiter.check("test_op", SafetyMode.WARN)
        # Should not raise in WARN mode, just logs a warning
        limiter.check("test_op", SafetyMode.WARN)

    def test_rate_limiter_disabled_no_check(self):
        limiter = CoreRateLimiter(max_calls=1, window_s=60.0)
        limiter.check("test_op", SafetyMode.DISABLED)
        # Even exceeding the limit should not raise
        limiter.check("test_op", SafetyMode.DISABLED)
        limiter.check("test_op", SafetyMode.DISABLED)

    def test_rate_limiter_properties(self):
        limiter = CoreRateLimiter(max_calls=7, window_s=30.0)
        assert limiter.max_calls == 7
        assert limiter.window_s == 30.0

    def test_rate_limiter_reset(self):
        limiter = CoreRateLimiter(max_calls=2, window_s=60.0)
        limiter.check("test_op", SafetyMode.ENFORCE)
        limiter.check("test_op", SafetyMode.ENFORCE)
        # At limit -- next call would fail
        limiter.reset()
        # After reset, calls should succeed again
        limiter.check("test_op", SafetyMode.ENFORCE)

    @patch("serialcables_switchtec.core.safety.time")
    def test_rate_limiter_window_expiry(self, mock_time):
        """After the window expires, the rate limit counter resets.

        Each successful check() calls time.monotonic() twice: once inside
        _prune_old() and once when appending the timestamp.  When the
        rate limit is exceeded in ENFORCE mode, only _prune_old() is called.
        """
        mock_time.monotonic.side_effect = [
            # Call 1 (succeeds): _prune_old + append
            100.0, 100.0,
            # Call 2 (succeeds): _prune_old + append
            100.0, 100.0,
            # Call 3 (succeeds): _prune_old + append
            100.0, 100.0,
            # Call 4 (after window expiry): _prune_old prunes all, then append
            200.0, 200.0,
        ]
        limiter = CoreRateLimiter(max_calls=3, window_s=60.0)
        for _ in range(3):
            limiter.check("test_op", SafetyMode.ENFORCE)
        # After window expiry, the counter should have been pruned
        limiter.check("test_op", SafetyMode.ENFORCE)


# ---------------------------------------------------------------------------
# SAFETY_LIMITS dict
# ---------------------------------------------------------------------------


class TestSafetyLimits:
    """Tests for the SAFETY_LIMITS configuration dict."""

    def test_safety_limits_has_expected_keys(self):
        expected_keys = {"hard_reset", "error_injection", "port_control", "loopback"}
        assert set(SAFETY_LIMITS.keys()) == expected_keys

    def test_safety_limits_values_are_limiters(self):
        for key, value in SAFETY_LIMITS.items():
            assert isinstance(value, CoreRateLimiter), (
                f"SAFETY_LIMITS[{key!r}] is not a CoreRateLimiter"
            )


# ---------------------------------------------------------------------------
# validate_injection_rate
# ---------------------------------------------------------------------------


class TestValidateInjectionRate:
    """Tests for the validate_injection_rate() function."""

    def test_validate_injection_rate_enforce_blocks(self):
        """Exceeding injection rate in ENFORCE mode raises SwitchtecError."""
        with pytest.raises(SwitchtecError):
            for _ in range(1000):
                validate_injection_rate(
                    port_id=0,
                    injection_type="dllp_crc",
                    safety_mode=SafetyMode.ENFORCE,
                )

    def test_validate_injection_rate_disabled_allows(self):
        """DISABLED mode never raises regardless of call count."""
        for _ in range(100):
            validate_injection_rate(
                port_id=0,
                injection_type="dllp_crc",
                safety_mode=SafetyMode.DISABLED,
            )


# ---------------------------------------------------------------------------
# validate_hard_reset
# ---------------------------------------------------------------------------


class TestValidateHardReset:
    """Tests for the validate_hard_reset() function."""

    def test_validate_hard_reset_enforce_blocks_second_call(self):
        """Two hard_reset calls within the window raises on the second."""
        validate_hard_reset(safety_mode=SafetyMode.ENFORCE)
        with pytest.raises(SwitchtecError):
            validate_hard_reset(safety_mode=SafetyMode.ENFORCE)

    def test_validate_hard_reset_disabled_allows(self):
        """DISABLED mode allows repeated hard resets."""
        for _ in range(5):
            validate_hard_reset(safety_mode=SafetyMode.DISABLED)


# ---------------------------------------------------------------------------
# validate_port_control and validate_loopback
# ---------------------------------------------------------------------------


class TestValidatePortControl:
    """Tests for the validate_port_control() function."""

    def test_validate_port_control_disabled_allows(self):
        for _ in range(50):
            validate_port_control(port_id=0, safety_mode=SafetyMode.DISABLED)


class TestValidateLoopback:
    """Tests for the validate_loopback() function."""

    def test_validate_loopback_disabled_allows(self):
        for _ in range(50):
            validate_loopback(port_id=0, safety_mode=SafetyMode.DISABLED)


# ---------------------------------------------------------------------------
# reset_all_limits
# ---------------------------------------------------------------------------


class TestResetAllLimits:
    """Tests for the reset_all_limits() convenience function."""

    def test_reset_all_limits_clears_state(self):
        """After reset_all_limits, previously exhausted limiters accept calls."""
        # First, ensure a clean slate for this test
        reset_all_limits()
        validate_hard_reset(safety_mode=SafetyMode.ENFORCE)
        # hard_reset limiter is now at its max (1 call per 60s)
        reset_all_limits()
        # Should succeed after reset
        validate_hard_reset(safety_mode=SafetyMode.ENFORCE)
