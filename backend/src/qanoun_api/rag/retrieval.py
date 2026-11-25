"""Hybrid retrieval over Postgres: pgvector cosine (dense) + Arabic FTS (lexical), fused
with reciprocal rank fusion.

The query side mirrors the indexing side exactly: the question is normalized with the
pipeline normalizer (same letter folding, same digit mapping) for FTS, and embedded with
the same model and prefixes for the vector search.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field

import httpx
import numpy as np
import psycopg
from qanoun_pipeline.embed import Embedder, fake_embedder, spec_for
from qanoun_pipeline.normalize import normalize

from qanoun_api.config import SETTINGS
from qanoun_api.db import db

log = logging.getLogger(__name__)

RRF_K = 60
CANDIDATES = 50  # per-channel candidate pool before fusion
# HNSW returns at most ef_search rows (pgvector's default is 40, i.e. fewer than CANDIDATES)
# and its recall grows with it. Legal passages embed close together, so the default misses
# true neighbours. Measured on the demo (Jina, 13.9k chunks, freshly built index), recall@10
# against an exact scan / median query time: 0.63 / 1 ms at 40, 0.91 / 3 ms at 200,
# 1.00 / 5 ms at 400, and the exact scan itself takes 93 ms.
HNSW_EF_SEARCH = 400
# Reranking (QANOUN_RERANKER): the fused top RERANK_POOL are re-ordered by a weighted
# reciprocal-rank fusion of their fused rank and the reranker's rank, RERANK_WEIGHT on the
# reranker. Measured on the 323 eval questions as typed against the demo (Jina's
# jina-reranker-v2-base-multilingual, eval/rerank_study.py), MRR law / article / page:
# fused 0.837 / 0.583 / 0.604; reranker order alone 0.851 / 0.617 / 0.624; this blend
# 0.864 / 0.669 / 0.635, and article hit@10 0.778 → 0.833. The reranker alone sometimes buries
# an exact match the fusion had right; blended, it mostly moves good candidates up.
RERANK_POOL = 20
RERANK_RRF_K = 60
RERANK_WEIGHT = 0.7


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
    """Load the embedding model once (BGE-M3: a ~2 GB download on cold start; Jina: an API
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


class JinaReranker:
    """Jina's rerank API (key in QANOUN_JINA_KEY), shaped like a CrossEncoder: no model on the
    server, so it runs where the API does (Vercel). Billed per token of question + passages,
    so passages are cut to MAX_CHARS (an article's opening says what it is about)."""

    URL = "https://api.jina.ai/v1/rerank"
    MAX_CHARS = 600

    def __init__(self, model: str, key: str | None = None, client: httpx.Client | None = None,
                 attempts: int = 1, sleep=time.sleep):  # fmt: skip
        self.model = model
        self.key = key or os.environ.get("QANOUN_JINA_KEY", "")
        if not self.key:
            raise RuntimeError("QANOUN_JINA_KEY is not set (needed for the Jina reranker)")
        self.client = client or httpx.Client(timeout=30)
        # A question can't wait out a rate limit: by default a 429 fails fast and search()
        # keeps the fused order. Batch jobs (the eval) pass more attempts.
        self.attempts, self.sleep = attempts, sleep
        self.tokens = 0  # used so far, as the API reports it

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """One request per call: every pair must share the question (as rerank() sends them)."""
        if not pairs:
            return []
        body = {"model": self.model, "query": pairs[0][0], "return_documents": False,
                "documents": [passage[: self.MAX_CHARS] for _, passage in pairs]}  # fmt: skip
        for attempt in range(self.attempts):
            response = self.client.post(self.URL, json=body, headers={"Authorization": f"Bearer {self.key}"})
            if response.status_code != 429 or attempt == self.attempts - 1:
                break
            retry_after = response.headers.get("retry-after", "")
            self.sleep(float(retry_after) if retry_after.isdigit() else min(2.0**attempt, 60.0))
        response.raise_for_status()
        data = response.json()
        self.tokens += (data.get("usage") or {}).get("total_tokens", 0)
        scores = [0.0] * len(pairs)
        for item in data["results"]:
            scores[item["index"]] = float(item["relevance_score"])
        return scores


def get_reranker():
    """The reranker named by QANOUN_RERANKER, built once: Jina's API for a `jina-reranker…`
    model, otherwise a local cross-encoder (a one-time model download)."""
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            if SETTINGS.reranker.startswith("jina-reranker"):
                _reranker = JinaReranker(SETTINGS.reranker)
            else:
                from qanoun_pipeline.embed import torch_device
                from sentence_transformers import CrossEncoder

                _reranker = CrossEncoder(SETTINGS.reranker, device=torch_device(), max_length=512)
        return _reranker


def blend(scores: list[float], k: float = RERANK_RRF_K, weight: float = RERANK_WEIGHT) -> list[int]:
    """Positions 0..n-1 (the fused order) re-ordered by weighted reciprocal-rank fusion of
    the fused rank and the rank by `scores` (the reranker's)."""
    positions = range(len(scores))
    by_score = {i: rank for rank, i in enumerate(sorted(positions, key=lambda i: -scores[i]), start=1)}
    value = {i: (1 - weight) / (k + i + 1) + weight / (k + by_score[i]) for i in positions}
    return sorted(positions, key=lambda i: -value[i])


def rerank(query: str, hits: list[Hit], k: int) -> list[Hit]:
    """Re-order the fused top RERANK_POOL with a reranker reading question and article
    together: fusion ranks by overlap, the reranker by whether the passage answers."""
    pool = hits[:RERANK_POOL]
    pairs = [(query, f"{hit.law_title} — {hit.article_number}: {hit.text}") for hit in pool]
    try:
        scores = [float(score) for score in get_reranker().predict(pairs)]
    except (httpx.HTTPError, RuntimeError) as exc:  # rate limit, quota, network: answer anyway
        log.warning("reranker failed, keeping the fused order: %s", exc)
        return hits[:k]
    return ([pool[i] for i in blend(scores)] + hits[RERANK_POOL:])[:k]


def _run(conn: psycopg.Connection, query: str, effective: str, params: dict) -> RetrievalResult:
    with conn.transaction():  # set_config(..., true) lasts until the end of this transaction
        conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(HNSW_EF_SEARCH),))
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
