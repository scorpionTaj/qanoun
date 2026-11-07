"""psycopg connection pool with pgvector registered on every connection."""

from contextlib import contextmanager
from collections.abc import Iterator

from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

from qanoun_api.config import SETTINGS
from qanoun_pipeline.load_db import db_url

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            db_url(SETTINGS.db_url),
            min_size=1,
            max_size=8,
            open=True,
            # pgvector adapters must be registered per connection.
            configure=register_vector,
        )
    return _pool


@contextmanager
def db() -> Iterator:
    with get_pool().connection() as conn:
        yield conn


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
