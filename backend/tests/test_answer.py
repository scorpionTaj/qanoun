from conftest import make_hit

from qanoun_api.rag.answer import (
    ABSTENTION,
    DISCLAIMER,
    NO_ANSWER,
    Answer,
    build_messages,
    parse_citations,
    source_label,
)


def test_parse_citations_extracts_and_dedupes():
    text = "الزواج عقد [1] ويشترط الركن [2][1]."
    assert parse_citations(text, 3) == [0, 1]


def test_parse_citations_ignores_out_of_range():
    assert parse_citations("غير موجود [9]", 2) == []


def test_build_messages_numbers_sources_and_sets_language():
    hits = [make_hit(), make_hit(number="13")]
    messages = build_messages("ما هي شروط الزواج؟", hits, "msa")
    assert messages[0]["role"] == "system"
    assert NO_ANSWER in messages[0]["content"]
    assert "[1] (مدونة الأسرة — المادة 12" in messages[1]["content"]
    assert "[2]" in messages[1]["content"]
    assert "Modern Standard Arabic" in messages[1]["content"]


def test_source_label_includes_law_and_article():
    hit = make_hit(number="12", page=30)
    assert source_label(hit) == "مدونة الأسرة — المادة 12 (ص30)"


def test_abstention_and_disclaimer_cover_all_varieties():
    for variety in ("msa", "darija", "arabizi", "other"):
        assert ABSTENTION[variety]
        assert DISCLAIMER[variety]


def test_answer_cited_hits():
    hits = [make_hit(), make_hit(number="13")]
    answer = Answer("q", "نص [2]", False, "msa", hits, cited=[1], disclaimer="d")
    assert answer.cited_hits == [hits[1]]


def test_answer_as_dict_shape():
    hits = [make_hit()]
    answer = Answer("q", "نص [1]", False, "msa", hits, cited=[0], retrieval_query="rq")
    data = answer.as_dict()
    assert data["abstained"] is False
    assert data["sources"][0]["law_slug"] == "family-code-ar"
    assert data["disclaimer"]


def test_style_and_fixed_language_reach_the_prompt():
    from conftest import make_hit

    from qanoun_api.rag.answer import build_messages

    default = build_messages("q", [make_hit()], "darija")
    assert "at most 4 sentences" in default[0]["content"] and "Darija" in default[1]["content"]
    custom = build_messages("q", [make_hit()], "darija", style="detailed", language="fr")
    assert "bullet points" in custom[0]["content"]
    assert "Answer in French." in custom[1]["content"] and "Darija" not in custom[1]["content"]
