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


PAGES = Path("data/eval/pages.jsonl")


def test_ported_page_set_is_consistent():
    questions = load_questions(PAGES)
    assert len(questions) >= 250
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)), "duplicate question ids"
    assert {q["variety"] for q in questions} == {"msa", "darija", "arabizi", "other"}
    for q in questions:
        targets = q["expected_page_articles"]
        assert targets, f"{q['id']} has no page-level target"
        # the strict target is always one of the articles on the labelled pages
        assert all(a in targets for a in q.get("expected_articles", [])), q["id"]


def test_page_level_and_cited_article_metrics(monkeypatch):
    from conftest import make_hit

    from qanoun_api.eval import run as eval_run
    from qanoun_api.rag.retrieval import RetrievalResult

    hits = [make_hit(number="9", group_slug="moudawana"), make_hit(number="5", group_slug="moudawana")]
    monkeypatch.setattr(eval_run, "search", lambda q, k: RetrievalResult(q, q, hits))
    questions = [
        {  # article 5 is on the labelled page (rank 2); the cited article 4 is not retrieved
            "id": "p1", "question": "q", "variety": "darija",
            "expected_page_articles": [["moudawana", "4"], ["moudawana", "5"]],
            "expected_articles": [["moudawana", "4"]],
        },
        {"id": "p2", "question": "q", "variety": "msa", "expected_page_articles": [["doc", "1"]]},
    ]
    results = eval_run.evaluate_retrieval(questions, k=10, log=False)
    assert results[0].variety == "darija"  # the label wins over detection
    assert results[0].page_hit and results[0].page_rr == 0.5 and not results[0].article_hit
    metrics = eval_run.retrieval_metrics(results)
    assert metrics["page_scored"] == 2 and metrics["page_hit_rate"] == 0.5
    assert metrics["article_scored"] == 1 and metrics["article_hit_rate"] == 0.0
    split = eval_run.by_variety(results)
    assert set(split) == {"all", "msa", "darija"}
    assert split["darija"]["page_hit_rate"] == 1.0 and split["msa"]["page_hit_rate"] == 0.0


def test_rewrite_run_scores_the_chat_retrieval_path(monkeypatch):
    """A Darija question that only its MSA rewrite can find: raw misses, the /chat path hits."""
    from conftest import FakeLLM, make_hit

    from qanoun_api.eval import run as eval_run
    from qanoun_api.rag import retrieval
    from qanoun_api.rag.answer import Answerer
    from qanoun_api.rag.rewrite import QueryRewriter

    darija, msa = "شحال من ساعة خاصني نخدم فالسيمانة؟", "ما هي مدة الشغل القانونية في الأسبوع؟"
    wrong = make_hit(slug="family-code-ar", number="1", group_slug="moudawana")
    right = make_hit(slug="labour-code-ar", number="184", group_slug="labour-code")

    def fake_search(query, k=8, search_query=None, **_):
        hits = [right] if (search_query or query) == msa else [wrong]
        return retrieval.RetrievalResult(query, search_query or query, hits)

    monkeypatch.setattr(eval_run, "search", fake_search)
    monkeypatch.setattr(retrieval, "search", fake_search)
    questions = [{"id": "hours", "question": darija, "expected_articles": [["labour-code", "184"]]}]

    raw = eval_run.evaluate_retrieval(questions, k=10, log=False)
    assert not raw[0].article_hit

    llm = FakeLLM(reply=msa)
    answerer = Answerer(llm, rewriter=QueryRewriter(llm))
    rewritten = eval_run.evaluate_retrieval(questions, k=10, log=False, retrieve=answerer.retrieve)
    assert rewritten[0].article_hit
    assert len(llm.calls) == 1  # one rewrite call; MSA and French questions would make none


def test_report_shows_raw_and_rewritten_rows_per_variety(tmp_path: Path):
    from qanoun_api.eval import run as eval_run

    def page_result(hit: bool) -> QuestionResult:
        return QuestionResult(
            "drag-1", "chhal mn sa3a?", "arabizi", [], expected_page_articles=[["labour-code", "184"]],
            page_hit=hit, page_rr=1.0 if hit else 0.0,
        )

    page_runs = {"raw": [page_result(False)], "rewrite": [page_result(True)]}
    metrics = retrieval_metrics([])
    history = eval_run.record_history(tmp_path / "h.jsonl", metrics, 10)  # no page set: old shape
    history = eval_run.record_history(
        tmp_path / "h.jsonl", metrics, 10, rewrite=True,
        page_metrics=retrieval_metrics(page_runs["rewrite"]),
    )
    assert "page_hit_rate" not in history[0] and history[1]["page_hit_rate"] == 1.0

    report = tmp_path / "eval-report.md"
    write_report(
        report, [], metrics, answer_mode=False, history=history,
        rewritten_metrics=metrics, page_runs=page_runs,
    )
    text = report.read_text(encoding="utf-8")
    assert "## darija-rag question set (1 questions)" in text
    assert "| arabizi | 1 | 0.0 / 0.0 | 1.0 / 1.0 |" in text
    assert "| BAAI/bge-m3 | off | off | 0.0 / 0.0 | 0.0 / 0.0 | – | – |" in text  # no page set
    assert "| off | on | 0.0 / 0.0 | 0.0 / 0.0 | 1.0 / 1.0 |" in text


def test_retrieval_only_run_never_touches_an_llm(tmp_path: Path, monkeypatch):
    from conftest import make_hit

    from qanoun_api.eval import run as eval_run
    from qanoun_api.rag.retrieval import RetrievalResult

    def no_llm():
        raise AssertionError("--retrieval-only must not build an LLM client")

    monkeypatch.setattr(eval_run, "get_router", no_llm)
    monkeypatch.setattr(eval_run, "search", lambda q, k: RetrievalResult(q, q, [make_hit()]))
    code = eval_run.main([
        "--retrieval-only", "--history", str(tmp_path / "h.jsonl"),
        "--report", str(tmp_path / "report.md"),
    ])
    assert code == 0
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## darija-rag question set" in text and "+ rewrite hit@" not in text


def test_answer_summary_averages_only_graded_answers(tmp_path: Path):
    """Abstention rows carry no scores: they must not dilute the judge averages."""
    graded = {"faithfulness": 5, "grounding": 4, "completeness": 3}
    results = [
        QuestionResult("a", "q", "msa", ["family-code-ar"], judge=graded),
        QuestionResult("abstain-1", "q", "msa", [], judge={"abstention_ok": True}),
        QuestionResult("b", "q", "msa", ["labour-code-ar"], judge={"abstention_mismatch": True}),
    ]
    report = tmp_path / "eval-report.md"
    write_report(report, results, retrieval_metrics(results), answer_mode=True, judge_label="nvidia")
    text = report.read_text(encoding="utf-8")
    assert "{'faithfulness': 5.0, 'grounding': 4.0, 'completeness': 3.0} over 1 answers" in text
    assert "judged by nvidia" in text
    assert "Abstention: 1 correct refusals, 1 wrong calls" in text


def test_a_failing_judge_is_recorded_not_raised():
    from qanoun_api.eval.run import judge_answer

    class _Down:
        def chat(self, messages, **kwargs):
            raise RuntimeError("provider unreachable")

    assert judge_answer(_Down(), "q", "a", ["source"]) == {"error": "judge failed: provider unreachable"}
