"""The connection pool against a live database."""

import os
from dataclasses import replace

import pytest


@pytest.mark.skipif(not os.environ.get("QANOUN_TEST_DB_URL"), reason="QANOUN_TEST_DB_URL not set")
def test_pooled_connections_never_prepare_statements(monkeypatch):
    # Behind Supabase's transaction pooler, prepared statements broke requests under load
    # (DuplicatePreparedStatement / InvalidSqlStatementName): they must stay off.
    from qanoun_api import db as db_module

    db_module.close_pool()
    monkeypatch.setattr(db_module, "SETTINGS", replace(db_module.SETTINGS, db_url=os.environ["QANOUN_TEST_DB_URL"]))
    try:
        with db_module.db() as conn:
            assert conn.prepare_threshold is None
            for _ in range(10):  # more than psycopg's default threshold of 5
                conn.execute("SELECT %s::int", (1,))
            assert conn.execute("SELECT count(*) FROM pg_prepared_statements").fetchone()[0] == 0
    finally:
        db_module.close_pool()
