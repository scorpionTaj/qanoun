"""Hybrid retrieval over Postgres: pgvector cosine (dense) + Arabic FTS (lexical), fused
with reciprocal rank fusion.

The query side mirrors the indexing side exactly: the question is normalized with the
pipeline normalizer (same letter folding, same digit mapping) for FTS, and embedded with
the same model and prefixes for the vector search.
"""

import os
import threading
from dataclasses import dataclass, field

import numpy as np
import psycopg
from qanoun_pipeline.embed import Embedder, fake_embedder, spec_for
from qanoun_pipeline.normalize import normalize

from qanoun_api.config import SETTINGS
from qanoun_api.db import db

RRF_K = 60
CANDIDATES = 50  # per-channel candidate pool before fusion
RERANK_POOL = 30  # fused candidates the cross-encoder re-scores (when enabled)


@dataclass(frozen=True)
class Hit:
    law_slug: str
    law_title: str  # Arabic title; the UI switches by locale when a French title exists
    law_title_fr: str | None
    group_slug: str
    domain: str
    language: str
    article_number: str
    article_id: int
    page: int
    text: str
    rrf: float
    dense_rank: int | None = None
    lexical_rank: int | None = None

    def as_dict(self) -> dict:
        return {
            "law_slug": self.law_slug,
            "law_title": self.law_title,
            "law_title_fr": self.law_title_fr,
            "group_slug": self.group_slug,
            "domain": self.domain,
            "language": self.language,
            "article_number": self.article_number,
            "article_id": self.article_id,
            "page": self.page,
            "text": self.text,
            "score": round(self.rrf, 5),
        }


@dataclass
class RetrievalResult:
    query: str
    search_query: str  # what was actually searched (after Darija rewriting, if any)
    hits: list[Hit] = field(default_factory=list)


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder:
    """Load the embedding model once (BGE-M3: a ~2 GB download on cold start; Gemini: an API
    client). Locked: the start-up warm-up thread and an early request must not load it twice."""
    global _embedder
    with _embedder_lock:
        if _embedder is None:
            if os.environ.get("QANOUN_FAKE_EMBED") == "1":
                _embedder = fake_embedder(dim=1024, cache_dir=None)
            else:
                _embedder = Embedder(spec_for(SETTINGS.embed_model), cache_dir=None)
        return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    """Test seam: inject a fake embedder."""
    global _embedder
    _embedder = embedder


_SQL = """
WITH dense AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(vec)s::vector) AS rank
    FROM chunks c
    JOIN laws l ON l.id = c.law_id
    WHERE (%(domain)s::text IS NULL OR l.domain = %(domain)s)
      AND (%(law_slug)s::text IS NULL OR l.slug = %(law_slug)s)
      AND (%(group)s::text IS NULL OR l.group_slug = %(group)s)
    ORDER BY c.embedding <=> %(vec)s::vector
    LIMIT %(n)s
),
lexical AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank(
               to_tsvector('simple', a.normalized),
               plainto_tsquery('simple', %(tsq)s)) DESC) AS rank
    FROM chunks c
    JOIN articles a ON a.id = c.article_id
    JOIN laws l ON l.id = c.law_id
    WHERE to_tsvector('simple', a.normalized) @@ plainto_tsquery('simple', %(tsq)s)
      AND (%(domain)s::text IS NULL OR l.domain = %(domain)s)
      AND (%(law_slug)s::text IS NULL OR l.slug = %(law_slug)s)
      AND (%(group)s::text IS NULL OR l.group_slug = %(group)s)
    ORDER BY rank  -- without this, LIMIT keeps an arbitrary 50 matches, not the best 50
    LIMIT %(n)s
),
fused AS (
    SELECT id, 1.0::float / (%(rrf_k)s + rank) AS score, rank AS dense_rank, NULL::int AS lexical_rank
    FROM dense
    UNION ALL
    SELECT id, 1.0::float / (%(rrf_k)s + rank), NULL::int, rank
    FROM lexical
)
SELECT l.slug, l.title_ar, l.title_fr, l.group_slug, l.domain, l.language,
       a.number, a.id, ch.page, ch.text,
       SUM(f.score) AS rrf,
       MIN(f.dense_rank) AS dense_rank,
       MIN(f.lexical_rank) AS lexical_rank
FROM fused f
JOIN chunks ch ON ch.id = f.id
JOIN articles a ON a.id = ch.article_id
JOIN laws l ON l.id = ch.law_id
GROUP BY l.slug, l.title_ar, l.title_fr, l.group_slug, l.domain, l.language,
         a.number, a.id, ch.page, ch.text
ORDER BY rrf DESC
LIMIT %(k)s
"""


def search(
    query: str,
    k: int = 8,
    domain: str | None = None,
    law_slug: str | None = None,
    group: str | None = None,  # every edition of one law (AR + FR)
    search_query: str | None = None,
    conn: psycopg.Connection | None = None,
) -> RetrievalResult:
    """Hybrid search. `search_query` lets the caller supply an already-rewritten query."""
    effective = (search_query or query).strip()
    if not effective:
        return RetrievalResult(query=query, search_query=effective)
    vector = get_embedder().encode_query(effective)
    tsq = " ".join(normalize(effective).split())
    params = {
        "vec": np.asarray(vector, dtype=np.float32),
        "tsq": tsq,
        "domain": domain,
        "law_slug": law_slug,
        "group": group,
        "n": CANDIDATES,
        "k": max(k, RERANK_POOL) if SETTINGS.reranker else k,
        "rrf_k": RRF_K,
    }
    if conn is None:
        with db() as c:
            result = _run(c, query, effective, params)
    else:
        result = _run(conn, query, effective, params)
    if SETTINGS.reranker and result.hits:
        result.hits = rerank(effective, result.hits, k)
    return result


_reranker = None
_reranker_lock = threading.Lock()


def get_reranker():
    """The cross-encoder from QANOUN_RERANKER, loaded once (a one-time model download)."""
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            from qanoun_pipeline.embed import torch_device
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder(SETTINGS.reranker, device=torch_device(), max_length=512)
        return _reranker


def rerank(query: str, hits: list[Hit], k: int) -> list[Hit]:
    """Re-order fused candidates by a cross-encoder reading question and article together:
    fusion ranks by overlap, the reranker by whether the passage actually answers."""
    pairs = [(query, f"{hit.law_title} — {hit.article_number}: {hit.text}") for hit in hits]
    scores = get_reranker().predict(pairs)
    ranked = sorted(zip(scores, hits, strict=True), key=lambda pair: -float(pair[0]))
    return [hit for _, hit in ranked[:k]]


def _run(conn: psycopg.Connection, query: str, effective: str, params: dict) -> RetrievalResult:
    rows = conn.execute(_SQL, params).fetchall()
    hits = [
        Hit(
            law_slug=r[0], law_title=r[1], law_title_fr=r[2], group_slug=r[3], domain=r[4],
            language=r[5], article_number=r[6], article_id=r[7], page=r[8], text=r[9],
            rrf=float(r[10]),
            dense_rank=r[11], lexical_rank=r[12],
        )
        for r in rows
    ]
    return RetrievalResult(query=query, search_query=effective, hits=hits)
