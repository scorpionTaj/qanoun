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
