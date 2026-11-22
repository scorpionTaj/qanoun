"""Query log: what a record keeps, privacy defaults, failure isolation, and (with
QANOUN_TEST_DB_URL) the insert and the admin usage SQL against a real Postgres."""

import os
from contextlib import contextmanager

import anyio
import pytest
from conftest import make_hit
from fastapi.testclient import TestClient

from qanoun_api import querylog
from qanoun_api.main import app
from qanoun_api.querylog import QueryRecord
from qanoun_api.querylog import write as real_write  # bound before the autouse capture
from qanoun_api.rag import retrieval
from qanoun_api.rag.retrieval import RetrievalResult
from qanoun_api.routers import analytics
from qanoun_api.routers import chat as chat_router
from qanoun_api.routers.auth import current_user


def test_record_follows_the_events_of_an_answer():
    record = QueryRecord("ما هي شروط الزواج؟", scope_domain="family")
    record.observe("meta", {"variety": "msa"})
    record.observe("sources", {"sources": [{"article_id": 7}, {"article_id": 9}]})
    record.observe("model", {"provider": "gemini", "model": "flash"})
    record.observe("done", {"abstained": False, "cited": [0], "timings": {"rewrite": 1, "search": 20, "answer": 900}})
    row = record.row()
    assert row["outcome"] == "answered" and row["variety"] == "msa"
    assert row["source_article_ids"] == [7, 9] and row["cited"] == [0]
    assert (row["provider"], row["model"]) == ("gemini", "flash")
    assert (row["rewrite_ms"], row["search_ms"], row["answer_ms"]) == (1, 20, 900)
    assert row["scope_domain"] == "family"


def test_record_outcomes_error_abstained_and_disconnected():
    err = QueryRecord("q")
    err.observe("error", {"code": "rate_limit", "message": "…"})
    assert (err.row()["outcome"], err.row()["error_code"]) == ("error", "rate_limit")
    abst = QueryRecord("q")
    abst.observe("done", {"abstained": True, "cited": []})
    assert abst.row()["outcome"] == "abstained"
    assert QueryRecord("q").row()["outcome"] == "disconnected"  # no final event seen


def test_question_text_is_kept_only_when_enabled(monkeypatch):
    settings = type(querylog.SETTINGS)
    monkeypatch.setattr(querylog, "SETTINGS", settings(log_questions=False))
    row = QueryRecord("سؤال").row()
    assert row["question"] is None and len(row["question_hash"]) == 64
    monkeypatch.setattr(querylog, "SETTINGS", settings(log_questions=True))
    assert QueryRecord("سؤال").row()["question"] == "سؤال"


def test_hash_counts_the_same_question_however_it_is_spelled():
    # diacritics and alef forms fold to the same normalized text
    assert QueryRecord("ما هي شُروط الزواج").row()["question_hash"] == QueryRecord("ما هي شروط الزواج").row()["question_hash"]


def test_write_never_raises():
    @contextmanager
    def broken():
        raise OSError("db down")
        yield

    real_write(QueryRecord("q"), connect=broken)  # logged, not raised


# ── through the chat endpoint (the autouse `query_log` fixture captures records) ──────────

def test_chat_logs_one_record_per_request(monkeypatch, fake_llm, query_log):
    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(fake_llm, None)
    TestClient(app).post("/api/chat", json={"question": "ما هي شروط الزواج؟", "domain": "family"})
    assert len(query_log) == 1
    row = query_log[0].row()
    assert row["outcome"] == "answered" and row["variety"] == "msa" and row["scope_domain"] == "family"
    assert row["source_article_ids"] == [1] and row["cited"] == [0]
    assert row["total_ms"] >= 0


