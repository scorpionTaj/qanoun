import pytest
from conftest import make_hit

from qanoun_api.rag.answer import merge
from qanoun_api.rag.retrieval import RetrievalResult


def test_merge_fuses_and_dedupes_by_identity():
    a = RetrievalResult("q", "q", hits=[make_hit(rrf=0.01), make_hit(number="13", rrf=0.008)])
    b = RetrievalResult("q", "q2", hits=[make_hit(rrf=0.012), make_hit(number="14", rrf=0.006)])
    fused = merge(a, b, k=5)
    numbers = [h.article_number for h in fused.hits]
    assert numbers == ["12", "13", "14"]  # 12 appears in both → highest fused score
    assert fused.hits[0].rrf == 1 / 61 + 1 / 61


def test_merge_respects_k():
    hits = [make_hit(number=str(n)) for n in range(1, 6)]
    a = RetrievalResult("q", "q", hits=hits)
    b = RetrievalResult("q", "q2", hits=[])
    assert len(merge(a, b, k=3).hits) == 3


def test_merge_keeps_channel_ranks():
    a = RetrievalResult("q", "q", hits=[make_hit(dense_rank=1, lexical_rank=None)])
    b = RetrievalResult("q", "q2", hits=[make_hit(dense_rank=None, lexical_rank=2)])
    fused = merge(a, b, k=5)
    assert fused.hits[0].dense_rank == 1
    assert fused.hits[0].lexical_rank == 2


def test_hit_as_dict_is_json_ready():
    data = make_hit().as_dict()
    assert data["law_slug"] == "family-code-ar"
    assert isinstance(data["score"], float)


def test_rerank_moves_the_answering_article_up(monkeypatch):
    from conftest import make_hit

    from qanoun_api.rag import retrieval

    class FakeCrossEncoder:
        def predict(self, pairs):
            return [1.0 if "133" in passage else 0.1 for _, passage in pairs]

    monkeypatch.setattr(retrieval, "get_reranker", lambda: FakeCrossEncoder())
    hits = [make_hit(number="132"), make_hit(number="136"), make_hit(number="133")]
    out = retrieval.rerank("عدة الحامل", hits, k=2)
    assert [h.article_number for h in out] == ["133", "132"]


def test_dense_search_asks_hnsw_for_enough_candidates():
    """pgvector's default ef_search (40) caps the dense channel below CANDIDATES (50) and
    hurts recall; search() raises it for its own transaction only."""
    from contextlib import contextmanager

    from qanoun_api.rag import retrieval

    calls: list[tuple] = []

    class Conn:
        @contextmanager
        def transaction(self):
            calls.append(("begin",))
            yield
            calls.append(("commit",))

        def execute(self, sql, params=None):
            calls.append(("sql", sql.strip().split()[0], params))

            class Rows:
                def fetchall(self):
                    return []

            return Rows()

    retrieval._run(Conn(), "q", "q", {"n": retrieval.CANDIDATES})
    assert retrieval.HNSW_EF_SEARCH >= retrieval.CANDIDATES
    assert calls[0] == ("begin",) and calls[-1] == ("commit",)
    assert calls[1] == ("sql", "SELECT", (str(retrieval.HNSW_EF_SEARCH),))  # set_config first
    assert calls[2][1] == "WITH"  # then the hybrid query, in the same transaction


def test_blend_moves_good_candidates_up_without_burying_the_fused_top():
    from qanoun_api.rag.retrieval import blend

    # the reranker likes the fused 5th best and the fused 1st least: the 5th moves up to 2nd,
    # the 1st falls to 4th, not to the bottom where the reranker's order alone would put it
    assert blend([0.1, 0.5, 0.4, 0.3, 0.9]) == [1, 4, 2, 0, 3]
    # the reranker's second choice that fusion ranked first stays first
    assert blend([0.5, 0.1, 0.2, 0.9, 0.3])[0] == 0
    assert blend([3.0, 2.0, 1.0]) == [0, 1, 2]  # agreement keeps the order


def test_rerank_keeps_the_fused_order_when_the_reranker_fails(monkeypatch):
    import httpx
    from conftest import make_hit

    from qanoun_api.rag import retrieval

    class Down:
        def predict(self, pairs):
            raise httpx.ConnectError("no route")

    monkeypatch.setattr(retrieval, "get_reranker", lambda: Down())
    hits = [make_hit(number=n) for n in ("1", "2", "3")]
    assert retrieval.rerank("q", hits, k=2) == hits[:2]


def test_jina_reranker_scores_by_index_and_retries_rate_limits():
    import json

    import httpx

    from qanoun_api.rag.retrieval import JinaReranker

    sent, waits = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            return httpx.Response(429, headers={"retry-after": "3"})
        return httpx.Response(200, json={"usage": {"total_tokens": 42}, "results": [
            {"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]})

    reranker = JinaReranker("jina-reranker-v2-base-multilingual", key="k",
                            client=httpx.Client(transport=httpx.MockTransport(handler)),
                            attempts=3, sleep=waits.append)
    scores = reranker.predict([("سؤال", "نص " * 400), ("سؤال", "نص آخر")])
    assert scores == [0.2, 0.9] and waits == [3.0] and reranker.tokens == 42
    assert sent[-1]["query"] == "سؤال" and len(sent[-1]["documents"][0]) == JinaReranker.MAX_CHARS

    # one attempt (what a question gets): a 429 is an error, rerank() then keeps the fused order
    sent.clear()
    with pytest.raises(httpx.HTTPStatusError):
        JinaReranker("m", key="k", client=httpx.Client(transport=httpx.MockTransport(handler))).predict(
            [("q", "p")]
        )
