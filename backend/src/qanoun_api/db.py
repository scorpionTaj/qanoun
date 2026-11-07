"""psycopg connection pool with pgvector registered on every connection."""

from collections.abc import Iterator
from contextlib import contextmanager

from pgvector.psycopg import register_vector  # noqa: F401  (re-exported for pool configure)
from psycopg_pool import ConnectionPool
from qanoun_pipeline.load_db import db_url, prepare_connection

from qanoun_api.config import SETTINGS

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            db_url(SETTINGS.db_url),
            min_size=1,
            max_size=8,
            open=True,
            # extension bootstrap + pgvector adapters on every pooled connection
            configure=prepare_connection,
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
