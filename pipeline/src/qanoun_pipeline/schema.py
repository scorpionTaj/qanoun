"""Single source of truth for the Qanoun schema (Postgres + pgvector).

The pipeline applies it idempotently on every load; the backend's Alembic migration runs
the same DDL so containers come up already consistent. `chunks.embedding` is fixed at 1024
(BGE-M3); switching embedding models means a migration plus a full re-embed.
"""

SCHEMA_SQL = """\
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS laws (
    id             SERIAL PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    group_slug     TEXT NOT NULL,
    title_ar       TEXT NOT NULL,
    title_fr       TEXT,
    law_number     TEXT,
    year           INTEGER,
    domain         TEXT NOT NULL,
    language       TEXT NOT NULL,
    source_url     TEXT,
    sha256         TEXT,
    file           TEXT NOT NULL,
    page_count     INTEGER,
    article_count  INTEGER,
    preamble       TEXT,
    warnings       TEXT[] NOT NULL DEFAULT '{}',
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS articles (
    id          SERIAL PRIMARY KEY,
    law_id      INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    number      TEXT NOT NULL,
    ordinal     INTEGER NOT NULL,
    text        TEXT NOT NULL,
    normalized  TEXT NOT NULL,
    page_start  INTEGER NOT NULL,
    page_end    INTEGER NOT NULL,
    UNIQUE (law_id, number)
);

-- Postgres ships no Arabic stemmer; 'simple' over our own normalized text is the correct
-- equivalent of matching the query through the same normalizer.
CREATE INDEX IF NOT EXISTS articles_fts_idx
    ON articles USING GIN (to_tsvector('simple', normalized));

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    law_id      INTEGER NOT NULL REFERENCES laws(id) ON DELETE CASCADE,
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    chunk_key   TEXT UNIQUE NOT NULL,
    ordinal     INTEGER NOT NULL,
    page        INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(1024) NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS laws_domain_idx ON laws (domain);
CREATE INDEX IF NOT EXISTS articles_law_idx ON articles (law_id, ordinal);
"""
