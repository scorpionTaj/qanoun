"""Cross-references: one test per rule, on phrasings taken from the corpus."""

import os

import pytest

from qanoun_pipeline.references import Law, Resolver, resolve_number

LAWS = [
    Law("family-code-ar", "ar", "70.03", "مدونة الأسرة"),
    Law("family-code-fr", "fr", "70-03", "Code de la famille"),
    Law("commercial-code-ar", "ar", "15-95", "مدونة التجارة"),
    Law("labour-code-fr", "fr", "65-99", "Code du travail"),
]
R = Resolver(LAWS)


def refs(text, slug="commercial-code-ar", language="ar", number="100"):
    return [(r.target_slug, r.number) for r in R.extract(slug, language, number, text)]


def test_arabic_glued_number_and_same_law_qualifier():
    assert refs("الوثائق المنصوص عليها في المادة53 أعلاه") == [("commercial-code-ar", "53")]


def test_arabic_prefixed_forms_lists_and_ranges():
    assert refs("طبقا للمادة 7 من هذا القانون") == [("commercial-code-ar", "7")]
    assert refs("المشار إليها في المواد 12 و13 و14") == [("commercial-code-ar", n) for n in ("12", "13", "14")]
    assert refs("المنصوص عليها في المادتين 5 و6") == [("commercial-code-ar", "5"), ("commercial-code-ar", "6")]
    found = refs("تطبق أحكام الفصول 644 إلى 648", slug="obligations-contracts-ar")
    assert [n for _, n in found] == ["644", "648", "645", "646", "647"]


def test_amendment_notes_are_not_references():
    assert refs("تم تغيير المادة 98 أعلاه بمقتضى المادة 134 من القانون رقم 64.12") == []
    assert refs("Alinéa 2 de l'article 145 modifié et complété", language="fr") == []


def test_another_law_by_number_or_title():
    assert refs("وفق المادة 19 من القانون رقم 70.03") == [("family-code-ar", "19")]
    assert refs("المنصوص عليها في المادة 400 من مدونة الأسرة") == [("family-code-ar", "400")]
    # mid-text, as in the corpus: an article's own leading header is never a reference
    assert refs("révolues ». 8- Article 210 de la loi n° 70-03 portant code", slug="labour-code-fr", language="fr") == [
        ("family-code-fr", "210")
    ]


def test_texts_we_do_not_have_are_dropped_not_guessed():
    assert refs("المادة 7 من المرسوم السالف الذكر") == []
    assert refs("المادة 3 من القانون رقم 99.99") == []
    assert refs("l'article 12 du dahir du 9 ramadan", language="fr") == []


def test_french_forms_and_section_headings():
    assert refs("conformément à l'article 12 ci-dessus", slug="labour-code-fr", language="fr") == [
        ("labour-code-fr", "12")
    ]
    assert refs("les articles 284 à 286", slug="labour-code-fr", language="fr") == [
        ("labour-code-fr", n) for n in ("284", "286", "285")
    ]
    assert refs("CHAPITRE II (Articles 248 à 256)", slug="labour-code-fr", language="fr") == []


def test_own_header_and_self_references_are_ignored():
    assert refs("المادة 100 يجب على التاجر أن يحتفظ بالمادة 100 كما هي", number="100") == []


def test_only_exact_targets_resolve():
    assert resolve_number("53", {"52", "53"}) == "53"
    assert resolve_number("10-157", {"10", "157"}) is None  # no guessing the base number
    assert resolve_number("4-10", {"4-10"}) == "4-10"


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_rebuild_on_a_real_database():
    from qanoun_pipeline import load_db, references
    from qanoun_pipeline.catalog import LawMeta

    with load_db.connect(os.environ["QANOUN_TEST_DB_URL"]) as conn:
        load_db.ensure_schema(conn)
        conn.execute("DELETE FROM laws WHERE slug LIKE 'refs-test-%'")
        conn.commit()
        for slug, texts in {
            "refs-test-a": ["المادة 1 نص.", "المادة 2 تطبق أحكام المادة 1 أعلاه والمادة 9."],
            "refs-test-b": ["المادة 1 وفق المادة 2 من القانون رقم 77.77."],
        }.items():
            meta = LawMeta(
                slug=slug, group=slug, title_ar=slug, title_fr=None,
                law_number="77.77" if slug == "refs-test-a" else None, year=2099,
                domain="family", language="ar", file="x.pdf", source_url=None, sha256=None,
            )
            law_id = load_db.upsert_law(conn, meta, page_count=1, article_count=len(texts), preamble="", warnings=[])
            load_db.insert_articles(conn, law_id, [
                {"law_slug": slug, "number": str(i), "ordinal": i, "text": t, "normalized": t,
                 "page_start": 1, "page_end": 1}
                for i, t in enumerate(texts, start=1)
            ])
        references.rebuild(conn)
        assert references.rebuild(conn) == references.rebuild(conn)  # idempotent
        links = set(conn.execute(
            """SELECT l.slug, a.number, r.target_law_slug, r.target_number FROM article_refs r
               JOIN articles a ON a.id = r.article_id JOIN laws l ON l.id = a.law_id
               WHERE l.slug LIKE 'refs-test-%'"""
        ).fetchall())
        # article 9 does not exist: dropped; b → a resolved through the law number
        assert links == {("refs-test-a", "2", "refs-test-a", "1"), ("refs-test-b", "1", "refs-test-a", "2")}
        conn.execute("DELETE FROM laws WHERE slug LIKE 'refs-test-%'")
        conn.commit()
