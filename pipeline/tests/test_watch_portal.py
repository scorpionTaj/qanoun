"""The portal watcher's matching rules (scripts/watch_portal.py), offline."""

import importlib.util
from pathlib import Path

from qanoun_pipeline.catalog import LawMeta

_spec = importlib.util.spec_from_file_location("watch_portal", Path(__file__).parents[2] / "scripts/watch_portal.py")
watch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watch)

BASE = "https://adala.justice.gov.ma/api/uploads/2024/10/24/old.pdf"


def law(number="65-99", language="ar", url=BASE, title="مدونة الشغل"):
    return LawMeta(slug="labour-code-ar", group="labour-code", title_ar=title, title_fr=None, law_number=number,
                   year=2003, domain="labour", language=language, file="x.pdf", source_url=url, sha256=None)


def result(name, date="2026/07/29", kind="ظهير", language="AR"):
    return {"type": "PDF", "language": language, "name": name, "path": f"uploads/{date}/{name}.pdf",
            "fileMeta": {"LawType": {"name": kind}}}


def test_number_forms_and_upload_date():
    assert watch.number_forms("65-99") == ["65.99", "65-99"]
    assert watch.number_forms("1-74-447") == ["1.74.447", "1-74-447"]
    assert watch.number_forms("DOC") == []
    assert watch.upload_date(BASE) == "20241024"


def test_newer_same_kind_same_language_with_the_number_is_a_candidate():
    found = watch.candidates(law(), [
        result("القانون رقم 65.99 المتعلق بمدونة الشغل"),                       # newer: yes
        result("القانون رقم 65.99 المتعلق بمدونة الشغل", date="2023/01/01"),    # older: no
        result("Loi n° 65-99 relative au Code du travail", language="FR"),      # other language: no
        result("دراسة حول القانون رقم 65.99", kind="دراسة"),                    # a study: no
        result("مرسوم بتطبيق القانون رقم 65.99", kind="مرسوم"),                 # a decree applying it: no
    ])
    assert [r["name"] for r in found] == ["القانون رقم 65.99 المتعلق بمدونة الشغل"]


def test_a_decree_is_matched_only_to_decrees():
    decree = law(number="2.04.569")
    found = watch.candidates(decree, [result("مرسوم رقم 2.04.569", kind="مرسوم"), result("ظهير 2.04.569")])
    assert [r["fileMeta"]["LawType"]["name"] for r in found] == ["مرسوم"]


def test_without_a_number_the_title_must_match():
    doc = law(number="DOC", title="قانون الالتزامات والعقود")
    found = watch.candidates(doc, [result("ظهير بمثابة قانون الالتزامات والعقود صيغة محينة"), result("قانون آخر")])
    assert len(found) == 1


def test_new_releases_citing_our_laws():
    releases = [{"title": "مرسوم رقم 2.26.10 بتطبيق القانون رقم 65.99 المتعلق بمدونة الشغل"},
                {"title": "مرسوم يتعلق بالصيد البحري"}]
    assert watch.cited_new_texts(releases, [law()]) == [("labour-code-ar", releases[0]["title"])]


def test_catalog_rewrite_touches_only_the_updated_entry(tmp_path):
    path = tmp_path / "laws.yaml"
    path.write_text("- slug: a\n  source_url: old-a\n  sha256: aaa\n- slug: b\n  source_url: old-b\n  sha256: bbb\n")
    watch.rewrite_catalog(path, [watch.Update("b", "old-b", "new-b", "n", 10, 10, "ccc")])
    assert path.read_text() == "- slug: a\n  source_url: old-a\n  sha256: aaa\n- slug: b\n  source_url: new-b\n  sha256: ccc\n"
