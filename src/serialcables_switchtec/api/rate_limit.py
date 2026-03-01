"""Simple in-process rate limiter for destructive API endpoints."""

from __future__ import annotations

import time
import threading
from collections import defaultdict

from fastapi import HTTPException


class RateLimiter:
    """Token-bucket rate limiter keyed by an arbitrary string (e.g. device ID).

    Each *key* gets an independent sliding-window counter.  When the
    number of calls within ``period`` seconds reaches ``calls``, any
    further attempt raises ``HTTPException(429)``.

    Thread-safe: all bucket mutations are guarded by a lock.
    """

    def __init__(self, calls: int, period: float) -> None:
        self._calls = calls
        self._period = period
        self._lock = threading.Lock()
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def reset(self) -> None:
        """Clear all tracked buckets.  Useful for testing."""
        with self._lock:
            self._buckets.clear()

    def check(self, key: str) -> None:
        """Raise HTTPException(429) if the rate limit for *key* is exceeded."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            # Prune expired entries
            self._buckets[key] = [t for t in bucket if now - t < self._period]
            bucket = self._buckets[key]
            if len(bucket) >= self._calls:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                )
            bucket.append(now)


# Pre-configured limiters --------------------------------------------------

hard_reset_limiter = RateLimiter(calls=1, period=60.0)        # 1 per minute
injection_limiter = RateLimiter(calls=10, period=60.0)        # 10 per minute
fabric_control_limiter = RateLimiter(calls=5, period=60.0)    # 5 per minute
mrpc_limiter = RateLimiter(calls=10, period=60.0)             # 10 per minute
csr_write_limiter = RateLimiter(calls=5, period=60.0)         # 5 per minute
