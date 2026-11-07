"""Chat endpoint over SSE with faked retrieval + LLM (no DB, no network)."""

from qanoun_api.rag import retrieval
from qanoun_api.rag.retrieval import RetrievalResult
from qanoun_api.routers import chat as chat_router
from qanoun_api.main import app
from fastapi.testclient import TestClient

from conftest import make_hit, parse_sse


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
    assert names == ["meta", "sources", "token", "token", "token", "done"]
    meta = events[0][1]
    assert meta["variety"] == "msa"
    assert meta["disclaimer"]
    sources = events[1][1]["sources"]
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
    from qanoun_api.rag.llm import LLMClient

    class SentinelLLM:
        calls = []

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
            raise RuntimeError("connection refused")
            yield  # pragma: no cover

    monkeypatch.setattr(retrieval, "search", lambda *a, **kw: RetrievalResult("q", "q", [make_hit()]))
    chat_router.set_llm(BrokenLLM(), None)
    events = parse_sse(post_chat({"question": "سؤال"}))
    assert events[-1][0] == "error"
    assert "LLM unavailable" in events[-1][1]["message"]


def test_chat_validates_input():
    client = TestClient(app)
    assert client.post("/api/chat", json={"question": ""}).status_code == 422
