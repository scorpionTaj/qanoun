"""Optional accounts: users, sessions and their synced conversations.

Application data, in tables apart from the corpus so that re-ingesting laws can never touch
it. Their DDL is a migration in qanoun_pipeline.schema, like every other table.

- Passwords: stdlib scrypt (memory-hard), per-user random salt, constant-time compare.
- Sessions: a random token in an httpOnly cookie; only its SHA-256 is stored, so a database
  leak exposes no usable session.
"""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

import psycopg

SESSION_DAYS = 30
MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


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


# API keys: «qk_» + 43 random URL-safe characters. Stored as a sha256, like session tokens:
# a key is a 256-bit random secret, so a fast hash is enough (no password stretching).
KEY_PREFIX = "qk_"
MAX_KEYS = 10  # active keys per user


def _key_row(row) -> dict:
    return {"id": row[0], "name": row[1], "prefix": row[2], "created_at": row[3].isoformat(),
            "last_used_at": row[4].isoformat() if row[4] else None}


def create_api_key(conn: psycopg.Connection, user_id: int, name: str) -> dict | None:
    """A new key for the user (the only time the key itself is returned), or None at the cap."""
    active = conn.execute(
        "SELECT count(*) FROM api_keys WHERE user_id = %s AND revoked_at IS NULL", (user_id,)
    ).fetchone()[0]
    if active >= MAX_KEYS:
        return None
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    row = conn.execute(
        """
        INSERT INTO api_keys (user_id, name, prefix, key_hash) VALUES (%s, %s, %s, %s)
        RETURNING id, name, prefix, created_at, last_used_at
        """,
        (user_id, name, key[:7], _token_hash(key)),
    ).fetchone()
    conn.commit()
    return {**_key_row(row), "key": key}


def list_api_keys(conn: psycopg.Connection, user_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, prefix, created_at, last_used_at FROM api_keys
        WHERE user_id = %s AND revoked_at IS NULL ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [_key_row(r) for r in rows]


def revoke_api_key(conn: psycopg.Connection, user_id: int, key_id: int) -> bool:
    row = conn.execute(
        "UPDATE api_keys SET revoked_at = now() WHERE id = %s AND user_id = %s AND revoked_at IS NULL RETURNING id",
        (key_id, user_id),
    ).fetchone()
    conn.commit()
    return row is not None


def api_key_owner(conn: psycopg.Connection, key: str) -> int | None:
    """The user id behind an active key (and record its use), or None."""
    if not key.startswith(KEY_PREFIX):
        return None
    row = conn.execute(
        "UPDATE api_keys SET last_used_at = now() WHERE key_hash = %s AND revoked_at IS NULL RETURNING user_id",
        (_token_hash(key),),
    ).fetchone()
    conn.commit()
    return row[0] if row else None


def get_settings(conn: psycopg.Connection, user_id: int) -> dict:
    row = conn.execute("SELECT settings FROM users WHERE id = %s", (user_id,)).fetchone()
    return row[0] if row else {}


def put_settings(conn: psycopg.Connection, user_id: int, settings: dict) -> None:
    conn.execute("UPDATE users SET settings = %s::jsonb WHERE id = %s", (json.dumps(settings), user_id))
    conn.commit()
