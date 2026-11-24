"""Seed a tiny fixture law for CI's browser smoke test (no PDFs, no embedding model).

    QANOUN_DB_URL=postgresql://… uv run --project pipeline python scripts/seed_fixture.py

Goes through the pipeline's own load_db functions, so the rows match what ingestion writes.
Chunk vectors are placeholders: the pages under test (home, laws, reader) never search.
Re-running replaces the fixture law.
"""

import os

from qanoun_pipeline import load_db, references
from qanoun_pipeline.catalog import LawMeta
from qanoun_pipeline.normalize import normalize

SLUG = "fixture-family-code-ar"
DECREE = "fixture-decree-ar"
ARTICLES = {
    "1": "يسمى هذا القانون مدونة الأسرة.",
    "4": "الزواج ميثاق تراض وترابط شرعي بين رجل وامرأة على وجه الدوام.",
    "19": "تكتمل أهلية الزواج بإتمام الفتى والفتاة المتمتعين بقواهما العقلية ثمان عشرة سنة شمسية، "
    "مع مراعاة أحكام المادة 4 أعلاه. "
    "12 - تم تغيير وتتميم المادة 4 أعلاه بمقتضى المادة الأولى من القانون رقم 102.21.",
}


def main() -> None:
    meta = LawMeta(
        slug=SLUG, group="fixture-family-code", title_ar="مدونة الأسرة (نص تجريبي)",
        title_fr="Code de la famille (fixture)", law_number="70.03", year=2004, domain="family",
        language="ar", file="fixture.pdf", source_url=None, sha256=None,
    )
    with load_db.connect(os.environ["QANOUN_DB_URL"]) as conn:
        load_db.ensure_schema(conn)
        law_id = load_db.upsert_law(
            conn, meta, page_count=1, article_count=len(ARTICLES), preamble="", warnings=[]
        )
        ids = load_db.insert_articles(conn, law_id, [
            {"law_slug": SLUG, "number": n, "ordinal": i, "text": f"المادة {n}: {text}",
             "normalized": normalize(text), "page_start": 1, "page_end": 1}
            for i, (n, text) in enumerate(ARTICLES.items(), start=1)
        ])
        dim = load_db.embedding_dim(conn)
        load_db.insert_chunks(conn, law_id, [
            {"chunk_key": f"{SLUG}#a{n}-c0", "ordinal": 0, "page": 1, "text": text,
             "article_id": ids[n], "embedding": [1.0] + [0.0] * (dim - 1)}
            for n, text in ARTICLES.items()
        ])
        # An implementing decree of the fixture law (catalog `parent`).
        decree = LawMeta(
            slug=DECREE, group="fixture-decree", title_ar="مرسوم تطبيقي (نص تجريبي)",
            title_fr="Décret d'application (fixture)", law_number="2.04.569", year=2004,
            domain="family", language="ar", file="fixture-decree.pdf", source_url=None,
            sha256=None, parent="fixture-family-code",
        )
        decree_id = load_db.upsert_law(conn, decree, page_count=1, article_count=1, preamble="", warnings=[])
        load_db.insert_articles(conn, decree_id, [
            {"law_slug": DECREE, "number": "1", "ordinal": 1, "text": "المادة الأولى يطبق هذا المرسوم.",
             "normalized": normalize("يطبق هذا المرسوم"), "page_start": 1, "page_end": 1}
        ])
        links = references.rebuild(conn)
    print(f"seeded {SLUG} and {DECREE}: {len(ARTICLES)} + 1 articles, {links} cross-reference(s)")


if __name__ == "__main__":
    main()
