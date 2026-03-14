"""Simple in-memory rate limiting utilities.

WARNING: This implementation is process-local. In deployments with multiple
workers or processes (e.g. ``uvicorn --workers N`` or multiple container
replicas) each worker maintains its own counter, so the effective rate limit
is multiplied by the number of workers.

For production multi-worker deployments replace this with a shared backend
(e.g. Redis via ``redis-py`` / ``aioredis``) so all workers share the same
counters.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, DefaultDict


class RateLimiter:
    """Provide in-memory rate limiting with asyncio locking.

    .. warning::
        State is not shared across processes/workers. See module docstring.
    """

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
