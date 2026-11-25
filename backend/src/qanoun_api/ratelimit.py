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

API keys (`Authorization: Bearer qk_…`, created on the Settings page): a valid key is counted
per owner instead of per address, with the limiter's `key_limit`; all of a user's keys share
one count, so more keys do not mean more quota. An unknown or revoked key is refused (401)
rather than silently counted as anonymous, so a client learns its key stopped working.
"""

import logging
import random
from typing import Annotated

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from qanoun_api import accounts
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


# Declares the key in the OpenAPI schema, so the Swagger UI shows «Authorize» and sends it.
# Optional (auto_error=False): without a key, requests are counted by address.
api_key = HTTPBearer(
    auto_error=False,
    scheme_name="APIKey",
    bearerFormat="qk_…",
    description="Optional API key (Settings page of the web app): higher limits per account.",
)


def bearer_key(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


class RateLimit:
    def __init__(self, name: str, limit: int, window: int = 60, key_limit: int | None = None, connect=db):
        self.name, self.limit, self.window = name, limit, window
        self.key_limit = limit if key_limit is None else key_limit
        self._connect = connect

    def check(self, key: str, limit: int | None = None) -> float | None:
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
        return max(float(remaining), 0.0) if count > (self.limit if limit is None else limit) else None

    def identity(self, request: Request) -> tuple[str, int]:
        """(counter key, limit) for this request: the key's owner, or the client address."""
        token = bearer_key(request)
        if token is None:
            return client_key(request), self.limit
        try:
            with self._connect() as conn:
                owner = accounts.api_key_owner(conn, token)
        except Exception:
            log.warning("API key check unavailable; counting the request by address", exc_info=True)
            return client_key(request), self.limit
        if owner is None:
            raise HTTPException(401, "invalid or revoked API key", headers={"WWW-Authenticate": "Bearer"})
        return f"user:{owner}", self.key_limit

    def __call__(self, request: Request, _: Annotated[HTTPAuthorizationCredentials | None, Security(api_key)] = None) -> None:
        key, limit = self.identity(request)  # reads the header itself: /mcp has no FastAPI dependencies
        wait = self.check(key, limit)
        if wait is not None:
            raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(wait) + 1)})


chat_limit = RateLimit("chat", limit=20)  # LLM calls cost money / quota (keys: same, per owner)
search_limit = RateLimit("search", limit=30, key_limit=120)  # each search embeds the query
mcp_limit = RateLimit("mcp", limit=60, key_limit=240)  # per MCP request (an agent sends several)
auth_limit = RateLimit("auth", limit=10)  # slows password guessing
