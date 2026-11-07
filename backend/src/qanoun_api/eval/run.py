"""Retrieval + grounded-answer evaluation with LLM-as-judge (adapted from darija-rag).

    uv run --project backend python -m qanoun_api.eval.run                  # full run (LLM needed)
    uv run --project backend python -m qanoun_api.eval.run --retrieval-only # metrics without LLM
    uv run --project backend python -m qanoun_api.eval.run --report docs/eval-report.md

Questions live in data/eval/questions.jsonl. Expectations are law-level (which corpus
document should surface) plus optional answer keywords — article-level expectations rot
when texts change, law-level ones survive re-ingestion.
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from qanoun_api.rag.answer import Answerer
from qanoun_api.rag.llm import LLMClient
from qanoun_api.rag.retrieval import search
from qanoun_api.rag.rewrite import detect_variety

DEFAULT_K = 10


@dataclass
class QuestionResult:
    id: str
    question: str
    variety: str
    expected_laws: list[str]
    law_hits: list[str] = field(default_factory=list)
    hit_at_k: bool = False
    reciprocal_rank: float = 0.0
    answer: str = ""
    abstained: bool = False
    judge: dict | None = None
    error: str = ""


def load_questions(path: Path) -> list[dict]:
    questions = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def evaluate_retrieval(questions: list[dict], k: int, log: bool = True) -> list[QuestionResult]:
    results = []
    for q in questions:
        expected = q.get("expected_laws", [])
        res = QuestionResult(
            id=q["id"], question=q["question"], variety=detect_variety(q["question"]),
            expected_laws=expected,
        )
        if not expected:  # abstention probes: nothing should be retrieved with authority
            results.append(res)
            continue
        try:
            hits = search(q["question"], k=k).hits
        except Exception as exc:
            res.error = f"retrieval failed: {exc}"
            results.append(res)
            continue
        res.law_hits = [hit.law_slug for hit in hits]
        for rank, hit in enumerate(hits, start=1):
            if hit.law_slug in expected:
                res.hit_at_k = True
                res.reciprocal_rank = 1.0 / rank
                break
        if log:
            status = "✓" if res.hit_at_k else "✗"
            print(f"  {status} {res.id} ({res.variety}) rr={res.reciprocal_rank:.2f}")
        results.append(res)
        time.sleep(0.0)  # keep the loop structure explicit for future rate limits
    return results


def retrieval_metrics(results: list[QuestionResult]) -> dict:
    scored = [r for r in results if r.expected_laws and not r.error]
    n = len(scored) or 1
    return {
        "questions": len(results),
        "scored": len(scored),
        "hit_at_k": sum(r.hit_at_k for r in scored),
        "hit_rate": round(sum(r.hit_at_k for r in scored) / n, 3),
        "mrr": round(sum(r.reciprocal_rank for r in scored) / n, 3),
    }


_JUDGE_SYSTEM = (
    "You judge answers about Moroccan law. Given a question, an answer, and the numbered "
    "sources the answer was generated from, score: faithfulness (does it only claim what "
    "sources say), grounding (are citations [n] real and relevant), completeness (does it "
    "answer the question). Reply with JSON only: "
    '{"faithfulness": 1-5, "grounding": 1-5, "completeness": 1-5, "notes": "one line"}'
)


def judge_answer(llm: LLMClient, question: str, answer_text: str, sources: list[str]) -> dict:
    numbered = "\n\n".join(f"[{i}] {s[:600]}" for i, s in enumerate(sources, start=1))
    user = f"Question: {question}\n\nAnswer: {answer_text}\n\nSources:\n{numbered}"
    reply = llm.chat(
        [{"role": "system", "content": _JUDGE_SYSTEM}, {"role": "user", "content": user}],
        max_tokens=200,
    )
    try:
        start, end = reply.index("{"), reply.rindex("}") + 1
        return json.loads(reply[start:end])
    except ValueError:
        return {"error": f"unparseable judge reply: {reply[:120]}"}


def evaluate_answers(questions: list[dict], results: list[QuestionResult], answerer: Answerer) -> None:
    llm = answerer.llm
    by_id = {r.id: r for r in results}
    for q in questions:
        res = by_id[q["id"]]
        if res.error or not q.get("ask", True):
            continue
        try:
            answer = answerer.ask(q["question"])
        except Exception as exc:
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


def write_report(
    path: Path, results: list[QuestionResult], metrics: dict, answer_mode: bool
) -> None:
    lines = [
        "# Qanoun evaluation report",
        "",
        f"- Questions: {metrics['questions']} (scored for retrieval: {metrics['scored']})",
        f"- Retrieval hit@{DEFAULT_K}: **{metrics['hit_rate']}** (MRR {metrics['mrr']})",
    ]
    if answer_mode:
        judged = [r for r in results if r.judge and "error" not in (r.judge or {})]
        if judged:
            avg = {
                key: round(sum(r.judge[key] for r in judged if key in r.judge) / len(judged), 2)
                for key in ("faithfulness", "grounding", "completeness")
            }
            lines.append(f"- LLM-judge averages: {avg} over {len(judged)} answers")
    lines += ["", "## Per-question retrieval", "", "| id | variety | expected | hit | rr |", "|---|---|---|---|---|"]
    for r in results:
        if r.expected_laws:
            lines.append(
                f"| {r.id} | {r.variety} | {', '.join(r.expected_laws)} | "
                f"{'✓' if r.hit_at_k else '✗'} | {r.reciprocal_rank:.2f} |"
            )
    abstain_probes = [r for r in results if not r.expected_laws and r.judge]
    if abstain_probes:
        lines += ["", "## Abstention probes", ""]
        for r in abstain_probes:
            lines.append(f"- {r.id}: {'✓ abstained' if r.judge.get('abstention_ok') else '✗ answered'}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qanoun-eval", description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/eval/questions.jsonl"))
    parser.add_argument("--report", type=Path, default=Path("docs/eval-report.md"))
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--retrieval-only", action="store_true")
    args = parser.parse_args(argv)

    questions = load_questions(args.questions)
    print(f"evaluating {len(questions)} questions (k={args.k})")
    results = evaluate_retrieval(questions, args.k)
    metrics = retrieval_metrics(results)
    print(f"hit@{args.k}={metrics['hit_rate']} mrr={metrics['mrr']}")

    if not args.retrieval_only:
        answerer = Answerer(LLMClient.from_env(), k=5)
        print("answering + judging…")
        evaluate_answers(questions, results, answerer)

    write_report(args.report, results, metrics, answer_mode=not args.retrieval_only)
    print(f"report → {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
