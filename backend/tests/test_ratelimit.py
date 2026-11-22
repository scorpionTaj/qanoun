"""Rate limits: decision logic offline; the shared counter SQL against a real Postgres when
QANOUN_TEST_DB_URL is set (migrations applied by the test)."""

import os
from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from qanoun_api import ratelimit
from qanoun_api.ratelimit import RateLimit, client_key


class FakeCounter:
    """Plays rate_hits: counts per key inside one window that has `remaining` seconds left."""

    def __init__(self, remaining: float = 42.0):
        self.counts: dict[tuple, int] = {}
        self.remaining = remaining

    def execute(self, sql, params=None):
        counter = self

        class Result:
            def fetchone(self):
                k = (params["bucket"], params["key"])
                counter.counts[k] = counter.counts.get(k, 0) + 1
                return counter.counts[k], counter.remaining

        return Result()


def _connect_to(conn):
    @contextmanager
    def connect():
        yield conn

    return connect


def _request(ip="1.2.3.4", headers=None):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (ip, 1234)})


def test_blocks_over_the_limit_per_key_and_bucket():
    limit = RateLimit("t", limit=2, connect=_connect_to(FakeCounter(remaining=42.0)))
    assert limit.check("ip") is None
    assert limit.check("ip") is None
    assert limit.check("ip") == 42.0  # third hit: wait until the window ends
    assert limit.check("other") is None  # per client


def test_raises_429_with_retry_after():
    limit = RateLimit("t", limit=0, connect=_connect_to(FakeCounter(remaining=7.2)))
    with pytest.raises(HTTPException) as exc:
        limit(_request())
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "8"


def test_fails_open_when_the_database_is_down():
    @contextmanager
    def broken():
        raise OSError("connection refused")
        yield

    assert RateLimit("t", limit=0, connect=broken).check("ip") is None


def test_client_key_trusts_forwarded_for_only_when_configured(monkeypatch):
    req = _request("10.0.0.1", {"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    settings = type(ratelimit.SETTINGS)
    monkeypatch.setattr(ratelimit, "SETTINGS", settings(trust_proxy=False))
    assert client_key(req) == "10.0.0.1"  # spoofable header ignored by default
    monkeypatch.setattr(ratelimit, "SETTINGS", settings(trust_proxy=True))
    assert client_key(req) == "203.0.113.9"
    assert client_key(_request("10.0.0.1")) == "10.0.0.1"  # no header: fall back


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_counts_are_shared_in_postgres():
    import uuid

    import psycopg
    from qanoun_pipeline.schema import migrate

    url = os.environ["QANOUN_TEST_DB_URL"]
    with psycopg.connect(url) as conn:
        migrate(conn)

    @contextmanager
    def connect():  # a fresh connection per hit, like separate serverless instances
        with psycopg.connect(url) as conn:
            yield conn

    bucket = f"test-{uuid.uuid4().hex[:8]}"
    a = RateLimit(bucket, limit=2, window=60, connect=connect)
    b = RateLimit(bucket, limit=2, window=60, connect=connect)
    assert a.check("ip") is None
    assert b.check("ip") is None  # second instance sees the first one's hit
    wait = a.check("ip")
    assert wait is not None and 0 <= wait <= 60
    assert b.check("other-ip") is None
    with psycopg.connect(url) as conn:
        conn.execute("DELETE FROM rate_hits WHERE bucket = %s", (bucket,))
