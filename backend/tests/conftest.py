"""Shared fixtures: fake LLM, fake retrieval, fake DB connection."""

import json
from contextlib import contextmanager

import pytest

from qanoun_api.rag.retrieval import Hit


class FakeLLM:
    """OpenAI-compatible stand-in: records calls, replays scripted replies."""

    def __init__(self, reply: str = "الجواب التجريبي [1]", stream_tokens: list[str] | None = None):
        self.reply = reply
        self.stream_tokens = stream_tokens or ["الجواب", " التجريبي", " [1]"]
        self.calls: list[list[dict]] = []

    def chat(self, messages, temperature=0.0, max_tokens=600, **kwargs):
        self.calls.append(messages)
        return self.reply

    def chat_stream(self, messages, temperature=0.0, max_tokens=600, **kwargs):
        self.calls.append(messages)
        yield from self.stream_tokens

    def resolve_model(self):
        return "fake-model"


def make_hit(slug: str = "family-code-ar", number: str = "12", **overrides) -> Hit:
    base = {
        "law_slug": slug, "law_title": "مدونة الأسرة", "law_title_fr": "Code de la famille",
        "group_slug": "moudawana", "domain": "family", "language": "ar", "article_number": number,
        "article_id": 1, "page": 30, "text": "يتم الزواج بعقد يبرره بين الزوجين.",
        "rrf": 0.016, "dense_rank": 1, "lexical_rank": None,
    }
    base.update(overrides)
    return Hit(**base)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """Returns canned rows per call pattern; records SQL for assertions."""

    def __init__(self, results: dict[str, list]):
        self.results = results  # substring of SQL -> rows
        self.queries: list[str] = []

    def execute(self, sql, params=None):
        self.queries.append(sql)
        for key, rows in self.results.items():
            if key in sql:
                return FakeResult(rows)
        return FakeResult([])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture()
def fake_llm():
    return FakeLLM()


@pytest.fixture()
def fake_db(monkeypatch):
    """Route every router `db()` call to a FakeConn built from the given results.

    Routers do `from qanoun_api.db import db`, so the symbol must be patched in each
    router module, not in qanoun_api.db.
    """

    def install(results: dict[str, list]):
        conn = FakeConn(results)

        @contextmanager
        def ctx():
            yield conn

        for mod in ("qanoun_api.routers.laws", "qanoun_api.routers.analytics"):
            monkeypatch.setattr(f"{mod}.db", ctx)
        return conn

    return install


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    events = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data = json.loads(line.removeprefix("data:").strip())
        if name and data is not None:
            events.append((name, data))
    return events
