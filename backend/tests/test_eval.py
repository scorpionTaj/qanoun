"""Eval harness internals: question loading, metrics math, report writing."""

from pathlib import Path

from qanoun_api.eval.run import (
    QuestionResult,
    load_questions,
    retrieval_metrics,
    write_report,
)

QUESTIONS = Path("data/eval/questions.jsonl")


def test_seed_questions_load_and_validate():
    questions = load_questions(QUESTIONS)
    assert len(questions) >= 25
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    for q in questions:
        assert q["question"]
        has_laws = bool(q.get("expected_laws"))
        assert has_laws or q.get("expected_abstain"), f"{q['id']} lacks expectations"


def test_seed_questions_cover_all_varieties():
    questions = load_questions(QUESTIONS)
    varieties = {q.get("variety_hint") for q in questions}
    assert {"msa", "darija", "arabizi", "other"} <= varieties
    assert any(q.get("expected_abstain") for q in questions)


def test_retrieval_metrics_math():
    results = [
        QuestionResult("a", "q", "msa", ["family-code-ar"], hit_at_k=True, reciprocal_rank=1.0),
        QuestionResult("b", "q", "msa", ["labour-code-ar"], hit_at_k=False, reciprocal_rank=0.0),
    ]
    metrics = retrieval_metrics(results)
    assert metrics["hit_rate"] == 0.5
    assert metrics["mrr"] == 0.5
    assert metrics["scored"] == 2


def test_retrieval_metrics_ignores_abstention_probes_and_errors():
    results = [
        QuestionResult("a", "q", "msa", ["family-code-ar"], hit_at_k=True, reciprocal_rank=0.5),
        QuestionResult("b", "q", "msa", []),  # abstention probe: not scored
        QuestionResult("c", "q", "msa", ["labour-code-ar"], error="boom"),
    ]
    metrics = retrieval_metrics(results)
    assert metrics["scored"] == 1
    assert metrics["hit_rate"] == 1.0


def test_write_report_produces_markdown(tmp_path: Path):
    results = [
        QuestionResult("a", "q", "msa", ["family-code-ar"], hit_at_k=True, reciprocal_rank=1.0),
        QuestionResult("abstain-1", "q", "darija", [], judge={"abstention_ok": True}),
    ]
    metrics = retrieval_metrics(results)
    report = tmp_path / "eval-report.md"
    write_report(report, results, metrics, answer_mode=False)
    text = report.read_text(encoding="utf-8")
    assert "# Qanoun evaluation report" in text
    assert "| a | msa | family-code-ar | ✓ | 1.00 |" in text
    assert "Abstention probes" in text


def test_article_level_metrics_and_history(tmp_path, monkeypatch):
    from conftest import make_hit

    from qanoun_api.eval import run as eval_run
    from qanoun_api.rag.retrieval import RetrievalResult

    hits = [make_hit(number="132", group_slug="moudawana"), make_hit(number="133", group_slug="moudawana")]
    monkeypatch.setattr(eval_run, "search", lambda q, k: RetrievalResult(q, q, hits))
    questions = [{"id": "idda", "question": "q", "expected_articles": [["moudawana", "133"]]}]
    results = eval_run.evaluate_retrieval(questions, k=10, log=False)
    assert results[0].article_hit and results[0].article_rr == 0.5
    metrics = eval_run.retrieval_metrics(results)
    assert metrics["article_hit_rate"] == 1.0 and metrics["article_mrr"] == 0.5

    history = eval_run.record_history(tmp_path / "h.jsonl", metrics, 10)
    history = eval_run.record_history(tmp_path / "h.jsonl", metrics, 10)
    assert len(history) == 2 and history[-1]["article_mrr"] == 0.5
