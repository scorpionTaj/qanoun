"""Embedding models with a per-text on-disk cache (ported from darija-rag's dense.py).

The real encoder (sentence-transformers, BGE-M3) is an optional extra; tests and smoke
runs inject a `FakeEncoder` so no model downloads are needed. Cache keys are sha256 of the
exact passage string, so adding a document embeds only its new chunks.
"""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_MODEL = "m3"


@dataclass(frozen=True)
class EmbeddingSpec:
    key: str
    name: str
    dim: int
    query_prefix: str = ""
    passage_prefix: str = ""


MODELS = {
    # BGE-M3: multilingual, strong on Arabic legal text, 1024-dim — matches the pgvector column.
    "m3": EmbeddingSpec("m3", "BAAI/bge-m3", dim=1024),
    # E5 models are trained with these prefixes; leaving them out costs recall.
    "e5": EmbeddingSpec("e5", "intfloat/multilingual-e5-small", dim=384, query_prefix="query: ", passage_prefix="passage: "),
}

EMBED_DIM = {spec.key: spec.dim for spec in MODELS.values()}


def torch_device() -> str:
    """Device for the embedding model (QANOUN_DEVICE: cpu, mps, cuda).

    Defaults to CPU: on a Mac running the LLM locally (LM Studio/MLX), sharing the GPU made
    generation slower and retrieval latency erratic (measured in darija-rag: 2-24 s vs a
    steady 7 s on CPU).
    """
    return os.environ.get("QANOUN_DEVICE", "cpu")


def _slug(spec: EmbeddingSpec) -> str:
    # The prefixes are part of the key: the same model with other prefixes gives other vectors.
    digest = hashlib.sha256(repr(spec).encode()).hexdigest()[:8]
    return f"{spec.name.replace('/', '__')}-{digest}"


class Embedder:
    def __init__(
        self,
        spec: EmbeddingSpec = MODELS[DEFAULT_MODEL],
        encoder=None,  # sentence_transformers.SentenceTransformer-compatible
        cache_dir: Path | None = Path("data/processed/embeddings"),
    ):
        self.spec = spec
        if encoder is None:
            from sentence_transformers import SentenceTransformer

            encoder = SentenceTransformer(spec.name, device=torch_device())
        self.encoder = encoder
        self.cache_dir = cache_dir

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        """Embed passages, consulting/refreshing the on-disk cache."""
        full = [self.spec.passage_prefix + text for text in texts]
        keys = [hashlib.sha256(text.encode()).hexdigest() for text in full]
        store = self.cache_dir / f"{_slug(self.spec)}.npz" if self.cache_dir else None
        cached: dict[str, np.ndarray] = {}
        if store and store.exists():
            with np.load(store) as data:
                cached = dict(zip(data["keys"].tolist(), data["vectors"], strict=True))
        missing = sorted({i for i, key in enumerate(keys) if key not in cached})
        if missing:
            fresh = self._encode([full[i] for i in missing])
            cached.update({keys[i]: vector for i, vector in zip(missing, fresh, strict=True)})
            if store:
                store.parent.mkdir(parents=True, exist_ok=True)
                tmp = store.with_suffix(".part.npz")
                np.savez(tmp, keys=np.array(list(cached)), vectors=np.stack(list(cached.values())))
                tmp.replace(store)
        return np.stack([cached[key] for key in keys]).astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self._encode([self.spec.query_prefix + text])[0].astype(np.float32)

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.encoder.encode(texts, batch_size=16, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)


class FakeEncoder:
    """Deterministic stand-in for smoke runs and tests: hashes text into unit vectors."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def encode(self, texts: list[str], **_kwargs) -> np.ndarray:
        rows = np.zeros((len(texts), self.dim), dtype=np.float32)
        for index, text in enumerate(texts):
            digest = hashlib.sha256(text.encode()).digest()
            for byte in digest:
                rows[index, byte % self.dim] += 1.0
            rows[index] /= np.linalg.norm(rows[index]) or 1.0
        return rows


def fake_embedder(dim: int = 64, cache_dir: Path | None = None) -> Embedder:
    spec = EmbeddingSpec("fake", "fake-model", dim=dim)
    return Embedder(spec, encoder=FakeEncoder(dim), cache_dir=cache_dir)
