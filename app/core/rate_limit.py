"""Simple in-memory rate limiting utilities."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, DefaultDict


class RateLimiter:
    """Provide in-memory rate limiting with asyncio locking."""

    def __init__(self) -> None:
        self._attempts: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Return True when the request should be allowed for the key."""
        async with self._lock:
            now = time.time()
            window_start = now - window_seconds
            bucket = self._attempts[key]

            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= max_requests:
                return False

            bucket.append(now)
            return True


rate_limiter = RateLimiter()
