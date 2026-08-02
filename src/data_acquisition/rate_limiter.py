"""NCBI-compliant request rate limiter.

NCBI's usage policy allows 3 requests/second without an API key and 10/second
with one. :class:`RateLimiter` enforces this with a sliding-window token
bucket: it records the timestamps of recent requests and blocks in
:meth:`wait` until firing another would not exceed the per-second budget.

If ``requests_per_second`` is not given, the limit is auto-detected from the
presence of the ``NCBI_API_KEY`` environment variable (10 if set, else 3).
"""

from __future__ import annotations

import collections
import os
import threading
import time


class RateLimiter:
    """Sliding-window limiter: at most ``requests_per_second`` per rolling second."""

    def __init__(self, requests_per_second: float | None = None):
        if requests_per_second is None:
            requests_per_second = 10.0 if os.environ.get("NCBI_API_KEY") else 3.0
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self.requests_per_second = float(requests_per_second)
        self._window = 1.0  # seconds
        self._times: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until issuing one more request stays within the rate limit.

        The sleep happens OUTSIDE the lock. Holding it across time.sleep() made
        every other thread block on the mutex rather than on the rate limit, so
        a limiter shared between threads serialised them through the sleep even
        when the window had room. Re-checking in a loop keeps the budget exact:
        another thread may have consumed the slot we woke up for.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                self._evict(now)
                if len(self._times) < self.requests_per_second:
                    self._times.append(now)
                    return
                sleep_for = self._window - (now - self._times[0])
            if sleep_for > 0:
                time.sleep(sleep_for)

    def _evict(self, now: float) -> None:
        while self._times and now - self._times[0] >= self._window:
            self._times.popleft()