def test_chat_logs_retrieval_errors(monkeypatch, fake_llm, query_log):
    def boom(*a, **kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(retrieval, "search", boom)
    chat_router.set_llm(fake_llm, None)
    TestClient(app).post("/api/chat", json={"question": "سؤال"})
    assert (query_log[0].row()["outcome"], query_log[0].row()["error_code"]) == ("error", "retrieval")


def test_chat_logs_a_client_that_goes_away(monkeypatch, fake_llm, query_log):
    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(fake_llm, None)

    async def hang_up_after_two_events():
        stream = chat_router._logged_stream(chat_router.ChatRequest(question="سؤال"))
        await anext(stream), await anext(stream)  # status, meta… then the browser tab closes
        await stream.aclose()

    anyio.run(hang_up_after_two_events)
    assert len(query_log) == 1 and query_log[0].row()["outcome"] == "disconnected"


def test_chat_logs_when_the_response_task_is_cancelled(monkeypatch, fake_llm, query_log):
    """What Starlette does on a disconnect: cancel the task while it waits on the stream."""
    import threading

    release = threading.Event()

    def slow_search(*a, **kw):
        release.wait(5)
        return RetrievalResult("q", "q", [make_hit()])

    monkeypatch.setattr(retrieval, "search", slow_search)
    chat_router.set_llm(fake_llm, None)

    async def consume_then_cancel():
        async with anyio.create_task_group() as tg:
            async def consume():
                async for _ in chat_router._logged_stream(chat_router.ChatRequest(question="سؤال")):
                    pass

            tg.start_soon(consume)
            await anyio.sleep(0.2)  # stuck in the search
            tg.cancel_scope.cancel()
            release.set()  # cancelling waits for the worker thread's current step to finish

    anyio.run(consume_then_cancel)
    assert len(query_log) == 1 and query_log[0].row()["outcome"] == "disconnected"


# ── admin usage endpoint ─────────────────────────────────────────────────────────────────

def test_usage_requires_an_admin():
    client = TestClient(app)
    app.dependency_overrides[current_user] = lambda: None
    try:
        assert client.get("/api/analytics/usage").status_code == 401
        app.dependency_overrides[current_user] = lambda: {"id": 2, "email": "u@x.ma", "is_admin": False}
        assert client.get("/api/analytics/usage").status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_write_and_usage_on_a_real_database(monkeypatch):
    import uuid

    import psycopg
    from qanoun_pipeline.schema import migrate

    url = os.environ["QANOUN_TEST_DB_URL"]
    with psycopg.connect(url) as conn:
        migrate(conn)
        conn.execute("DELETE FROM query_log")

    @contextmanager
    def connect():
        with psycopg.connect(url) as conn:
            yield conn

    tag = uuid.uuid4().hex[:6]
    for outcome_events in (
        [("meta", {"variety": "darija"}), ("done", {"abstained": True, "cited": []})],
        [("meta", {"variety": "darija"}), ("done", {"abstained": True, "cited": []})],
        [("meta", {"variety": "msa"}), ("model", {"provider": "gemini", "model": "m"}),
         ("done", {"abstained": False, "cited": [0]})],
        [("error", {"code": "rate_limit"})],
    ):
        record = QueryRecord(f"question {tag} {outcome_events[0][0]}")
        for event, data in outcome_events:
            record.observe(event, data)
        real_write(record, connect=connect)

    monkeypatch.setattr(analytics, "db", connect)
    app.dependency_overrides[current_user] = lambda: {"id": 1, "email": "a@x.ma", "is_admin": True}
    try:
        body = TestClient(app).get("/api/analytics/usage?days=1").json()
    finally:
        app.dependency_overrides.clear()
    assert body["questions"] == 4
    assert body["outcomes"] == {"answered": 1, "abstained": 2, "error": 1, "disconnected": 0}
    assert body["abstention_rate"] == round(2 / 3, 3) and body["error_rate"] == 0.25
    assert body["latency_ms"]["p50"] is not None
    assert {"key": "darija", "questions": 2, "abstained": 2, "errors": 0} in body["by_variety"]
    assert body["by_error"] == [{"key": "rate_limit", "questions": 1, "abstained": 0, "errors": 1}]
    assert body["top_abstained"][0] == {"question": None, "variety": "darija", "count": 2}
    with psycopg.connect(url) as conn:
        conn.execute("DELETE FROM query_log")


def test_response_closes_an_abandoned_stream(query_log):
    """uvicorn path: the send fails, Starlette raises ClientDisconnect and drops the iterator."""
    from starlette.requests import ClientDisconnect

    closed = []

    async def body():
        try:
            yield "event: status\n\n"
            yield "event: meta\n\n"
        finally:
            closed.append(True)

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            raise OSError("connection lost")

    async def receive():
        return {"type": "http.request"}

    async def run():
        response = chat_router._ClosingStreamingResponse(body(), media_type="text/event-stream")
        scope = {"type": "http", "asgi": {"spec_version": "2.4"}}
        with pytest.raises(ClientDisconnect):
            await response(scope, receive, send)
        # checked while the loop runs: its shutdown would finalize a leaked generator anyway
        assert closed == [True]

    anyio.run(run)

