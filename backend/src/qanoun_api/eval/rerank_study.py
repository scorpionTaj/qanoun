"""Which reranking setup raises MRR, not only hit@10? One run scores them all.

    uv run --project backend python -m qanoun_api.eval.rerank_study \\
        --model jina-reranker-v2-base-multilingual --pool 20 [--limit 30]

For every eval question (the three sets run.py uses, as typed) it fetches the fused top
`--pool` once and has the reranker score each candidate once. The scores are cached in
`--cache`, so re-running costs no API tokens. From those it evaluates, on the same
candidates:

- `fused`: today's order (the baseline);
- `replace@N`: the fused top N re-ordered by the reranker alone;
- `blend@N/k/w`: the fused top N re-ordered by a weighted reciprocal-rank fusion of the fused
  rank and the reranker's rank, w on the reranker. A reranker that is right most of the time
  but sometimes buries an exact match then only moves good candidates up, not bad ones.

Prints one table row per strategy (law / article / page hit@10 and MRR) and the API tokens
used, which is what the reranker would cost per question in production.
"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from qanoun_api.db import close_pool
from qanoun_api.eval.run import evaluate_retrieval, load_questions, retrieval_metrics
from qanoun_api.rag.retrieval import JinaReranker, RetrievalResult, search

SETS = ("data/eval/questions.jsonl", "data/eval/articles.jsonl", "data/eval/pages.jsonl")
K = 10


def passage(hit) -> str:
    return f"{hit.law_title} — {hit.article_number}: {hit.text}"


def blend(order: list[int], scores: list[float], k: float, weight: float) -> list[int]:
    """Indexes of `order` (fused ranking) re-ranked by weighted RRF with the reranker's ranks."""
    by_score = sorted(order, key=lambda i: -scores[i])
    rr_rank = {i: r for r, i in enumerate(by_score, start=1)}
    fused_rank = {i: r for r, i in enumerate(order, start=1)}
    value = {i: (1 - weight) / (k + fused_rank[i]) + weight / (k + rr_rank[i]) for i in order}
    return sorted(order, key=lambda i: -value[i])


def strategies(pools: list[int]) -> dict[str, callable]:
    out = {"fused": lambda n, scores: list(range(n))}
    for size in pools:
        out[f"replace@{size}"] = lambda n, scores, size=size: (
            sorted(range(min(size, n)), key=lambda i: -scores[i]) + list(range(min(size, n), n))
        )
        for k in (2, 10, 60):
            for weight in (0.5, 0.7):
                out[f"blend@{size}/k{k}/w{weight}"] = lambda n, scores, size=size, k=k, weight=weight: (
                    blend(list(range(min(size, n))), scores, k, weight) + list(range(min(size, n), n))
                )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default="jina-reranker-v2-base-multilingual")
    parser.add_argument("--pool", type=int, default=20, help="fused candidates scored per question")
    parser.add_argument("--limit", type=int, help="only the first N questions of each set (a pilot)")
    parser.add_argument("--cache", type=Path, default=Path("data/eval/rerank-cache.json"))
    args = parser.parse_args()

    cache = json.loads(args.cache.read_text(encoding="utf-8")) if args.cache.exists() else {}
    reranker = JinaReranker(args.model)
    pools: dict[str, RetrievalResult] = {}
    scores: dict[str, list[float]] = {}
    questions = {path: load_questions(Path(path))[: args.limit] for path in SETS}
    for path, items in questions.items():
        for q in items:
            text = q["question"]
            if text in pools:
                continue
            pools[text] = result = search(text, k=args.pool)
            key = f"{args.model}|{args.pool}|{text}"
            cached = cache.get(key)
            if cached and cached["keys"] == [f"{h.group_slug}:{h.article_number}" for h in result.hits]:
                scores[text] = cached["scores"]
                continue
            scores[text] = reranker.predict([(text, passage(h)) for h in result.hits])
            cache[key] = {"keys": [f"{h.group_slug}:{h.article_number}" for h in result.hits],
                          "scores": scores[text]}  # fmt: skip
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    close_pool()

    asked = len(pools)
    print(f"{asked} questions, pool {args.pool}, model {args.model}: {reranker.tokens} API tokens "
          f"this run ({reranker.tokens // max(asked, 1)} per question)\n")  # fmt: skip
    header = "| strategy | law hit / MRR | article hit / MRR | page hit / MRR |"
    print(header + "\n|---|---|---|---|")
    for name, order_of in strategies(sorted({10, args.pool})).items():

        def retrieve(question: str, k: int, order_of=order_of) -> RetrievalResult:
            pool = pools[question]
            order = order_of(len(pool.hits), scores[question])
            return replace(pool, hits=[pool.hits[i] for i in order][:k])

        cells = []
        for path in SETS:
            m = retrieval_metrics(evaluate_retrieval(questions[path], K, log=False, retrieve=retrieve))
            metric = {"questions": ("hit_rate", "mrr"), "articles": ("article_hit_rate", "article_mrr"),
                      "pages": ("page_hit_rate", "page_mrr")}[Path(path).stem]  # fmt: skip
            cells.append(f"{m[metric[0]]:.3f} / {m[metric[1]]:.3f}")
        print(f"| {name} | " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
