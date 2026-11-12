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


def _gemini(responses, dim=4):
    """GeminiEncoder over a fake HTTP transport replaying `responses` in order."""
    import json

    import httpx

    from qanoun_pipeline.embed import GeminiEncoder

    sent, slept = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        status, body = responses[len(sent) - 1]
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    encoder = GeminiEncoder("gemini-embedding-001", dim, key="test", client=client, sleep=slept.append)
    return encoder, sent, slept


def test_gemini_batches_normalizes_and_uses_task_types():
    rows = [{"values": [3.0, 4.0, 0.0, 0.0]}] * 100
    encoder, sent, _ = _gemini([(200, {"embeddings": rows}), (200, {"embeddings": rows[:20]})])
    vectors = encoder.encode([f"t{i}" for i in range(120)])
    assert vectors.shape == (120, 4)
    np.testing.assert_allclose(vectors[0], [0.6, 0.8, 0.0, 0.0])  # truncated → re-normalized
    assert [len(body["requests"]) for body in sent] == [100, 20]  # the API's batch limit
    assert sent[0]["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert sent[0]["requests"][0]["outputDimensionality"] == 4

    encoder, sent, _ = _gemini([(200, {"embeddings": rows[:1]})])
    encoder.encode_queries(["q"])
    assert sent[0]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_gemini_waits_out_the_rate_limit():
    limited = {"error": {"code": 429, "details": [{"retryDelay": "12s"}]}}
    encoder, sent, slept = _gemini([(429, limited), (200, {"embeddings": [{"values": [1, 0, 0, 0]}]})])
    encoder.encode(["t"])
    assert len(sent) == 2 and slept == [12.0]


def test_embedder_routes_queries_to_the_query_task(tmp_path: Path):
    from qanoun_pipeline.embed import MODELS

    encoder, sent, _ = _gemini([(200, {"embeddings": [{"values": [0.0, 1.0, 0.0, 0.0]}]})])
    embedder = Embedder(MODELS["gemini"], encoder=encoder, cache_dir=None)
    vector = embedder.encode_query("ما هي شروط الزواج؟")
    assert vector.dtype == np.float32 and sent[0]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


def test_spec_for_picks_the_model_by_name_and_defaults_to_bge_m3():
    from qanoun_pipeline.embed import MODELS, spec_for

    assert spec_for("gemini-embedding-001") is MODELS["gemini"]
    assert spec_for(None) is MODELS["m3"] and spec_for("unknown") is MODELS["m3"]
