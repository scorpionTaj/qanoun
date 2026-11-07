"""Chat endpoint over SSE with faked retrieval + LLM (no DB, no network)."""

from conftest import make_hit, parse_sse
from fastapi.testclient import TestClient

from qanoun_api.main import app
from qanoun_api.rag import retrieval
from qanoun_api.rag.retrieval import RetrievalResult
from qanoun_api.routers import chat as chat_router


def post_chat(payload: dict) -> str:
    client = TestClient(app)
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return response.text


def test_chat_streams_full_event_flow(monkeypatch, fake_llm):
    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(fake_llm, None)
    events = parse_sse(post_chat({"question": "ما هي شروط الزواج؟"}))

    names = [name for name, _ in events]
    assert names == ["status", "meta", "sources", "status", "token", "token", "token", "done"]
    assert [d["stage"] for n, d in events if n == "status"] == ["searching", "answering"]
    meta = events[1][1]
    assert meta["variety"] == "msa"
    assert meta["disclaimer"]
    assert set(events[-1][1]["timings"]) == {"rewrite", "search", "answer"}
    sources = events[2][1]["sources"]
    assert sources[0]["law_slug"] == "family-code-ar"
    done = events[-1][1]
    assert done["abstained"] is False
    assert done["cited"] == [0]


def test_chat_abstains_without_sources(monkeypatch, fake_llm):
    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", []))
    chat_router.set_llm(fake_llm, None)
    events = parse_sse(post_chat({"question": "واش غادي تمطر غدا؟"}))
    done = events[-1][1]
    assert done["abstained"] is True
    assert done["text"]
    # no LLM call happened
    assert fake_llm.calls == []


def test_chat_abstains_on_no_answer_sentinel(monkeypatch):

    class SentinelLLM:
        def __init__(self):
            self.calls = []

        def chat_stream(self, messages, **kw):
            self.calls.append(messages)
            yield "NO_ANSWER"

    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(SentinelLLM(), None)
    events = parse_sse(post_chat({"question": "سؤال لا جواب له"}))
    done = events[-1][1]
    assert done["abstained"] is True


def test_chat_reports_llm_failure(monkeypatch):
    class BrokenLLM:
        def chat_stream(self, messages, **kw):
            from qanoun_api.rag.llm import LLMError

            raise LLMError("connection refused", kind="unreachable")
            yield  # pragma: no cover

    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(BrokenLLM(), None)
    events = parse_sse(post_chat({"question": "سؤال"}))
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "unreachable"
    assert "connection refused" in events[-1][1]["message"]


def test_chat_validates_input():
    client = TestClient(app)
    assert client.post("/api/chat", json={"question": ""}).status_code == 422


def test_chat_reports_mid_stream_interruption(monkeypatch):
    class FlakyLLM:
        def chat_stream(self, messages, **kw):
            yield "partial "
            raise RuntimeError("connection reset")

    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(FlakyLLM(), None)
    events = parse_sse(post_chat({"question": "سؤال"}))
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "interrupted"
    assert "done" not in [name for name, _ in events]
