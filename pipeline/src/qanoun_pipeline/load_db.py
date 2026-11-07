"""Load structured laws into Postgres/pgvector (psycopg3, register_vector).

Re-ingesting a slug replaces that law's rows (DELETE cascades to articles and chunks), so
the operation is idempotent from the CLI. Rows are counted and returned for the ingest
summary.
"""

from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector

from qanoun_pipeline.catalog import LawMeta
from qanoun_pipeline.schema import SCHEMA_SQL


def db_url(url: str) -> str:
    """Accept both SQLAlchemy-style (postgresql+psycopg://) and plain psycopg URLs."""
    return url.replace("postgresql+psycopg://", "postgresql://")


def prepare_connection(conn: psycopg.Connection) -> None:
    """Idempotent per-connection setup: make sure the vector extension exists, then bind
    the pgvector adapters. Handles a fresh database (extension before registration)."""
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(db_url(url))
    prepare_connection(conn)
    return conn


@dataclass
class IngestCounts:
    laws: int = 0
    articles: int = 0
    chunks: int = 0


def ensure_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL)
    conn.commit()


def upsert_law(
    conn: psycopg.Connection,
    meta: LawMeta,
    *,
    page_count: int,
    article_count: int,
    preamble: str,
    warnings: list[str],
) -> int:
    conn.execute("DELETE FROM laws WHERE slug = %s", (meta.slug,))
    row = conn.execute(
        """
        INSERT INTO laws (slug, group_slug, title_ar, title_fr, law_number, year, domain,
                          language, source_url, sha256, file, page_count, article_count,
                          preamble, warnings)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            meta.slug, meta.group, meta.title_ar, meta.title_fr, meta.law_number, meta.year,
            meta.domain, meta.language, meta.source_url, meta.sha256, meta.file,
            page_count, article_count, preamble, warnings,
        ),
    ).fetchone()
    conn.commit()
    return row[0]


def insert_articles(
    conn: psycopg.Connection, law_id: int, articles: list[dict]
) -> dict[str, int]:
    """Insert articles; returns {number: article_id} so chunk rows can reference them."""
    mapping: dict[str, int] = {}
    with conn.cursor() as cur:
        for article in articles:
            article_id = cur.execute(
                """
                INSERT INTO articles (law_id, number, ordinal, text, normalized, page_start, page_end)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    law_id, article["number"], article["ordinal"], article["text"],
                    article["normalized"], article["page_start"], article["page_end"],
                ),
            ).fetchone()[0]
            mapping[article["number"]] = article_id
    conn.commit()
    return mapping


def insert_chunks(
    conn: psycopg.Connection,
    law_id: int,
    rows: list[dict],  # {chunk_key, ordinal, page, text, article_id, embedding}
) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO chunks (law_id, article_id, chunk_key, ordinal, page, text, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (chunk_key) DO UPDATE
                SET text = EXCLUDED.text, embedding = EXCLUDED.embedding
                """,
                (
                    law_id, row["article_id"], row["chunk_key"], row["ordinal"], row["page"],
                    row["text"], row["embedding"],
                ),
            )
    conn.commit()
    return len(rows)


def summary(conn: psycopg.Connection) -> dict:
    """One-row-per-law stats plus totals, for the CLI ingest report."""
    per_law = conn.execute(
        """
        SELECT l.slug, l.domain, l.language, l.article_count, l.page_count,
               (SELECT count(*) FROM chunks c WHERE c.law_id = l.id) AS chunk_count
        FROM laws l ORDER BY l.slug
        """
    ).fetchall()
    totals = conn.execute(
        "SELECT (SELECT count(*) FROM laws), (SELECT count(*) FROM articles), "
        "(SELECT count(*) FROM chunks)"
    ).fetchone()
    return {
        "laws": [dict(zip(("slug", "domain", "language", "articles", "pages", "chunks"), row)) for row in per_law],
        "totals": dict(zip(("laws", "articles", "chunks"), totals)),
    }


def embedding_dim(conn: psycopg.Connection) -> int:
    return conn.execute(
        "SELECT atttypmod FROM pg_attribute "
        "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
    ).fetchone()[0]
