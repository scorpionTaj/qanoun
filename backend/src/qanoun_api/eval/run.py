"""Retrieval + grounded-answer evaluation with LLM-as-judge (adapted from darija-rag).

    uv run --project backend python -m qanoun_api.eval.run                  # full run (LLM needed)
    uv run --project backend python -m qanoun_api.eval.run --retrieval-only # metrics without LLM
    uv run --project backend python -m qanoun_api.eval.run --retrieval-only --rewrite
    uv run --project backend python -m qanoun_api.eval.run --report docs/eval-report.md

Questions live in data/eval/questions.jsonl (law-level: which document should surface),
data/eval/articles.jsonl (article-level: [law group, article number] that must
surface — precise, but to re-check when texts are re-ingested) and data/eval/pages.jsonl
(darija-rag's set, labelled by page: see scripts/port_darija_rag_eval.py). Each run is
appended to data/eval/history.jsonl and the report shows the trend.

Retrieval is always scored on the raw question. With an LLM (`--rewrite`, or a full run) it
is scored a second time the way /chat retrieves: Darija and Arabizi rewritten to MSA, both
searches merged. That second row is the one users get.
"""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from qanoun_api.config import SETTINGS
from qanoun_api.rag.answer import Answerer
from qanoun_api.rag.llm import ChatModel
from qanoun_api.rag.providers import get_router
from qanoun_api.rag.retrieval import RetrievalResult, search
from qanoun_api.rag.rewrite import QueryRewriter, detect_variety

DEFAULT_K = 10
VARIETIES = ("msa", "darija", "arabizi", "other")


@dataclass
class QuestionResult:
    id: str
    question: str
    variety: str
    expected_laws: list[str]
    expected_articles: list[list[str]] = field(default_factory=list)  # [[group, number]]
    article_hit: bool = False
    article_rr: float = 0.0
    law_hits: list[str] = field(default_factory=list)
    hit_at_k: bool = False
    reciprocal_rank: float = 0.0
    answer: str = ""
    abstained: bool = False
    judge: dict | None = None
    error: str = ""
    expected_page_articles: list[list[str]] = field(default_factory=list)  # any one counts
    page_hit: bool = False
    page_rr: float = 0.0


def load_questions(path: Path) -> list[dict]:
    questions = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def _reciprocal_rank(found: list, targets: list) -> float:
    """1/rank of the first found item that is a target; 0.0 when none is."""
    return next((1.0 / rank for rank, item in enumerate(found, start=1) if item in targets), 0.0)


def evaluate_retrieval(
    questions: list[dict],
    k: int,
    log: bool = True,
    retrieve: Callable[[str, int], RetrievalResult] | None = None,
) -> list[QuestionResult]:
    """Score each question's top-k. `retrieve` defaults to the raw hybrid search; pass
    `Answerer.retrieve` (with a rewriter) to score what /chat serves."""
    results = []
    for q in questions:
        expected = q.get("expected_laws", [])
        articles = [tuple(a) for a in q.get("expected_articles", [])]
        page_articles = [tuple(a) for a in q.get("expected_page_articles", [])]
        res = QuestionResult(
            id=q["id"], question=q["question"],
            variety=q.get("variety") or detect_variety(q["question"]),
            expected_laws=expected, expected_articles=[list(a) for a in articles],
            expected_page_articles=[list(a) for a in page_articles],
        )
        if not (expected or articles or page_articles):  # abstention probes: nothing to find
            results.append(res)
            continue
        try:
            found = retrieve(q["question"], k) if retrieve else search(q["question"], k=k)
        except Exception as exc:  # noqa: BLE001 — record per-question failures in the report
            res.error = f"retrieval failed: {exc}"
            results.append(res)
            continue
        res.law_hits = [hit.law_slug for hit in found.hits]
        found_articles = [(hit.group_slug, hit.article_number) for hit in found.hits]
        res.reciprocal_rank = _reciprocal_rank(res.law_hits, expected)
        res.hit_at_k = res.reciprocal_rank > 0
        res.article_rr = _reciprocal_rank(found_articles, articles)
        res.article_hit = res.article_rr > 0
        res.page_rr = _reciprocal_rank(found_articles, page_articles)
        res.page_hit = res.page_rr > 0
        if log:
            if articles:
                ok, rr = res.article_hit, res.article_rr
            elif page_articles:
                ok, rr = res.page_hit, res.page_rr
            else:
                ok, rr = res.hit_at_k, res.reciprocal_rank
            print(f"  {'✓' if ok else '✗'} {res.id} ({res.variety}) rr={rr:.2f}")
        results.append(res)
    return results


