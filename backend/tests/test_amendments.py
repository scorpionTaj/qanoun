from qanoun_api.amendments import parse_amendments, summarize


def test_parses_arabic_footnote_target_and_law():
    note = "111 - تم تغيير وتتميم وتعويض الفصل179 أعاله بموجب القانون رقم72.03 ، سالف الذكر"
    assert parse_amendments(note) == [("179", "72.03")]


def test_ignores_arabic_prose_without_amending_text():
    assert parse_amendments("إذا وقع تغيير في وضعية الحاضن سقطت حضانته") == []


def test_parses_french_footnote_and_normalizes_number():
    note = "5 - Article 9 modifié, complété et remplacé par la loi n° 72.03 modifiant le code"
    assert parse_amendments(note) == [("9", "72-03")]


def test_summary_groups_by_amending_law_and_article():
    texts = [
        "تم تغيير الفصل 12 أعلاه بموجب القانون رقم 35.10",
        "تم نسخ الفصل 2 أعلاه بموجب القانون رقم 35.10؛ تم تغيير الفصل 12 أعلاه بمقتضى القانون رقم 72.03",
    ]
    summary = summarize(texts)
    assert summary["laws"][0] == {"ref": "35.10", "mentions": 2, "articles": ["2", "12"]}
    assert summary["articles"]["12"] == ["35.10", "72.03"]


def test_joins_numbers_split_by_a_line_break():
    assert parse_amendments("Article 279 modifié par le dahir portant loi n° 1-93- 206, précité") == [("279", "1-93-206")]
