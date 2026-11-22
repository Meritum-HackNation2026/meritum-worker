"""apply_corpus_migrations on real PostgreSQL (local only: pytest -m integration)."""

import os

import psycopg
import pytest

from meritum_worker.corpus.adapters import apply_corpus_migrations

# Own variable, so the test never touches a real corpus; needs the meritum-postgres
# image (pgvector, pg_trgm, public.polish) and creates or reuses schema corpus.
URL = os.environ.get("MERITUM_TEST_DATABASE_URL", "")


@pytest.mark.integration
@pytest.mark.skipif(not URL, reason="set MERITUM_TEST_DATABASE_URL")
def test_second_run_applies_nothing() -> None:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS corpus")
    apply_corpus_migrations(URL)
    assert apply_corpus_migrations(URL) == []
    with psycopg.connect(URL) as conn:
        names = conn.execute("SELECT name FROM corpus.schema_migrations").fetchall()
        tables = conn.execute("SELECT to_regclass('corpus.passages')").fetchone()
    assert ("0001_corpus_search.sql",) in names
    assert tables == ("corpus.passages",)
