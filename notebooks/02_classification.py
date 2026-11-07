# %% [markdown]
"""
# Qanoun — Domain classification experiment

The catalog assigns domains manually for the seed laws. This notebook tests the keyword
classifier (`qanoun_pipeline.classify`) against that ground truth — the same classifier
that will auto-route freshly scraped Bulletin Officiel texts later.

Run:
    uv run --project pipeline --with pandas --with matplotlib python notebooks/02_classification.py
"""

# %%
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from qanoun_pipeline.classify import domain_votes, suggest_domain

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})

ARTICLES = Path("data/processed/articles.jsonl")
CATALOG = Path("data/catalog/laws.yaml")

if not ARTICLES.exists():
    raise SystemExit("no articles.jsonl — run the ingest first")

# %% [markdown]
"""## Ground truth vs keyword prediction, per document"""

# %%
articles = pd.read_json(ARTICLES, lines=True).rename(columns={"law_slug": "slug"})
meta = pd.DataFrame(yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["entries"])[
    ["slug", "domain"]
]
df = articles.merge(meta, on="slug", how="left")

rows = []
for slug, group in df.groupby("slug"):
    # One vote profile per document: concatenated article text is the unit a scraper
    # would classify before ingestion.
    text = " ".join(group["text"].head(300))
    predicted = suggest_domain(text)
    votes = domain_votes(text)
    rows.append(
        {
            "slug": slug,
            "true_domain": group["domain"].iloc[0],
            "predicted": predicted,
            "top_votes": max(votes, key=votes.get) if votes else None,
            "votes_for_true": votes.get(group["domain"].iloc[0], 0),
        }
    )
results = pd.DataFrame(rows)
results["correct"] = results["true_domain"] == results["predicted"]
results

# %% [markdown]
"""## Agreement rate — expect high for family/labour, lower for civil (the D.O.C. shares
contract vocabulary with housing and commercial texts)."""

# %%
accuracy = results["correct"].mean()
print(f"document-level agreement: {accuracy:.0%} ({results['correct'].sum()}/{len(results)})")
print("\nmisses:")
print(results[~results["correct"]][["slug", "true_domain", "predicted"]].to_string(index=False))

# %% [markdown]
"""## Keyword votes per document (the evidence behind each prediction)"""

# %%
vote_matrix = pd.DataFrame(
    [domain_votes(" ".join(g["text"].head(200))) for _, g in df.groupby("slug")],
    index=sorted(df["slug"].unique()),
)
fig, ax = plt.subplots(figsize=(8, 0.6 * len(vote_matrix) + 1.5))
im = ax.imshow(vote_matrix.values, cmap="Greens", aspect="auto")
ax.set_xticks(range(len(vote_matrix.columns)), vote_matrix.columns, rotation=45, ha="right")
ax.set_yticks(range(len(vote_matrix.index)), vote_matrix.index)
fig.colorbar(im, ax=ax, shrink=0.7, label="keyword hits")
ax.set_title("Domain keyword evidence per document")
Path("docs/figures").mkdir(parents=True, exist_ok=True)
fig.savefig("docs/figures/classification_votes.png", bbox_inches="tight")
vote_matrix
