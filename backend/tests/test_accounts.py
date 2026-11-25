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



def test_csrf_guard_lets_the_apis_own_pages_write():
    # the Swagger UI is served by the API itself: same host, not a cross-site request
    own = {"content-type": "application/json", "origin": "https://qanoun-api.example", "host": "qanoun-api.example"}
    same_origin_json(_request("POST", own))
    with pytest.raises(HTTPException) as other:
        same_origin_json(_request("POST", {**own, "origin": "https://qanoun-api.example.evil.test"}))
    assert other.value.status_code == 403


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_full_account_flow(monkeypatch):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from qanoun_api import db as db_module
    from qanoun_api.main import app

    # SETTINGS was read at import: point the pool itself at the test database (setting
    # QANOUN_DB_URL here would be too late and silently use the default one).
    db_module.close_pool()
    monkeypatch.setattr(
        db_module, "SETTINGS", replace(db_module.SETTINGS, db_url=os.environ["QANOUN_TEST_DB_URL"])
    )

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


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_app_session_by_header_and_account_settings(monkeypatch):
    """The mobile app: token in the body, sent back in a header; settings follow the account."""
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from qanoun_api import db as db_module
    from qanoun_api.main import app

    db_module.close_pool()
    monkeypatch.setattr(db_module, "SETTINGS", replace(db_module.SETTINGS, db_url=os.environ["QANOUN_TEST_DB_URL"]))
    email = "app-flow@example.com"
    with TestClient(app) as client:  # no Origin header, like a native app
        from qanoun_api.db import db

        with db() as conn:
            conn.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()
        body = {"email": email, "password": "long-enough", "client": "app"}
        signed_up = client.post("/api/auth/signup", json=body)
        assert signed_up.status_code == 200 and "qanoun_session" not in signed_up.cookies
        token = signed_up.json()["token"]
        auth = {"X-Qanoun-Session": token}

        assert client.get("/api/auth/me").json()["user"] is None  # no cookie: anonymous
        assert client.get("/api/auth/me", headers=auth).json()["user"]["email"] == email
        assert client.get("/api/auth/settings", headers=auth).json() == {}
        saved = {"provider": "gemini", "style": "detailed", "ui_language": "fr", "theme": "dark"}
        assert client.put("/api/auth/settings", json=saved, headers=auth).json() == saved
        assert client.get("/api/auth/settings", headers=auth).json() == saved
        assert client.put("/api/auth/settings", json={"theme": "neon"}, headers=auth).status_code == 422
        assert client.get("/api/auth/settings").status_code == 401

        conv = {"title": "t", "updated_at": 1, "messages": [{"role": "user", "text": "q"}]}
        assert client.put("/api/conversations/m1", json=conv, headers=auth).status_code == 200
        assert [c["id"] for c in client.get("/api/conversations", headers=auth).json()] == ["m1"]

        login = client.post("/api/auth/login", json=body).json()
        assert login["token"] != token  # a second device gets its own session
        client.post("/api/auth/logout", json={}, headers=auth)
        assert client.get("/api/auth/me", headers=auth).json()["user"] is None  # this session ended
        assert client.get("/api/auth/me", headers={"X-Qanoun-Session": login["token"]}).json()["user"] is not None

        with db() as conn:
            conn.execute("DELETE FROM users WHERE email = %s", (email,))
            conn.commit()
    db_module.close_pool()