def retrieval_metrics(results: list[QuestionResult]) -> dict:
    scored = [r for r in results if r.expected_laws and not r.error]
    n = len(scored) or 1
    by_article = [r for r in results if r.expected_articles and not r.error]
    m = len(by_article) or 1
    by_page = [r for r in results if r.expected_page_articles and not r.error]
    p = len(by_page) or 1
    return {
        "questions": len(results),
        "scored": len(scored),
        "hit_at_k": sum(r.hit_at_k for r in scored),
        "hit_rate": round(sum(r.hit_at_k for r in scored) / n, 3),
        "mrr": round(sum(r.reciprocal_rank for r in scored) / n, 3),
        "article_scored": len(by_article),
        "article_hit_rate": round(sum(r.article_hit for r in by_article) / m, 3),
        "article_mrr": round(sum(r.article_rr for r in by_article) / m, 3),
        "page_scored": len(by_page),
        "page_hit_rate": round(sum(r.page_hit for r in by_page) / p, 3),
        "page_mrr": round(sum(r.page_rr for r in by_page) / p, 3),
        "errors": sum(bool(r.error) for r in results),
    }


def by_variety(results: list[QuestionResult]) -> dict[str, dict]:
    """`retrieval_metrics` for all questions and for each variety that has some."""
    groups = {"all": results}
    groups |= {v: [r for r in results if r.variety == v] for v in VARIETIES}
    return {name: retrieval_metrics(group) for name, group in groups.items() if group}


def record_history(
    path: Path, metrics: dict, k: int, rewrite: bool = False, page_metrics: dict | None = None
) -> list[dict]:
    """Append this run to the history file and return all runs (oldest first).

    `page_metrics` are the darija-rag set's: its page-level rate, and its strict
    (cited-article) rate under `cited_*`.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        commit = ""

    entry = {
        "time": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "k": k,
        "reranker": os.environ.get("QANOUN_RERANKER", "") or "off",
        "rewrite": "on" if rewrite else "off",
        **{key: metrics[key] for key in ("hit_rate", "mrr", "article_hit_rate", "article_mrr")},
    }
    if page_metrics and page_metrics["page_scored"]:
        entry |= {
            "page_hit_rate": page_metrics["page_hit_rate"],
            "page_mrr": page_metrics["page_mrr"],
            "cited_hit_rate": page_metrics["article_hit_rate"],
            "cited_mrr": page_metrics["article_mrr"],
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


_JUDGE_SYSTEM = (
    "You judge answers about Moroccan law. Given a question, an answer, and the numbered "
    "sources the answer was generated from, score: faithfulness (does it only claim what "
    "sources say), grounding (are citations [n] real and relevant), completeness (does it "
    "answer the question). Reply with JSON only: "
    '{"faithfulness": 1-5, "grounding": 1-5, "completeness": 1-5, "notes": "one line"}'
)


def judge_answer(llm: ChatModel, question: str, answer_text: str, sources: list[str]) -> dict:
    numbered = "\n\n".join(f"[{i}] {s[:600]}" for i, s in enumerate(sources, start=1))
    user = f"Question: {question}\n\nAnswer: {answer_text}\n\nSources:\n{numbered}"
    try:
        # Room for reasoning models, whose hidden thinking counts against max_tokens.
        reply = llm.chat(
            [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": user}],
            max_tokens=1500,
        )
    except Exception as exc:  # noqa: BLE001 — one failed grade must not lose the whole run
        return {"error": f"judge failed: {exc}"[:300]}
    try:
        start, end = reply.index("{"), reply.rindex("}") + 1
        return json.loads(reply[start:end])
    except ValueError:
        return {"error": f"unparseable judge reply: {reply[:120]}"}


def evaluate_answers(
    questions: list[dict],
    results: list[QuestionResult],
    answerer: Answerer,
    judge: ChatModel | None = None,
) -> None:
    """Answer and judge. `judge` defaults to the answering model, which flatters the scores:
    pass another provider's model to have answers graded by a different one."""
    llm = judge or answerer.llm
    by_id = {r.id: r for r in results}
    for q in questions:
        res = by_id[q["id"]]
        if res.error or not q.get("ask", True):
            continue
        try:
            answer = answerer.ask(q["question"])
        except Exception as exc:  # noqa: BLE001 — record per-question failures in the report
            res.error = f"answer failed: {exc}"
            continue
        res.answer = answer.text
        res.abstained = answer.abstained
        expected_abstain = q.get("expected_abstain", False)
        if expected_abstain != answer.abstained:
            res.judge = {
                "abstention_mismatch": True,
                "notes": f"expected {'abstention' if expected_abstain else 'an answer'}",
            }
            continue
        if answer.abstained:
            res.judge = {"abstention_ok": True}
            continue
        keywords = q.get("expected_keywords", [])
        missing = [k for k in keywords if k not in answer.text]
        res.judge = judge_answer(
            llm, q["question"], answer.text, [hit.text[:600] for hit in answer.sources]
        )
        if missing:
            res.judge["missing_keywords"] = missing


