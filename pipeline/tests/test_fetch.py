from pathlib import Path

import pytest

from qanoun_pipeline.catalog import LawMeta, file_sha256
from qanoun_pipeline.sources.fetch import FetchError, ensure_file, upload_url


def meta(**overrides) -> LawMeta:
    base = dict(
        slug="t",
        group="t",
        title_ar="ت",
        title_fr=None,
        law_number=None,
        year=None,
        domain="family",
        language="ar",
        file="t.pdf",
        source_url=None,
        sha256=None,
    )
    return LawMeta(**{**base, **overrides})


GOOD = "ab" * 32


def test_upload_url_quotes_arabic_segments():
    url = upload_url("https://adala.justice.gov.ma/api/uploads/2024/07/22/مدونة الأسرة-1721646687560.pdf")
    assert url.startswith("https://adala.justice.gov.ma/api/uploads/2024/07/22/")
    assert "%D9%85" in url
    assert " " not in url


def test_existing_file_with_matching_sha_is_kept(tmp_path: Path):
    dest = tmp_path / "t.pdf"
    dest.write_bytes(b"pdf")
    m = meta(file="t.pdf", sha256=file_sha256(dest))
    assert ensure_file(m, tmp_path) == dest


def test_existing_file_with_wrong_sha_raises(tmp_path: Path):
    dest = tmp_path / "t.pdf"
    dest.write_bytes(b"pdf")
    m = meta(file="t.pdf", sha256=GOOD)
    with pytest.raises(FetchError, match="sha256 mismatch"):
        ensure_file(m, tmp_path)


def test_missing_file_without_source_raises(tmp_path: Path):
    with pytest.raises(FetchError, match="no source"):
        ensure_file(meta(file="missing.pdf"), tmp_path)


def test_missing_file_with_verify_only_raises(tmp_path: Path):
    with pytest.raises(FetchError, match="verify-only"):
        ensure_file(meta(file="missing.pdf", source_url="https://x/y.pdf"), tmp_path, verify_only=True)
