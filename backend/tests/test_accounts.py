"""Accounts: password hashing, CSRF guard (offline), and the full flow against a live DB.

    QANOUN_TEST_DB_URL=postgresql://qanoun:qanoun@localhost:5433/qanoun \\
        uv run --project backend pytest backend/tests/test_accounts.py
"""

import os

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from qanoun_api import accounts
from qanoun_api.routers.auth import same_origin_json


def test_password_hash_roundtrip_and_salting():
    stored = accounts.hash_password("correct horse battery")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert accounts.verify_password("correct horse battery", stored)
    assert not accounts.verify_password("wrong", stored)
    assert accounts.hash_password("correct horse battery") != stored  # random salt
    assert not accounts.verify_password("x", "garbage")


def _request(method: str, headers: dict) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": method, "headers": raw})


def test_csrf_guard_requires_json_from_allowed_origin():
    same_origin_json(_request("GET", {}))  # reads are never blocked
    same_origin_json(_request("POST", {"content-type": "application/json", "origin": "http://localhost:3000"}))
    with pytest.raises(HTTPException) as form:
        same_origin_json(_request("POST", {"content-type": "application/x-www-form-urlencoded"}))
    assert form.value.status_code == 415
    with pytest.raises(HTTPException) as foreign:
        same_origin_json(_request("POST", {"content-type": "application/json", "origin": "https://evil.example"}))
    assert foreign.value.status_code == 403


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_full_account_flow(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("QANOUN_DB_URL", os.environ["QANOUN_TEST_DB_URL"])
    from qanoun_api.main import app

    email = "flow-test@example.com"
    client = TestClient(app, headers={"origin": "http://localhost:3000"})
    with client:
        from qanoun_api.db import db

        with db() as conn:
            conn.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()

        assert client.get("/api/auth/me").json()["user"] is None
        assert client.post("/api/auth/signup", json={"email": email, "password": "long-enough"}).status_code == 200
        assert client.get("/api/auth/me").json()["user"]["email"] == email
        assert client.post("/api/auth/signup", json={"email": email, "password": "long-enough"}).status_code == 409

        conv = {"title": "t", "updated_at": 2, "messages": [{"role": "user", "text": "q"}]}
        assert client.put("/api/conversations/c1", json=conv).status_code == 200
        older = {**conv, "title": "stale", "updated_at": 1}
        client.put("/api/conversations/c1", json=older)  # last write wins: ignored
        assert client.get("/api/conversations").json()[0]["title"] == "t"

        client.post("/api/auth/logout", json={})
        assert client.get("/api/conversations").status_code == 401
        assert client.post("/api/auth/login", json={"email": email, "password": "nope-nope"}).status_code == 401
        assert client.post("/api/auth/login", json={"email": email, "password": "long-enough"}).status_code == 200

        with db() as conn:
            conn.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()
