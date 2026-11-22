"""Schema migrations: ordering rules offline, and a real round trip when a test DB is set.

    QANOUN_TEST_DB_URL=postgresql://qanoun:qanoun@localhost:5433/qanoun \
        uv run --project pipeline pytest pipeline/tests/test_schema.py
"""

import os
from contextlib import nullcontext

import psycopg
import pytest

from qanoun_pipeline import schema


def test_versions_are_unique_and_increasing():
    versions = [v for v, _, _ in schema.MIGRATIONS]
    assert versions == sorted(versions)
    assert len(set(versions)) == len(versions)
    assert versions[0] == 1


def test_pending_skips_applied_and_keeps_order():
    all_versions = [v for v, _, _ in schema.MIGRATIONS]
    assert [v for v, _, _ in schema.pending(set())] == all_versions
    assert schema.pending(set(all_versions)) == []


class _Rows(list):
    pass


class FakeConn:
    """Records SQL; `applied` plays the schema_migrations table."""

    def __init__(self, applied: set[int]):
        self.applied = set(applied)
        self.sql: list[str] = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if sql.startswith("SELECT version"):
            return _Rows((v,) for v in sorted(self.applied))
        if sql.startswith("INSERT INTO schema_migrations"):
            self.applied.add(params[0])
        return _Rows()


def test_migrate_applies_pending_under_lock_then_is_a_noop():
    conn = FakeConn(set())
    assert schema.migrate(conn) == [v for v, _, _ in schema.MIGRATIONS]
    assert "pg_advisory_xact_lock" in conn.sql[0]

    again = FakeConn(conn.applied)
    assert schema.migrate(again) == []
    assert not any("CREATE TABLE IF NOT EXISTS laws" in s for s in again.sql)


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_migrate_on_a_real_database_is_idempotent():
    with psycopg.connect(os.environ["QANOUN_TEST_DB_URL"]) as conn:
        schema.migrate(conn)  # adopts an existing DB or creates a fresh one
        assert schema.migrate(conn) == []
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        assert [r[0] for r in rows] == [v for v, _, _ in schema.MIGRATIONS]
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
            )
        }
        assert {"laws", "articles", "chunks", "users", "sessions", "conversations"} <= tables
