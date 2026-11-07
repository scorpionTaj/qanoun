import pytest

from qanoun_pipeline.parse import Page
from qanoun_pipeline.structure import StructureError, segment


def pages(*texts: str) -> list[Page]:
    return [Page("doc.pdf", i + 1, t) for i, t in enumerate(texts)]


AR = """المادة 1
يتم الزواج بعقد يبرره بين الزوجين.
المادة 11
يتعين على العاقد التحقق من الأهلية.
المادة 20
تنظم المادة 20 الشروط الأخرى."""

FR = """Titre préliminaire
Article 1er
Le mariage est régi par les dispositions du présent code.
Article 2
Les fiançailles ne sont pas contraignantes."""

AR_DIGITS = """مادة ١٢
النص العربي بالأرقام الهندية.
مادة ١٣
المتابعة."""


def test_segment_arabic_articles():
    report = segment(pages(AR))
    assert [a.number for a in report.articles] == ["1", "11", "20"]
    assert report.articles[0].text.startswith("المادة 1")
    assert "العاقد" in report.articles[1].text
    assert report.articles[0].page_start == report.articles[0].page_end == 1


def test_segment_french_articles_with_1er():
    report = segment(pages(FR))
    assert [a.number for a in report.articles] == ["1", "2"]
    assert "fiançailles" in report.articles[1].text
    assert "Titre préliminaire" in report.preamble


def test_segment_preamble_and_page_ranges():
    report = segment(pages("بسم الله والقانون رقم 70.03\nالمادة 1\nنص أول.", "المادة 2\nنص ثان."))
    assert "بسم الله" in report.preamble
    assert report.articles[1].page_start == 2


def test_segment_handles_arabic_indic_digits():
    report = segment(pages(AR_DIGITS))
    assert [a.number for a in report.articles] == ["12", "13"]


def test_segment_reports_out_of_order_numbers_as_warnings():
    report = segment(pages("المادة 5\nنص.\nالمادة 3\nنص آخر."))
    assert any("out of order" in w for w in report.warnings)


def test_segment_reports_duplicate_numbers():
    report = segment(pages("المادة 4\nنص.\nالمادة 4\nمرة أخرى."))
    assert any("duplicate" in w for w in report.warnings)


def test_segment_raises_when_no_articles_found():
    with pytest.raises(StructureError):
        segment(pages("نص عشوائي بلا مواد إطلاقا."))


def test_segment_keeps_sub_numbered_articles_unique():
    report = segment(pages("Article 65\ntexte.\nArticle 65-1\nvariante un.\nArticle 65-2\nvariante deux."))
    assert [a.number for a in report.articles] == ["65", "65-1", "65-2"]


def test_segment_arabic_sub_numbered_articles():
    report = segment(pages("المادة 4\nنص.\nالمادة 4 مكرر\nنص مكرر."))
    assert [a.number for a in report.articles] == ["4", "4-bis"]


def test_segment_trims_glued_footnote_from_header():
    # "Article 23" + superscript footnote 17 extracts as "2317"; the sequence repairs it.
    body = "".join(f"Article {n}\ntexte {n}.\n" for n in range(1, 23))
    report = segment(pages(body + "Article 2317\nL'offre faite.\nArticle 24\nsuite."))
    numbers = [a.number for a in report.articles]
    assert "23" in numbers and "24" in numbers
    assert any("trimmed glued footnote" in w for w in report.warnings)


def test_segment_drops_duplicate_headers_as_body_text():
    report = segment(pages("Article 5\nنص المادة الخامسة الطويلة بما يكفي للفحص.\nArticle 5\nإشارة لاحقة."))
    assert len(report.articles) == 1
    assert "إشارة لاحقة" in report.articles[0].text
    assert any("duplicate" in w for w in report.warnings)
