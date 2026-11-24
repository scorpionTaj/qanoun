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


def test_ingest_rejects_unknown_slugs_before_doing_anything():
    from qanoun_pipeline import cli

    with pytest.raises(SystemExit, match="unknown slugs: \\['no-such-law'\\]"):
        cli.main(["ingest-all", "--skip-fetch", "--slugs", "family-code-ar,no-such-law"])


def test_explicit_db_url_beats_the_environment(monkeypatch):
    from qanoun_pipeline import cli

    seen = {}
    monkeypatch.setenv("QANOUN_DB_URL", "postgresql://env-db/x")
    monkeypatch.setattr(cli, "show_summary", lambda args: seen.setdefault("url", args.db_url) and 0)
    monkeypatch.setattr("sys.argv", ["qanoun_pipeline", "--db-url", "postgresql://flag-db/x", "summary"])
    cli.main()  # as from the command line: argv=None
    assert seen["url"] == "postgresql://flag-db/x"

    seen.clear()
    monkeypatch.setattr("sys.argv", ["qanoun_pipeline", "summary"])
    cli.main()
    assert seen["url"] == "postgresql://env-db/x"  # no flag: the environment applies


def _write(tmp_path, entries):
    import yaml

    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(entries, allow_unicode=True), encoding="utf-8")
    return path


def _entry(slug, group, language="ar", **extra):
    return {"slug": slug, "group": group, "title_ar": slug, "domain": "labour", "language": language,
            "file": f"{slug}.pdf", **extra}


def test_a_group_is_one_law(tmp_path):
    ok = [_entry("a-ar", "a"), _entry("a-fr", "a", "fr")]
    assert len(catalog.load(_write(tmp_path, ok))) == 2
    with pytest.raises(catalog.CatalogError, match="two ar editions"):
        catalog.load(_write(tmp_path, [_entry("a-ar", "shared"), _entry("b-ar", "shared")]))


def test_a_decree_names_an_existing_parent_law(tmp_path):
    law, decree = _entry("labour-ar", "labour"), _entry("hours-decree-ar", "hours-decree", parent="labour")
    assert catalog.load(_write(tmp_path, [law, decree]))[1].parent == "labour"
    with pytest.raises(catalog.CatalogError, match="parent 'nope'"):
        catalog.load(_write(tmp_path, [law, _entry("x-ar", "x", parent="nope")]))
