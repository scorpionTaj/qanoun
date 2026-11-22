"""One `query_log` row per /api/chat request: what was asked, how it went, how long it took.

The chat router feeds every SSE event it sends through `QueryRecord.observe`, so the record
sees exactly what the user saw, on every exit path (answer, abstention, error, or the client
closing the stream). `write` runs once the stream has ended and never raises: logging must
not break answering.

Privacy: no IP and no user id. The question is stored as a SHA-256 of its normalized form,
which counts repeats; its text only when QANOUN_LOG_QUESTIONS is on. Rows older than
RETENTION_DAYS are swept now and then.
"""

import hashlib
import logging
import random
import time
from dataclasses import dataclass, field

from qanoun_pipeline.normalize import normalize

from qanoun_api.config import SETTINGS
from qanoun_api.db import db

log = logging.getLogger(__name__)

RETENTION_DAYS = 90


@dataclass
class QueryRecord:
    question: str
    scope_domain: str | None = None
    scope_group: str | None = None
    follow_up: bool = False
    variety: str | None = None
    outcome: str = "disconnected"  # until a final event says otherwise
    error_code: str | None = None
    provider: str | None = None
    model: str | None = None
    timings: dict = field(default_factory=dict)
    source_article_ids: list[int] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)
    started: float = field(default_factory=time.perf_counter)

    def observe(self, event: str, data: dict) -> None:
        if event == "meta":
            self.variety = data.get("variety")
        elif event == "sources":
            self.source_article_ids = [s["article_id"] for s in data["sources"] if s.get("article_id")]
        elif event == "model":
            self.provider, self.model = data.get("provider"), data.get("model")
        elif event == "done":
            self.outcome = "abstained" if data.get("abstained") else "answered"
            self.cited = list(data.get("cited") or [])
            self.timings = data.get("timings") or {}
            self.provider = data.get("provider", self.provider)
            self.model = data.get("model", self.model)
        elif event == "error":
            self.outcome, self.error_code = "error", data.get("code")

    def row(self) -> dict:
        return {
            "question_hash": hashlib.sha256(normalize(self.question).encode()).hexdigest(),
            "question": self.question if SETTINGS.log_questions else None,
            "variety": self.variety,
            "scope_domain": self.scope_domain,
            "scope_group": self.scope_group,
            "follow_up": self.follow_up,
            "outcome": self.outcome,
            "error_code": self.error_code,
            "provider": self.provider,
            "model": self.model,
            "rewrite_ms": self.timings.get("rewrite"),
            "search_ms": self.timings.get("search"),
            "answer_ms": self.timings.get("answer"),
            "total_ms": round((time.perf_counter() - self.started) * 1000),
            "source_article_ids": self.source_article_ids,
            "cited": self.cited,
        }


_INSERT = """
INSERT INTO query_log (question_hash, question, variety, scope_domain, scope_group, follow_up,
                       outcome, error_code, provider, model, rewrite_ms, search_ms, answer_ms,
                       total_ms, source_article_ids, cited)
VALUES (%(question_hash)s, %(question)s, %(variety)s, %(scope_domain)s, %(scope_group)s,
        %(follow_up)s, %(outcome)s, %(error_code)s, %(provider)s, %(model)s, %(rewrite_ms)s,
        %(search_ms)s, %(answer_ms)s, %(total_ms)s, %(source_article_ids)s, %(cited)s)
"""


def write(record: QueryRecord, connect=db) -> None:
    try:
        with connect() as conn:
            conn.execute(_INSERT, record.row())
            if random.random() < 0.01:
                conn.execute(
                    "DELETE FROM query_log WHERE ts < now() - make_interval(days => %s)",
                    (RETENTION_DAYS,),
                )
    except Exception:
        log.warning("query log write failed", exc_info=True)
