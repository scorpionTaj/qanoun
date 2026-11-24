from qanoun_api.amendments import parse_amendments, parse_events, ref_year, summarize


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
    assert summary["laws"][0] == {"ref": "35.10", "mentions": 2, "articles": ["2", "12"], "year": 2010}
    assert summary["articles"]["12"] == ["35.10", "72.03"]


def test_joins_numbers_split_by_a_line_break():
    assert parse_amendments("Article 279 modifié par le dahir portant loi n° 1-93- 206, précité") == [("279", "1-93-206")]


def test_kinds_of_change_in_both_languages():
    ar = parse_events("111 - تم تغيير وتتميم وتعويض الفصل179 أعاله بموجب القانون رقم72.03 ، سالف الذكر")
    assert ar[0].kinds == ("amended", "supplemented", "replaced")
    fr = parse_events("5 - Article 9 modifié, complété et remplacé par la loi n° 72.03 modifiant le code")
    assert fr[0].kinds == ("amended", "supplemented", "replaced")
    assert parse_events("تم نسخ المادة 5 أعلاه بمقتضى القانون رقم 12.18")[0].kinds == ("repealed",)


def test_year_from_the_number_or_an_explicit_date():
    assert [ref_year(r) for r in ("12.18", "65-99", "1-93-206", "2.04.569", "DOC")] == [2018, 1999, 1993, 2004, None]
    # Notes go on to cite the amended law's own dahir: its date is not the amendment's.
    note = ("تم تغيير وتتميم المادة 32 أعلاه بمقتضى المادة الأولى من القانون رقم 02.21 الرامي إلى تغيير "
            "المادتين 32 و256 من القانون رقم 65.99 المتعلق بمدونة الشغل الصادر بتنفيذه الظهير الشريف "
            "بتاريخ 11 سبتمبر 2003")
    assert parse_events(note)[0].year == 2021
    # A number without a year falls back to a date written in the note.
    assert parse_events("Article 3 modifié par la loi n° 5-2020 du 3 mars 2020")[0].year == 2020


def test_history_is_chronological_per_article():
    texts = [
        "تم تتميم المادة 12 أعلاه بمقتضى القانون رقم 35.10؛ تم تغيير المادة 12 أعلاه بموجب القانون رقم 72.03",
        "Article 12 modifié par la loi n° 72-03",
    ]
    history = summarize(texts)["history"]["12"]
    assert [(e["ref"], e["year"]) for e in history] == [("72-03", 2003), ("72.03", 2003), ("35.10", 2010)]
    assert history[-1]["kinds"] == ["supplemented"]
