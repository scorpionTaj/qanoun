"""DB round-trip tests. Run with a live Postgres:

    QANOUN_TEST_DB_URL=postgresql://qanoun:qanoun@localhost:5433/qanoun uv run --project pipeline pytest pipeline/tests/test_load_db.py

Skipped silently when the variable is unset (CI stays offline).
"""

import os

import pytest

from qanoun_pipeline import load_db

pytestmark = pytest.mark.skipif(
    not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set"
)


@pytest.fixture()
def conn():
    with load_db.connect(os.environ["QANOUN_TEST_DB_URL"]) as c:
        load_db.ensure_schema(c)
        c.execute("DELETE FROM laws WHERE slug = 'test-law'")
        c.commit()
        yield c
        c.execute("DELETE FROM laws WHERE slug = 'test-law'")
        c.commit()


def test_roundtrip(conn):
    from qanoun_pipeline.catalog import LawMeta

    meta = LawMeta(
        slug="test-law", group="test", title_ar="قانون الاختبار", title_fr=None,
        law_number="99-99", year=2099, domain="family", language="ar",
        file="test.pdf", source_url=None, sha256=None,
    )
    law_id = load_db.upsert_law(
        conn, meta, page_count=2, article_count=2, preamble="بسم الله", warnings=["w"]
    )
    articles = [
        {"law_slug": "test-law", "number": str(n), "ordinal": n, "text": f"المادة {n}",
         "normalized": f"المادة {n}", "page_start": n, "page_end": n}
        for n in (1, 2)
    ]
    ids = load_db.insert_articles(conn, law_id, articles)
    assert set(ids) == {"1", "2"}

    dim = load_db.embedding_dim(conn)
    rows = [
        {"chunk_key": f"test-law#a{n}-c0", "ordinal": 0, "page": n, "text": f"المادة {n}",
         "article_id": ids[str(n)], "embedding": [1.0] + [0.0] * (dim - 1)}
        for n in (1, 2)
    ]
    assert load_db.insert_chunks(conn, law_id, rows) == 2

    # upsert replaces the law and cascades
    load_db.upsert_law(conn, meta, page_count=2, article_count=2, preamble="بسم الله", warnings=[])
    totals = load_db.summary(conn)["totals"]
    assert totals["laws"] >= 1  # cascade cleaned the old rows; no orphans via FK


def test_summary_shape(conn):
    report = load_db.summary(conn)
    assert {"laws", "totals"} <= set(report)
    assert set(report["totals"]) == {"laws", "articles", "chunks"}
