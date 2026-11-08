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


def test_rerank_reorders_by_cross_encoder_score(monkeypatch):
    from conftest import make_hit

    from qanoun_api.rag import retrieval

    class FakeCrossEncoder:
        def predict(self, pairs):
            return [1.0 if "133" in passage else 0.1 for _, passage in pairs]

    monkeypatch.setattr(retrieval, "get_reranker", lambda: FakeCrossEncoder())
    hits = [make_hit(number="132"), make_hit(number="136"), make_hit(number="133")]
    out = retrieval.rerank("عدة الحامل", hits, k=2)
    assert [h.article_number for h in out] == ["133", "132"]
