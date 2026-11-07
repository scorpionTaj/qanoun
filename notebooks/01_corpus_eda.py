# %% [markdown]
"""
# Qanoun — Corpus EDA

Exploratory analysis of the ingested Moroccan legal corpus. Works off the JSONL artifacts
the pipeline writes (`data/processed/`), so it runs even without a live database.

Run:
    uv run --project pipeline --with pandas --with matplotlib python notebooks/01_corpus_eda.py
"""

# %%
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})
GREEN, SAND, DARK = "#44855d", "#ba8c4b", "#1d392a"

ARTICLES = Path("data/processed/articles.jsonl")
CATALOG = Path("data/catalog/laws.yaml")
FIGURES = Path("docs/figures")

if not ARTICLES.exists():
    raise SystemExit("no articles.jsonl — run `make ingest-smoke` or `make ingest` first")

# %% [markdown]
"""## Load articles + catalog metadata"""

# %%
articles = pd.read_json(ARTICLES, lines=True)
articles = articles.rename(columns={"law_slug": "slug"})
articles["chars"] = articles["text"].str.len()
articles["words"] = articles["text"].str.split().str.len()

catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["entries"]
meta = pd.DataFrame(catalog)[["slug", "title_ar", "domain", "language", "year", "law_number"]]
df = articles.merge(meta, on="slug", how="left")

print(f"{len(df):,} articles across {df['slug'].nunique()} documents")
df.head(3)

# %% [markdown]
"""## Articles per document"""

# %%
per_doc = df.groupby(["slug", "domain", "language"], as_index=False).size().sort_values("size")
fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(per_doc["slug"], per_doc["size"], color=[GREEN if l == "ar" else SAND for l in per_doc["language"]])
ax.set_xlabel("articles")
ax.set_title("Articles per document (green=ar, sand=fr)")
FIGURES.mkdir(parents=True, exist_ok=True)
fig.savefig(FIGURES / "articles_per_document.png", bbox_inches="tight")
per_doc

# %% [markdown]
"""## Article length distribution — legal articles cluster under ~800 chars; long tails
usually mean a header was missed (the warnings in the ingest log confirm)."""

# %%
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.hist(df["chars"].clip(upper=3000), bins=60, color=GREEN, alpha=0.85)
ax.axvline(df["chars"].median(), color=DARK, linestyle="--", label=f"median {df['chars'].median():.0f}")
ax.set_xlabel("chars per article")
ax.set_ylabel("articles")
ax.legend()
fig.savefig(FIGURES / "article_length.png", bbox_inches="tight")
df["chars"].describe().round(0)

# %% [markdown]
"""## Corpus by year and language — the D.O.C. (1913) vs the modern codes."""

# %%
by_year = meta.dropna(subset=["year"]).groupby(["year", "language"]).size().unstack(fill_value=0)
fig, ax = plt.subplots(figsize=(7, 3))
by_year.plot.barh(ax=ax, color={"ar": GREEN, "fr": SAND})
ax.set_xlabel("documents")
ax.set_title("Seed corpus by promulgation year")
fig.savefig(FIGURES / "corpus_by_year.png", bbox_inches="tight")
by_year

# %% [markdown]
"""## Chunk coverage — how much overlap-window chunking splits each law"""

# %%
chunks_path = Path("data/processed/chunks.jsonl")
if chunks_path.exists():
    chunks = pd.read_json(chunks_path, lines=True)
    ratio = (chunks.groupby("law_slug").size() / df.groupby("slug").size()).dropna()
    print(ratio.round(2).sort_values(ascending=False))
else:
    print("no chunks.jsonl yet")

print("\nfigures → docs/figures/")
