from pathlib import Path

import pytest

from qanoun_pipeline import catalog

CATALOG_PATH = Path("data/catalog/laws.yaml")
RAW_DIR = CATALOG_PATH.parents[1] / "raw"


def test_seed_catalog_loads_and_validates():
    laws = catalog.load(CATALOG_PATH)
    assert len(laws) >= 8
    domains = {law.domain for law in laws}
    assert {"family", "labour", "civil", "housing", "commercial"} <= domains


def test_bilingual_laws_share_group():
    laws = catalog.load(CATALOG_PATH)
    moudawana = [law for law in laws if law.group == "moudawana"]
    assert {law.language for law in moudawana} == {"ar", "fr"}
    assert all(law.law_number == "70-03" for law in moudawana)


def test_every_entry_has_sha256():
    for law in catalog.load(CATALOG_PATH):
        assert law.sha256, f"{law.slug} missing sha256"


@pytest.mark.skipif(
    not any(RAW_DIR.glob("*.pdf")),
    reason="corpus not fetched: data/raw/*.pdf is not in git (run `make ingest`)",
)
def test_every_catalog_file_was_fetched():
    for law in catalog.load(CATALOG_PATH):
        assert (RAW_DIR / law.file).exists(), f"{law.slug}: file missing"


def test_rejects_unknown_domain(tmp_path: Path):
    bad = tmp_path / "catalog.yaml"
    bad.write_text(
        "- slug: x\n  title_ar: ت\n  domain: cooking\n  language: ar\n  file: f.pdf\n",
        encoding="utf-8",
    )
    with pytest.raises(catalog.CatalogError, match="unknown domain"):
        catalog.load(bad)


def test_rejects_bad_sha256(tmp_path: Path):
    bad = tmp_path / "catalog.yaml"
    bad.write_text(
        "- slug: x\n  title_ar: ت\n  domain: family\n  language: ar\n  file: f.pdf\n"
        "  sha256: nothex\n",
        encoding="utf-8",
    )
    with pytest.raises(catalog.CatalogError, match="sha256"):
        catalog.load(bad)


def test_missing_required_field_reports_entry(tmp_path: Path):
    bad = tmp_path / "catalog.yaml"
    bad.write_text("- slug: x\n  domain: family\n  language: ar\n", encoding="utf-8")
    with pytest.raises(catalog.CatalogError, match="title_ar"):
        catalog.load(bad)
