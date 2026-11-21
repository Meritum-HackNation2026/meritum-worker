"""PostgresEuvsCopy on a real database: local only, ``uv run pytest -m integration``.

Needs the meritum-postgres image (pgvector) and ``MERITUM_TEST_DATABASE_URL``. The
fake server's keys (``case:1``...) would clash with a real copy, so the test runs
only while both copy tables are empty and empties them again afterwards.
"""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import apply_corpus_migrations
from meritum_worker.corpus.fakes import FakeEuvsDisinfoServer

TOKEN = "token"  # ruff: ignore[hardcoded-password-string]  # the fake server's token
ANY_ROW = (
    "SELECT 1 FROM corpus.euvsdisinfo_entries LIMIT 1",
    "SELECT 1 FROM corpus.euvsdisinfo_flagged_domains LIMIT 1",
)
EMPTY = (
    "DELETE FROM corpus.euvsdisinfo_entries",
    "DELETE FROM corpus.euvsdisinfo_flagged_domains",
)


@pytest.fixture
def settings() -> Iterator[CorpusSettings]:
    url = os.environ.get("MERITUM_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("set MERITUM_TEST_DATABASE_URL to the meritum-postgres image")
    apply_corpus_migrations(url)
    with psycopg.connect(url, autocommit=True) as conn:
        if any(conn.execute(query).fetchone() for query in ANY_ROW):
            pytest.skip("the EUvsDisinfo copy has rows; use an empty test database")
    yield CorpusSettings(provider=CorpusProvider.POSTGRES, database_url=url)
    with psycopg.connect(url, autocommit=True) as conn:
        for query in EMPTY:
            conn.execute(query)


def sync(
    server: FakeEuvsDisinfoServer, store: corpus.EuvsCopyPort
) -> corpus.SyncReport:
    return asyncio.run(
        corpus.run_euvsdisinfo_sync(
            {"EUVSDISINFO_MCP_API_KEY": TOKEN},
            store,
            build_embeddings(EmbeddingsSettings()),
            now=datetime(2026, 11, 21, tzinfo=UTC),
            http_client=server.client(),
        )
    )


@pytest.mark.integration
def test_issue_scenario_copy_survives_a_worker_restart(
    settings: CorpusSettings,
) -> None:
    """Gherkin: kopia przeżywa restart workera (worker#59)."""
    # Given kopia EUvsDisinfo zapisana przez workflow synchronizacji
    server = FakeEuvsDisinfoServer(TOKEN)
    server.seed(cases=30, articles=10)
    before = corpus.build_euvsdisinfo_copy(settings)
    assert sync(server, before) == corpus.SyncReport(added=40)
    # When worker startuje ponownie
    after = corpus.build_euvsdisinfo_copy(settings)
    # Then kolejny przebieg synchronizacji widzi poprzednią kopię
    # i zapisuje tylko różnicę
    cases = [s for s in asyncio.run(after.entries()) if s.entry.kind == "case"]
    assert len(cases) == 30
    assert all(s.source is not None and s.fact_vector is not None for s in cases)
    assert len(cases[0].description_vector) == EmbeddingsSettings().dimensions
    assert asyncio.run(after.flagged_domains())
    server.add_cases(5)
    server.change_cases(2)
    server.remove_cases(1)
    assert sync(server, after) == corpus.SyncReport(added=5, updated=2, deleted=1)
