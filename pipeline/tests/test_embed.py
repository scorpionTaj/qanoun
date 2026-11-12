from pathlib import Path

import numpy as np
import pytest

from qanoun_pipeline.embed import Embedder, FakeEncoder, fake_embedder


def test_fake_encoder_is_deterministic_and_normalized():
    enc = FakeEncoder(dim=64)
    a = enc.encode(["نص عربي", "نص عربي"])
    assert a.shape == (2, 64)
    assert np.allclose(a[0], a[1])
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0)


def test_passage_cache_persists_between_embedders(tmp_path: Path):
    first = Embedder(encoder=FakeEncoder(dim=16), cache_dir=tmp_path)
    vectors = first.encode_passages(["المادة الأولى", "المادة الثانية"])

    # A fresh embedder with an empty cache must reproduce the same vectors from disk.
    second = Embedder(encoder=FakeEncoder(dim=16), cache_dir=tmp_path)
    cached = second.encode_passages(["المادة الأولى", "المادة الثانية"])
    assert np.allclose(vectors, cached)
    assert list(tmp_path.glob("*.npz"))


def test_cache_only_embeds_new_texts(tmp_path: Path):
    embedder = Embedder(encoder=FakeEncoder(dim=16), cache_dir=tmp_path)
    embedder.encode_passages(["نص"])
    store = next(iter(tmp_path.glob("*.npz")))

    embedder.encode_passages(["نص", "نص جديد"])
    with np.load(store) as data:
        assert len(data["keys"]) == 2


def test_query_encoding_uses_prefix():
    spec_with_prefix = type(fake_embedder(8).spec)(key="t", name="t", dim=8, query_prefix="query: ")
    embedder = Embedder(spec_with_prefix, encoder=FakeEncoder(dim=8), cache_dir=None)
    bare = Embedder(type(spec_with_prefix)(key="t2", name="t", dim=8), encoder=FakeEncoder(dim=8), cache_dir=None)
    assert not np.allclose(embedder.encode_query("س"), bare.encode_query("س"))


def test_real_model_spec_has_expected_dim():
    from qanoun_pipeline.embed import MODELS

    assert MODELS["m3"].dim == 1024


@pytest.mark.parametrize("dim", [64, 1024])
def test_fake_embedder_dims(dim):
    vectors = fake_embedder(dim).encode_passages(["x"])
    assert vectors.shape == (1, dim)


def _jina(responses, dim=4):
    """JinaEncoder over a fake HTTP transport replaying `responses` (status, body, headers)."""
    import json

    import httpx

    from qanoun_pipeline.embed import JinaEncoder

    sent, slept = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        status, body, headers = responses[len(sent) - 1]
        return httpx.Response(status, json=body, headers=headers)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    encoder = JinaEncoder("jina-embeddings-v3", dim, key="test", client=client, sleep=slept.append)
    return encoder, sent, slept


def _data(vectors):
    # The API may return items out of order; `index` says where each belongs.
    return {"data": [{"index": i, "embedding": v} for i, v in reversed(list(enumerate(vectors)))]}


def test_jina_batches_orders_normalizes_and_uses_task_adapters():
    first = [[3.0, 4.0, 0.0, 0.0]] + [[1.0, 0.0, 0.0, 0.0]] * 63
    encoder, sent, _ = _jina([(200, _data(first), {}), (200, _data([[0, 0, 2.0, 0]] * 6), {})])
    vectors = encoder.encode([f"t{i}" for i in range(70)])
    assert vectors.shape == (70, 4)
    np.testing.assert_allclose(vectors[0], [0.6, 0.8, 0.0, 0.0])  # kept in input order, unit length
    assert [len(body["input"]) for body in sent] == [64, 6]
    assert sent[0]["task"] == "retrieval.passage" and sent[0]["dimensions"] == 4

    encoder, sent, _ = _jina([(200, _data([[1.0, 0, 0, 0]]), {})])
    encoder.encode_queries(["q"])
    assert sent[0]["task"] == "retrieval.query"


def test_jina_waits_out_the_rate_limit():
    ok = (200, _data([[1.0, 0, 0, 0]]), {})
    encoder, sent, slept = _jina([(429, {}, {"retry-after": "7"}), (429, {}, {}), ok])
    encoder.encode(["t"])
    assert len(sent) == 3 and slept == [7.0, 2.0]  # the server's delay, then backoff


def test_embedder_routes_queries_to_the_query_task():
    from qanoun_pipeline.embed import MODELS

    encoder, sent, _ = _jina([(200, _data([[0.0, 1.0, 0.0, 0.0]]), {})])
    embedder = Embedder(MODELS["jina"], encoder=encoder, cache_dir=None)
    vector = embedder.encode_query("ما هي شروط الزواج؟")
    assert vector.dtype == np.float32 and sent[0]["task"] == "retrieval.query"


def test_spec_for_picks_the_model_by_name_and_defaults_to_bge_m3():
    from qanoun_pipeline.embed import MODELS, spec_for

    assert spec_for("jina-embeddings-v3") is MODELS["jina"]
    assert spec_for(None) is MODELS["m3"] and spec_for("unknown") is MODELS["m3"]
