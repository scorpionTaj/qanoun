"""Per-IP rate limits for the expensive (LLM) and abusable (password) endpoints.

In-memory sliding window: correct for the single API process the compose stack runs.
Several API replicas would each count separately — put the limit in the reverse proxy then.
Behind a proxy, start uvicorn with --proxy-headers so request.client is the real client.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimit:
    def __init__(self, name: str, limit: int, window: float = 60.0):
        self.name, self.limit, self.window = name, limit, window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float | None:
        """Record a hit; return seconds to wait if over the limit, else None."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return hits[0] + self.window - now
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle clients so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
            return None

    def __call__(self, request: Request) -> None:
        wait = self.check(request.client.host if request.client else "unknown")
        if wait is not None:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(wait) + 1)})


chat_limit = RateLimit("chat", limit=20)  # LLM calls cost money / quota
auth_limit = RateLimit("auth", limit=10)  # slows password guessing
