"""Single source of truth for the Qanoun schema (Postgres + pgvector): numbered migrations.

`migrate(conn)` applies the ones a database has not seen yet, in order, inside one
transaction under an advisory lock, and records each in `schema_migrations`. The pipeline runs
it before every load and the API at start-up (qanoun_api.main), so concurrent cold starts
cannot race and an up-to-date database costs one small read.

Rules: never edit a migration that has shipped; add the next number instead. Migration 1 is
written idempotently (IF NOT EXISTS) because it adopts databases created before migrations
existed. `chunks.embedding` is fixed at 1024 (BGE-M3); switching embedding models means a
migration plus a full re-embed.
"""

import psycopg

# Corpus: laws → articles → chunks. Re-ingesting a law replaces only its own rows.
CORPUS_SQL = """\
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

# Application data: optional accounts, their sessions and synced conversations. Kept in
# separate tables so re-ingesting laws can never touch it.
APP_SQL = """\
CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    email          TEXT UNIQUE NOT NULL,          -- stored lower-cased
    password_hash  TEXT NOT NULL,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);

CREATE TABLE IF NOT EXISTS conversations (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id          TEXT NOT NULL,                    -- client-generated UUID
    title       TEXT NOT NULL DEFAULT '',
    updated_at  BIGINT NOT NULL,                  -- client epoch ms (last write wins)
    messages    JSONB NOT NULL,
    PRIMARY KEY (user_id, id)
);
"""

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "base corpus and accounts schema", CORPUS_SQL + "\n" + APP_SQL),
]

# Arbitrary constant: serialises schema changes (and extension creation) across processes.
MIGRATION_LOCK_KEY = 7_302_614


def pending(applied: set[int]) -> list[tuple[int, str, str]]:
    return [m for m in MIGRATIONS if m[0] not in applied]


def migrate(conn: psycopg.Connection) -> list[int]:
    """Apply pending migrations; return the versions applied (empty when up to date)."""
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        done = []
        for version, name, sql in pending(applied):
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)", (version, name)
            )
            done.append(version)
    return done
