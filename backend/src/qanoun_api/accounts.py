"""Optional accounts: users, sessions and their synced conversations.

Application data, kept apart from the corpus schema (qanoun_pipeline.schema) so that
re-ingesting laws can never touch it. Applied idempotently at API start-up.

- Passwords: stdlib scrypt (memory-hard), per-user random salt, constant-time compare.
- Sessions: a random token in an httpOnly cookie; only its SHA-256 is stored, so a database
  leak exposes no usable session.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import psycopg

APP_SCHEMA_SQL = """\
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

SESSION_DAYS = 30
MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def ensure_app_schema(conn: psycopg.Connection) -> None:
    conn.execute(APP_SCHEMA_SQL)
    conn.commit()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(conn: psycopg.Connection, email: str, password: str, *, admin: bool | None = None) -> int:
    """Create a user; the very first user becomes admin unless `admin` says otherwise."""
    if admin is None:
        admin = conn.execute("SELECT NOT EXISTS (SELECT 1 FROM users)").fetchone()[0]
    row = conn.execute(
        "INSERT INTO users (email, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id",
        (normalize_email(email), hash_password(password), admin),
    ).fetchone()
    conn.commit()
    return row[0]


def authenticate(conn: psycopg.Connection, email: str, password: str) -> int | None:
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email = %s", (normalize_email(email),)
    ).fetchone()
    if row is None:
        hash_password(password)  # same work as a real check: don't reveal which emails exist
        return None
    return row[0] if verify_password(password, row[1]) else None


def create_session(conn: psycopg.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
        (_token_hash(token), user_id, datetime.now(UTC) + timedelta(days=SESSION_DAYS)),
    )
    conn.commit()
    return token


def session_user(conn: psycopg.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """
        SELECT u.id, u.email, u.is_admin FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = %s AND s.expires_at > now()
        """,
        (_token_hash(token),),
    ).fetchone()
    return {"id": row[0], "email": row[1], "is_admin": row[2]} if row else None


def delete_session(conn: psycopg.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = %s", (_token_hash(token),))
        conn.commit()