def _page_set_section(page_runs: dict[str, list[QuestionResult]]) -> list[str]:
    """The darija-rag set by variety: page-level and strict, raw and (if run) rewritten."""
    raw = by_variety(page_runs["raw"])
    rewritten = by_variety(page_runs["rewrite"]) if "rewrite" in page_runs else None
    lines = [
        "", f"## darija-rag question set ({raw['all']['page_scored']} questions)", "",
        (
            "Ported from darija-rag (`scripts/port_darija_rag_eval.py`). **Page-level**: any "
            "article printed on a labelled page is in the top 10, which is darija-rag's own "
            "criterion. **Cited article**: the article the reference answer cites is in the top "
            "10. *Raw* searches the question as typed"
            + (
                "; *+ rewrite* is what /chat does (Darija and Arabizi rewritten to MSA, both "
                "searches merged)."
                if rewritten
                else ", without the Darija/Arabizi rewriting /chat applies (run with `--rewrite`)."
            )
        ),
    ]
    for title, n_key, hit_key, mrr_key in (
        ("Page-level", "page_scored", "page_hit_rate", "page_mrr"),
        ("Cited article", "article_scored", "article_hit_rate", "article_mrr"),
    ):
        header = f"| {title} | n | raw hit@{DEFAULT_K} / MRR |"
        header += f" + rewrite hit@{DEFAULT_K} / MRR |" if rewritten else ""
        lines += ["", header, "|---|---|---|" + ("---|" if rewritten else "")]
        for variety, m in raw.items():
            row = f"| {variety} | {m[n_key]} | {m[hit_key]} / {m[mrr_key]} |"
            if rewritten:
                row += f" {rewritten[variety][hit_key]} / {rewritten[variety][mrr_key]} |"
            lines.append(row)
    final = page_runs.get("rewrite", page_runs["raw"])
    misses = [r for r in final if r.expected_page_articles and not r.page_hit and not r.error]
    if misses:
        lines += ["", f"Page-level misses ({'+ rewrite' if rewritten else 'raw'}):", ""]
        lines += [f"- {r.id} ({r.variety}): {r.question}" for r in misses]
    return lines


