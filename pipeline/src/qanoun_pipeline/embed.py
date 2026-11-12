"""Embedding models with a per-text on-disk cache (ported from darija-rag's dense.py).

Two real encoders: BGE-M3 run locally (sentence-transformers, an optional extra) and
Gemini's embedding API, which needs no model on the server, so the API fits a small
serverless function. QANOUN_EMBED_MODEL picks one; passages and queries must use the same.
Tests and smoke runs inject a `FakeEncoder`. Cache keys are sha256 of the exact passage
string, so adding a document embeds only its new chunks.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
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
    # Gemini's API model, truncated to 1024 dimensions to fit the same pgvector column.
    "gemini": EmbeddingSpec("gemini", "gemini-embedding-001", dim=1024),
    # E5 models are trained with these prefixes; leaving them out costs recall.
    "e5": EmbeddingSpec("e5", "intfloat/multilingual-e5-small", dim=384, query_prefix="query: ", passage_prefix="passage: "),
}

EMBED_DIM = {spec.key: spec.dim for spec in MODELS.values()}


def spec_for(name: str | None) -> EmbeddingSpec:
    """The spec whose model name is `name` (QANOUN_EMBED_MODEL); BGE-M3 when unset."""
    return next((s for s in MODELS.values() if s.name == name), MODELS[DEFAULT_MODEL])


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
        if encoder is None and spec.key == "gemini":
            encoder = GeminiEncoder(spec.name, spec.dim)
        elif encoder is None:
            from sentence_transformers import SentenceTransformer

            encoder = SentenceTransformer(spec.name, device=torch_device())
        self.encoder = encoder
        self.cache_dir = cache_dir

    SAVE_EVERY = 500  # passages between cache writes, so a long remote run can resume

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
        for start in range(0, len(missing), self.SAVE_EVERY):
            if len(missing) > self.SAVE_EVERY:
                print(f"  embedding {start:,}/{len(missing):,} new passages", flush=True)
            part = missing[start : start + self.SAVE_EVERY]
            fresh = self._encode([full[i] for i in part])
            cached.update({keys[i]: vector for i, vector in zip(part, fresh, strict=True)})
            if store:
                store.parent.mkdir(parents=True, exist_ok=True)
                tmp = store.with_suffix(".part.npz")
                np.savez(tmp, keys=np.array(list(cached)), vectors=np.stack(list(cached.values())))
                tmp.replace(store)
        return np.stack([cached[key] for key in keys]).astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        text = self.spec.query_prefix + text
        if hasattr(self.encoder, "encode_queries"):  # API models embed queries differently
            return self.encoder.encode_queries([text])[0].astype(np.float32)
        return self._encode([text])[0].astype(np.float32)

    def _encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.encoder.encode(texts, batch_size=16, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)


class GeminiEncoder:
    """Gemini's embedding API (key in QANOUN_GEMINI_KEY), shaped like SentenceTransformer.

    Vectors are truncated to `dim` by the API and re-normalized here, since a truncated
    vector is no longer unit length. Passages and queries use their own task types. The
    free tier allows about 100 texts a minute, so batches wait out 429 responses.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
    BATCH = 100  # the API's maximum per request

    def __init__(self, model: str, dim: int, key: str | None = None, client: httpx.Client | None = None,
                 sleep=time.sleep):  # fmt: skip
        self.model, self.dim = model, dim
        self.key = key or os.environ.get("QANOUN_GEMINI_KEY", "")
        if not self.key:
            raise RuntimeError("QANOUN_GEMINI_KEY is not set (needed for Gemini embeddings)")
        self.client = client or httpx.Client(timeout=120)
        self.sleep = sleep

    def encode(self, texts: list[str], **_kwargs) -> np.ndarray:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts, "RETRIEVAL_QUERY")

    def _embed(self, texts: list[str], task: str) -> np.ndarray:
        rows = []
        for start in range(0, len(texts), self.BATCH):
            rows.extend(self._request(texts[start : start + self.BATCH], task))
        vectors = np.asarray(rows, dtype=np.float32).reshape(len(texts), self.dim)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)

    def _request(self, batch: list[str], task: str, attempts: int = 30) -> list[list[float]]:
        body = {"requests": [
            {"model": f"models/{self.model}", "content": {"parts": [{"text": text}]},
             "taskType": task, "outputDimensionality": self.dim}
            for text in batch
        ]}  # fmt: skip
        for attempt in range(attempts):
            response = self.client.post(self.URL.format(model=self.model), json=body,
                                        headers={"x-goog-api-key": self.key})  # fmt: skip
            if response.status_code == 429 and attempt < attempts - 1:
                self.sleep(_retry_delay(response.text))
                continue
            response.raise_for_status()
            return [item["values"] for item in response.json()["embeddings"]]
        raise RuntimeError("unreachable")


def _retry_delay(body: str, default: float = 60.0) -> float:
    """Seconds the API asks to wait ("retryDelay": "4s"), at least a few seconds."""
    match = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', body)
    return max(float(match.group(1)), 5.0) if match else default


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
