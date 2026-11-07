# %% [markdown]
"""
# Qanoun — Embedding space map

Projects the stored chunk embeddings to 2D (PCA, then t-SNE refinement when available) and
colors by domain: a visual sanity check that family/labour/housing clusters separate —
the same check a data scientist runs before trusting retrieval.

Requires the real (BGE-M3) ingest and a live database:
    make ingest          # real embeddings
    uv run --project backend --extra models python notebooks/03_embedding_map.py
"""

# %%
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})

if not os.environ.get("QANOUN_DB_URL"):
    os.environ["QANOUN_DB_URL"] = "postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun"

# %%
from qanoun_api.db import db  # noqa: E402

with db() as conn:
    rows = conn.execute(
        """
        SELECT l.domain, l.slug, ch.embedding::text
        FROM chunks ch JOIN laws l ON l.id = ch.law_id
        LIMIT 6000
        """
    ).fetchall()

if not rows:
    raise SystemExit("no chunks in the database — run `make ingest` (with real embeddings) first")

# pgvector text form: '[0.1,0.2,...]' — parse to a matrix
X = np.array([[float(v) for v in r[2].strip("[]").split(",")] for r in rows], dtype=np.float32)
domains = np.array([r[0] for r in rows])
slugs = np.array([r[1] for r in rows])
print(f"{X.shape[0]} chunks × {X.shape[1]} dims, {len(set(domains))} domains")

# %% [markdown]
"""## PCA → 2D. Cosine-normalized BGE-M3 vectors; PCA preserves the dominant directions."""

# %%
from sklearn.decomposition import PCA

Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
xy = PCA(n_components=2, random_state=0).fit_transform(Xn)

COLORS = {
    "family": "#ba8c4b",
    "labour": "#44855d",
    "civil": "#29553b",
    "housing": "#67a27b",
    "commercial": "#d6bd8b",
    "education": "#8c6038",
    "penal": "#722f37",
    "nationality": "#97c1a4",
    "social": "#c2dbc9",
    "justice": "#5e422d",
}

fig, ax = plt.subplots(figsize=(9, 7))
for domain in sorted(set(domains)):
    mask = domains == domain
    ax.scatter(xy[mask, 0], xy[mask, 1], s=6, alpha=0.55, color=COLORS.get(domain, "#888"), label=domain)
ax.legend(markerscale=2, frameon=False)
ax.set_title("Chunk embedding space, colored by legal domain")
Path("docs/figures").mkdir(parents=True, exist_ok=True)
fig.savefig("docs/figures/embedding_map.png", bbox_inches="tight")
print("figure → docs/figures/embedding_map.png")

# %% [markdown]
"""## Separability quick check: nearest-centroid accuracy per domain — a cheap proxy for
"are domains linearly separable", which retrieval depends on. Members are included in
their own centroid (slightly optimistic), so treat it as an upper bound."""

# %%
centroids = {d: Xn[domains == d].mean(axis=0) for d in sorted(set(domains))}
hits, total = 0, 0
for domain, centroid in centroids.items():
    members = Xn[domains == domain]
    for vec in members[:: max(1, len(members) // 50)]:
        own_sim = float(vec @ centroid)
        best_other = max(float(vec @ c) for d, c in centroids.items() if d != domain)
        hits += own_sim >= best_other
        total += 1

print(f"nearest-centroid separability: {hits / total:.0%} over {total} sampled chunks")