def _answer_summary(results: list[QuestionResult], judge_label: str) -> list[str]:
    """Judge averages over the answers that were graded, and the abstention outcomes."""
    graded = [r.judge for r in results if r.judge and "faithfulness" in r.judge]
    lines = []
    if graded:
        avg = {
            key: round(sum(j.get(key, 0) for j in graded) / len(graded), 2)
            for key in ("faithfulness", "grounding", "completeness")
        }
        by = f"judged by {judge_label}" if judge_label else "judged by the answering model"
        lines.append(f"- LLM-judge averages (1–5): {avg} over {len(graded)} answers, {by}")
    decided = [r.judge for r in results if r.judge and "faithfulness" not in r.judge]
    wrong = sum(bool(j.get("abstention_mismatch")) for j in decided)
    ungraded = sum("error" in j for j in decided)
    correct = sum(bool(j.get("abstention_ok")) for j in decided)
    if correct or wrong:
        lines.append(
            f"- Abstention: {correct} correct refusals, {wrong} wrong calls "
            "(answered an out-of-scope question, or refused an answerable one)"
        )
    if ungraded:
        lines.append(f"- {ungraded} answers were not graded (the judge failed or replied without JSON)")
    return lines


def write_report(
    path: Path,
    results: list[QuestionResult],
    metrics: dict,
    answer_mode: bool,
    history: list[dict] | None = None,
    rewritten_metrics: dict | None = None,
    page_runs: dict[str, list[QuestionResult]] | None = None,
    judge_label: str = "",
) -> None:
    """`results` fill the per-question tables: the rewritten run when there is one.
    `metrics` are the raw run's; `rewritten_metrics` the /chat-path run's."""
    lines = [
        "# Qanoun evaluation report",
        "",
        f"- Questions: {metrics['questions']} (scored for retrieval: {metrics['scored']})",
        f"- Law-level hit@{DEFAULT_K}: **{metrics['hit_rate']}** (MRR {metrics['mrr']})",
        (
            f"- Article-level hit@{DEFAULT_K}: **{metrics['article_hit_rate']}** "
            f"(MRR {metrics['article_mrr']}, {metrics['article_scored']} questions)"
        ),
    ]
    if rewritten_metrics:
        lines.append(
            f"- With Darija/Arabizi rewriting (what /chat serves): law-level "
            f"**{rewritten_metrics['hit_rate']}** (MRR {rewritten_metrics['mrr']}), article-level "
            f"**{rewritten_metrics['article_hit_rate']}** (MRR {rewritten_metrics['article_mrr']})"
        )
    failed = (rewritten_metrics or metrics)["errors"]
    if failed:
        lines.append(f"- **{failed} question(s) failed** and are left out of the rates above")
    if answer_mode:
        lines += _answer_summary(results, judge_label)
    if history:
        lines += ["", "## History (last 10 runs)", "",
                  ("| when (UTC) | commit | reranker | rewrite | law hit / MRR | article hit / MRR "
                   "| page hit / MRR | cited hit / MRR |"),
                  "|---|---|---|---|---|---|---|---|"]
        for run in history[-10:]:
            page = f"{run['page_hit_rate']} / {run['page_mrr']}" if "page_mrr" in run else "–"
            cited = f"{run['cited_hit_rate']} / {run['cited_mrr']}" if "cited_mrr" in run else "–"
            lines.append(
                f"| {run['time']} | {run['commit']} | {run['reranker']} | {run.get('rewrite', 'off')} | "
                f"{run['hit_rate']} / {run['mrr']} | {run['article_hit_rate']} / {run['article_mrr']} | "
                f"{page} | {cited} |"
            )
    if page_runs and page_runs["raw"]:
        lines += _page_set_section(page_runs)
    lines += ["", "## Per-question retrieval", "", "| id | variety | expected | hit | rr |", "|---|---|---|---|---|"]
    for r in results:
        if r.expected_laws:
            lines.append(
                f"| {r.id} | {r.variety} | {', '.join(r.expected_laws)} | "
                f"{'✓' if r.hit_at_k else '✗'} | {r.reciprocal_rank:.2f} |"
            )
    article_rows = [r for r in results if r.expected_articles]
    if article_rows:
        lines += ["", "## Per-question retrieval (article level)", "",
                  "| id | variety | expected | hit | rr |", "|---|---|---|---|---|"]
        for r in article_rows:
            expected = ", ".join(f"{g} {n}" for g, n in r.expected_articles)
            lines.append(
                f"| {r.id} | {r.variety} | {expected} | "
                f"{'✓' if r.article_hit else '✗'} | {r.article_rr:.2f} |"
            )
    abstain_probes = [r for r in results if not r.expected_laws and not r.expected_articles and r.judge]
    if abstain_probes:
        lines += ["", "## Abstention probes", ""]
        for r in abstain_probes:
            lines.append(f"- {r.id}: {'✓ abstained' if r.judge.get('abstention_ok') else '✗ answered'}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qanoun-eval", description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/eval/questions.jsonl"))
    parser.add_argument("--articles", type=Path, default=Path("data/eval/articles.jsonl"))
    parser.add_argument("--pages", type=Path, default=Path("data/eval/pages.jsonl"))
    parser.add_argument("--history", type=Path, default=Path("data/eval/history.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("docs/eval-report.md"))
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--retrieval-only", action="store_true", help="skip answers and judging")
    parser.add_argument(
        "--rewrite", action="store_true",
        help="also score retrieval the way /chat does (needs an LLM; implied by a full run)",
    )
    parser.add_argument(
        "--judge", metavar="PROVIDER[:MODEL]", default="",
        help="grade answers with this provider (gemini, openrouter, nvidia, local) instead of "
        "the answering one; it never falls back to another provider",
    )
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    article_questions = load_questions(args.articles) if args.articles.exists() else []
    page_questions = load_questions(args.pages) if args.pages.exists() else []
    seed = questions + article_questions
    print(f"evaluating {len(seed)} + {len(page_questions)} questions (k={args.k})")

    def summarize(label: str, metrics: dict, page_metrics: dict) -> None:
        print(
            f"{label}: law hit@{args.k}={metrics['hit_rate']} mrr={metrics['mrr']} · "
            f"article hit@{args.k}={metrics['article_hit_rate']} mrr={metrics['article_mrr']} · "
            f"page hit@{args.k}={page_metrics['page_hit_rate']} mrr={page_metrics['page_mrr']}"
        )

    results = evaluate_retrieval(seed, args.k)
    page_runs = {"raw": evaluate_retrieval(page_questions, args.k)}
    metrics, page_metrics = retrieval_metrics(results), retrieval_metrics(page_runs["raw"])
    summarize("raw", metrics, page_metrics)
    history = record_history(args.history, metrics, args.k, page_metrics=page_metrics)

    rewritten_metrics = None
    if args.rewrite or not args.retrieval_only:
        llm = get_router().bind()  # same providers + fallback as /chat
        rewriter = QueryRewriter(llm, cache_path=SETTINGS.rewrite_cache)
        answerer = Answerer(llm, k=5, rewriter=rewriter)
        print("retrieval with Darija/Arabizi rewriting…")
        results = evaluate_retrieval(seed, args.k, retrieve=answerer.retrieve)
        page_runs["rewrite"] = evaluate_retrieval(page_questions, args.k, retrieve=answerer.retrieve)
        rewritten_metrics = retrieval_metrics(results)
        page_metrics = retrieval_metrics(page_runs["rewrite"])
        summarize("+ rewrite", rewritten_metrics, page_metrics)
        history = record_history(
            args.history, rewritten_metrics, args.k, rewrite=True, page_metrics=page_metrics
        )
        if not args.retrieval_only:
            judge = None
            if args.judge:
                provider, _, model = args.judge.partition(":")
                judge = get_router().bind(provider, model)
            print("answering + judging…")
            # law-level set only
            evaluate_answers(questions, results[: len(questions)], answerer, judge)

    write_report(
        args.report, results, metrics, answer_mode=not args.retrieval_only, history=history,
        rewritten_metrics=rewritten_metrics, page_runs=page_runs, judge_label=args.judge,
    )
    print(f"report → {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
