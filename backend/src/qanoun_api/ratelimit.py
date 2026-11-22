"""Per-client rate limits for the expensive (LLM) and abusable (password) endpoints.

Counters live in Postgres (`rate_hits`, an UNLOGGED table), so every API process and every
serverless instance shares them. Fixed windows on the database clock: one atomic upsert per
request, no clock skew between instances. A burst straddling a window boundary can reach at
most twice the limit, which is acceptable for quota protection.

If the database cannot be reached the request is let through (and logged): a limiter outage
must not take the API down with it.

Client identity: `request.client.host`. Behind uvicorn's --proxy-headers (docker-compose.prod)
that is already the real client. On hosts where the app sees only the platform's proxy
(Vercel), set QANOUN_TRUST_PROXY=true to use the first X-Forwarded-For address instead. Only
do that behind a proxy that overwrites the header, or clients could pick their own key.
"""

import logging
import random

from fastapi import HTTPException, Request

from qanoun_api.config import SETTINGS
from qanoun_api.db import db

log = logging.getLogger(__name__)

_HIT_SQL = """
WITH w AS (
    SELECT to_timestamp(floor(extract(epoch FROM now()) / %(window)s) * %(window)s) AS start
)
INSERT INTO rate_hits AS r (bucket, key, window_start, count)
SELECT %(bucket)s, %(key)s, w.start, 1 FROM w
ON CONFLICT (bucket, key, window_start) DO UPDATE SET count = r.count + 1
RETURNING r.count,
          extract(epoch FROM r.window_start + make_interval(secs => %(window)s) - now())
"""

_SWEEP_SQL = "DELETE FROM rate_hits WHERE window_start < now() - make_interval(secs => %s)"


def client_key(request: Request) -> str:
    if SETTINGS.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


class RateLimit:
    def __init__(self, name: str, limit: int, window: int = 60, connect=db):
        self.name, self.limit, self.window = name, limit, window
        self._connect = connect

    def check(self, key: str) -> float | None:
        """Record a hit; return seconds to wait if over the limit, else None."""
        params = {"bucket": self.name, "key": key, "window": self.window}
        try:
            with self._connect() as conn:
                count, remaining = conn.execute(_HIT_SQL, params).fetchone()
                if random.random() < 0.01:  # forget old windows now and then
                    conn.execute(_SWEEP_SQL, (2 * self.window,))
        except Exception:
            log.warning("rate limit %s unavailable; letting the request through", self.name, exc_info=True)
            return None
        return max(float(remaining), 0.0) if count > self.limit else None

    def __call__(self, request: Request) -> None:
        wait = self.check(client_key(request))
        if wait is not None:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(wait) + 1)})


chat_limit = RateLimit("chat", limit=20)  # LLM calls cost money / quota
auth_limit = RateLimit("auth", limit=10)  # slows password guessing
