"""PostgresCorpusWriter on a real database: local only (``pytest -m integration``).

Needs the meritum-postgres image (pgvector, ``public.polish``) and
``MERITUM_TEST_DATABASE_URL``. The test runs only on a corpus with no documents
or snapshots and empties those tables again afterwards.
"""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus import CorpusProvider, CorpusSettings, build_corpus_search
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import apply_corpus_migrations
from meritum_worker.corpus.fakes import FakeCatalogSite
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
ANY_ROW = (
    "SELECT 1 FROM corpus.documents LIMIT 1",
    "SELECT 1 FROM corpus.passages LIMIT 1",
    "SELECT 1 FROM corpus.snapshots LIMIT 1",
    "SELECT 1 FROM corpus.ingest_attempts LIMIT 1",
)
EMPTY = (
    "DELETE FROM corpus.snapshot_manifest",
    "DELETE FROM corpus.snapshots",
    "DELETE FROM corpus.passages",
    "DELETE FROM corpus.documents",
    "DELETE FROM corpus.ingest_attempts",
)
ENTRY = CatalogEntry(
    domain="urzad.gov.pl",
    publisher="Urząd",
    publisher_id="urzad",
    kind="instytucja",
    tier="primary",
    license="CC BY 4.0",
    ingest="static",
    qualified_because="Źródło z listy organizatora konkursu.",
)


@pytest.fixture
def settings() -> Iterator[CorpusSettings]:
    url = os.environ.get("MERITUM_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("set MERITUM_TEST_DATABASE_URL to the meritum-postgres image")
    apply_corpus_migrations(url)
    with psycopg.connect(url, autocommit=True) as conn:
        if any(conn.execute(query).fetchone() for query in ANY_ROW):
            pytest.skip("the corpus has documents; use an empty test database")
    yield CorpusSettings(provider=CorpusProvider.POSTGRES, database_url=url)
    with psycopg.connect(url, autocommit=True) as conn:
        for query in EMPTY:
            conn.execute(query)


@pytest.mark.integration
def test_new_snapshot_adds_documents_and_the_old_one_replays(
    settings: CorpusSettings,
) -> None:
    """Gherkin: nowa migawka według harmonogramu (worker#17)."""
    embeddings = build_embeddings(EmbeddingsSettings())
    store = corpus.build_corpus_writer(settings)
    site = FakeCatalogSite(pages_per_domain=3)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=embeddings,
        store=store,
        injection=CleanInjectionDetector(),
    )
    search = build_corpus_search(settings, embeddings)
    query = "komunikat urzędowy"
    # Given korpus w wersji 2026-11-20T10:00Z
    asyncio.run(corpus.ingest_catalog([ENTRY], deps, now=NOW))
    hour = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    old = asyncio.run(corpus.take_snapshot(store, scheduled=hour))
    seen = asyncio.run(
        search.search(
            query, claim_date=date(2026, 11, 20), corpus_version=old.version, limit=50
        )
    )
    # and nowe dokumenty: a changed page and a live-search page after the scan
    site.set_text("https://urzad.gov.pl/strona-0", "Zmieniony komunikat urzędowy.")
    later = NOW + timedelta(days=1)
    asyncio.run(corpus.ingest_catalog([ENTRY], deps, now=later))
    page = FetchedPage(
        url="https://urzad.gov.pl/live",
        content_type="text/html",
        untrusted_text="Komunikat urzędowy z wyszukiwania na żywo.",
    )
    asyncio.run(corpus.store_page(page, ENTRY, deps, now=later))
    # When mija termin kolejnej migawki
    new = asyncio.run(corpus.take_snapshot(store, scheduled=hour + timedelta(hours=1)))
    # Then powstaje nowa corpus_version z tymi dokumentami
    assert new.version == "2026-11-20T11:00Z"
    assert new.taken_at > old.taken_at
    assert len(new.manifest) == len(old.manifest) + 1
    assert {m.fetched_at for m in new.manifest} == {later}
    # And sprawdzenia z poprzednią wersją dalej się odtwarzają
    assert asyncio.run(store.snapshot(old.version)) == old
    again = asyncio.run(
        search.search(
            query, claim_date=date(2026, 11, 20), corpus_version=old.version, limit=50
        )
    )
    # ties of the stub embeddings may come back in any order
    assert {p.passage_id for p in again} == {p.passage_id for p in seen}
    fresh = asyncio.run(
        search.search(
            query, claim_date=date(2026, 11, 21), corpus_version=new.version, limit=50
        )
    )
    assert {p.passage_id for p in fresh} != {p.passage_id for p in seen}


@pytest.mark.integration
def test_documents_keep_catalog_metadata_and_full_text(
    settings: CorpusSettings,
) -> None:
    store = corpus.build_corpus_writer(settings)
    site = FakeCatalogSite(pages_per_domain=2)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=CleanInjectionDetector(),
    )
    report = asyncio.run(corpus.ingest_catalog([ENTRY], deps, now=NOW))
    assert report == corpus.IngestReport(added=2)
    documents = asyncio.run(store.documents())
    assert {(d.publisher_id, d.license, d.fetched_at) for d in documents} == {
        ("urzad", "CC BY 4.0", NOW)
    }
    assert asyncio.run(store.last_attempt("urzad.gov.pl")) == NOW
    assert asyncio.run(store.last_attempt("inny.gov.pl")) is None
    url = os.environ["MERITUM_TEST_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        texts = conn.execute("SELECT full_text FROM corpus.documents").fetchall()
    assert all(text and "Komunikat" in text for (text,) in texts)
    again = asyncio.run(
        corpus.ingest_catalog([ENTRY], deps, now=NOW + timedelta(days=1))
    )
    assert again == corpus.IngestReport(unchanged=2)


@pytest.mark.integration
def test_documents_keep_the_way_they_came_into_the_corpus(
    settings: CorpusSettings,
) -> None:
    """Gherkin: dokument z kanału RSS zapisuje drogę pozyskania (worker#154)."""
    store = corpus.build_corpus_writer(settings)
    site = FakeCatalogSite(pages_per_domain=1)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=CleanInjectionDetector(),
    )
    asyncio.run(corpus.ingest_catalog([ENTRY], deps, now=NOW))
    page = FetchedPage(
        url="https://urzad.gov.pl/komunikat",
        content_type="text/html",
        untrusted_text="Komunikat urzędowy z kanału RSS.",
    )
    found = corpus.DiscoveredPage(url=page.url, via="rss")
    asyncio.run(corpus.store_page(page, ENTRY, deps, now=NOW, found=found))
    url = os.environ["MERITUM_TEST_DATABASE_URL"]
    with psycopg.connect(url) as conn:
        rows = conn.execute("SELECT url, via FROM corpus.documents").fetchall()
    assert dict(rows) == {
        "https://urzad.gov.pl/strona-0": "corpus",
        "https://urzad.gov.pl/komunikat": "rss",
    }
    assert {d.via for d in asyncio.run(store.documents())} == {"corpus", "rss"}
