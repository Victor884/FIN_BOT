import asyncio
from collections import defaultdict, deque
from time import monotonic


class InMemoryRateLimiter:
    def __init__(self, requests: int, window_seconds: int = 60) -> None:
        self._requests = max(requests, 1)
        self._window_seconds = window_seconds
        self._entries: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self._window_seconds
        async with self._lock:
            entries = self._entries[key]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self._requests:
                return False
            entries.append(now)
            return True
