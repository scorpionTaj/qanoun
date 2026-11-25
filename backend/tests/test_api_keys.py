"""API keys end to end against a live database: create, list, use, cap, revoke.

    QANOUN_TEST_DB_URL=postgresql://qanoun:qanoun@localhost:5433/qanoun \\
        uv run --project backend pytest backend/tests/test_api_keys.py
"""

import os
from dataclasses import replace

import pytest

from qanoun_api.rag.retrieval import RetrievalResult

pytestmark = pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")

EMAILS = ("keys-a@example.com", "keys-b@example.com")
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}
JSON = {"content-type": "application/json"}  # the CSRF guard wants it on every write


@pytest.fixture
def app_client(monkeypatch):
    from fastapi.testclient import TestClient

    from qanoun_api import db as db_module
    from qanoun_api import ratelimit
    from qanoun_api.main import app
    from qanoun_api.routers import search

    db_module.close_pool()
    monkeypatch.setattr(db_module, "SETTINGS", replace(db_module.SETTINGS, db_url=os.environ["QANOUN_TEST_DB_URL"]))
    # The real limiters (the key check is under test), with the counter left out.
    for limiter in (ratelimit.search_limit, ratelimit.mcp_limit, ratelimit.auth_limit):
        monkeypatch.setattr(limiter, "check", lambda key, limit=None: None)
    monkeypatch.setattr(search.retrieval, "search", lambda q, **kw: RetrievalResult(query=q, search_query=q))

    with TestClient(app, headers={"origin": "http://localhost:3000"}) as client:
        from qanoun_api.db import db

        def cleanup():
            with db() as conn:
                conn.execute("DELETE FROM users WHERE email = ANY(%s)", (list(EMAILS),))
                conn.commit()

        cleanup()
        yield client
        cleanup()
    db_module.close_pool()


def _sign_up(client, email):
    client.cookies.clear()
    assert client.post("/api/auth/signup", json={"email": email, "password": "long-enough"}).status_code == 200


def test_api_key_lifecycle(app_client):
    client = app_client
    assert client.get("/api/keys").status_code == 401  # signed-in users only

    _sign_up(client, EMAILS[0])
    created = client.post("/api/keys", json={"name": "my script"})
    assert created.status_code == 201
    key = created.json()["key"]
    assert key.startswith("qk_") and len(key) > 40
    listed = client.get("/api/keys").json()
    assert [(k["name"], k["prefix"], k["last_used_at"]) for k in listed] == [("my script", key[:7], None)]
    assert "key" not in listed[0]  # shown once, never again

    # Using it: a cookie-less client, like a script.
    client.cookies.clear()
    bearer = {"Authorization": f"Bearer {key}"}
    assert client.post("/api/search", json={"q": "الزواج"}, headers=bearer).status_code == 200
    assert client.post("/api/search", json={"q": "x"}, headers={"Authorization": "Bearer qk_forged"}).status_code == 401
    assert client.post("/api/search", json={"q": "x"}).status_code == 200  # anonymous still works

    # Another user can neither see nor revoke it.
    _sign_up(client, EMAILS[1])
    assert client.get("/api/keys").json() == []
    assert client.delete(f"/api/keys/{listed[0]['id']}", headers=JSON).status_code == 404

    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": EMAILS[0], "password": "long-enough"}).status_code == 200
    assert client.get("/api/keys").json()[0]["last_used_at"] is not None
    assert client.delete(f"/api/keys/{listed[0]['id']}", headers=JSON).status_code == 204
    assert client.get("/api/keys").json() == []

    client.cookies.clear()
    assert client.post("/api/search", json={"q": "x"}, headers=bearer).status_code == 401  # revoked
    mcp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={**MCP_HEADERS, **bearer})
    assert mcp.status_code == 401 and mcp.json()["detail"] == "invalid or revoked API key"


def test_active_keys_are_capped(app_client):
    from qanoun_api.accounts import MAX_KEYS

    _sign_up(app_client, EMAILS[0])
    ids = [app_client.post("/api/keys", json={"name": f"k{i}"}).json()["id"] for i in range(MAX_KEYS)]
    assert app_client.post("/api/keys", json={"name": "one too many"}).status_code == 409
    app_client.delete(f"/api/keys/{ids[0]}", headers=JSON)
    assert app_client.post("/api/keys", json={"name": "after revoking"}).status_code == 201
