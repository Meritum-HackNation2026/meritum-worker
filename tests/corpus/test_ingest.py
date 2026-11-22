import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.corpus.fetching import FetchedPage, FetchFailureReason, FetchPurpose
from meritum_core.shared.embeddings import (
    EmbeddingsSettings,
    EmbeddingsUnavailableError,
    Vector,
    build_embeddings,
)

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.constants import CHUNK_MAX_CHARS
from meritum_worker.corpus.fakes import FakeCatalogSite
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


def entry(domain: str = "urzad.gov.pl", **fields: object) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": "Urząd",
            "publisher_id": "urzad",
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY 4.0",
            "ingest": "static",
            "qualified_because": "Źródło z listy organizatora konkursu.",
            **fields,
        }
    )


def deps(site: FakeCatalogSite, store: MemoryCorpusWriter) -> corpus.IngestDeps:
    embeddings = build_embeddings(EmbeddingsSettings())
    return corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=embeddings,
        store=store,
        injection=CleanInjectionDetector(),
    )


def run(
    site: FakeCatalogSite, store: MemoryCorpusWriter, now: datetime = NOW
) -> corpus.IngestReport:
    return asyncio.run(corpus.ingest_catalog([entry()], deps(site, store), now=now))


def test_only_evidence_entries_that_may_be_mined_are_ingested() -> None:
    kept = entry("a.gov.pl")
    others = [
        entry("b.gov.pl", ingest="live"),
        entry("c.gov.pl", ingest="mcp"),
        entry("d.gov.pl", ingest="web_search"),
        entry("e.gov.pl", role="source_status"),
        entry("f.gov.pl", excluded=True, exclusion_reason="robots.txt"),
        entry("g.gov.pl", tdm_reservation="reserved"),
    ]
    rss = entry("h.gov.pl", ingest="rss")
    api = entry("api.gov.pl", ingest="api")
    assert corpus.ingestible([kept, *others, rss, api]) == [kept, rss, api]


def test_domain_whose_pages_all_fail_waits_its_refresh_minutes() -> None:
    site, store = FakeCatalogSite(pages_per_domain=1), MemoryCorpusWriter()
    site.fail("https://urzad.gov.pl/strona-0", FetchFailureReason.ROBOTS_DISALLOWED)
    run(site, store)
    assert run(site, store, now=NOW + timedelta(hours=1)) == corpus.IngestReport()
    assert len(site.fetched) == 1


def test_page_that_cannot_be_embedded_is_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site, store = FakeCatalogSite(pages_per_domain=2), MemoryCorpusWriter()
    embeddings = build_embeddings(EmbeddingsSettings())

    async def down(texts: Sequence[str]) -> list[Vector]:  # ruff: ignore[unused-async]  # replaces an async port method
        raise EmbeddingsUnavailableError(len(texts))

    monkeypatch.setattr(embeddings, "embed_documents", down)
    ports = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=embeddings,
        store=store,
        injection=CleanInjectionDetector(),
    )
    report = asyncio.run(corpus.ingest_catalog([entry()], ports, now=NOW))
    assert [f.reason for f in report.failures] == ["embeddings_unavailable"] * 2


def test_entry_is_due_after_its_refresh_minutes() -> None:
    every_hour = entry(refresh_minutes=60)
    assert corpus.is_due(every_hour, None, NOW)
    assert not corpus.is_due(every_hour, NOW - timedelta(minutes=59), NOW)
    assert corpus.is_due(every_hour, NOW - timedelta(minutes=60), NOW)
    assert not corpus.is_due(entry(), NOW - timedelta(hours=23), NOW)


def test_failed_page_is_reported_and_the_run_goes_on() -> None:
    site, store = FakeCatalogSite(pages_per_domain=3), MemoryCorpusWriter()
    site.fail("https://urzad.gov.pl/strona-1", FetchFailureReason.ROBOTS_DISALLOWED)
    report = run(site, store)
    assert report.added == 2
    assert [(f.url, f.reason) for f in report.failures] == [
        ("https://urzad.gov.pl/strona-1", "robots_disallowed")
    ]
    assert {purpose for _, purpose in site.fetched} == {FetchPurpose.SOURCE}


def test_blank_page_is_a_failure() -> None:
    site, store = FakeCatalogSite(pages_per_domain=1), MemoryCorpusWriter()
    site.set_text("https://urzad.gov.pl/strona-0", "  \n ")
    assert [f.reason for f in run(site, store).failures] == ["empty_text"]


def test_refetch_keeps_unchanged_text_and_replaces_changed_text() -> None:
    site, store = FakeCatalogSite(pages_per_domain=2), MemoryCorpusWriter()
    run(site, store)
    first = set(store.passages)
    site.set_text("https://urzad.gov.pl/strona-0", "Nowy komunikat.")
    later = NOW + timedelta(days=1)
    report = run(site, store, now=later)
    assert (report.added, report.updated, report.unchanged) == (0, 1, 1)
    assert len(set(store.passages) - first) == 1
    documents = asyncio.run(store.documents())
    assert {d.fetched_at for d in documents} == {later}


def test_entry_that_is_not_due_is_not_fetched() -> None:
    site, store = FakeCatalogSite(pages_per_domain=1), MemoryCorpusWriter()
    run(site, store)
    site.fetched.clear()
    assert run(site, store, now=NOW + timedelta(hours=1)) == corpus.IngestReport()
    assert site.fetched == []


def test_long_page_becomes_short_passages_with_embeddings() -> None:
    site, store = FakeCatalogSite(pages_per_domain=1), MemoryCorpusWriter()
    site.set_text("https://urzad.gov.pl/strona-0", "zdanie " * CHUNK_MAX_CHARS)
    run(site, store)
    assert len(store.passages) > 1
    for passage in store.passages.values():
        assert len(passage.text) <= CHUNK_MAX_CHARS
        assert any(passage.embedding)


def test_snapshot_is_named_after_its_hour_and_taken_once() -> None:
    store = MemoryCorpusWriter()
    run(FakeCatalogSite(pages_per_domain=2), store)
    at = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    first = asyncio.run(corpus.take_snapshot(store, scheduled=at))
    run(FakeCatalogSite(pages_per_domain=3), store, now=NOW + timedelta(days=1))
    again = asyncio.run(corpus.take_snapshot(store, scheduled=at))
    assert first.version == "2026-11-20T10:00Z"
    assert again == first
    assert len(first.manifest) == 2


def test_ingestion_runs_only_where_it_is_enabled() -> None:
    assert corpus.ingestion_enabled({"MERITUM_CORPUS_INGEST": "enabled"})
    assert not corpus.ingestion_enabled({})
    assert not corpus.ingestion_enabled({"MERITUM_CORPUS_INGEST": "yes"})


def test_entry_page_discovery_fetches_the_catalogue_domain() -> None:
    discovery = corpus.build_document_discovery()
    pages = asyncio.run(discovery.pages(entry("www.gov.pl/web/rcb")))
    assert [p.url for p in pages] == ["https://www.gov.pl/web/rcb"]


def test_gus_is_fetched_from_its_releases_page_not_the_login_home_page() -> None:
    discovery = corpus.build_document_discovery()
    pages = asyncio.run(discovery.pages(entry("stat.gov.pl")))
    assert [p.url for p in pages] == [
        "https://stat.gov.pl/sygnalne/komunikaty-i-obwieszczenia/"
    ]


def test_writer_follows_the_corpus_settings() -> None:
    assert isinstance(corpus.build_corpus_writer(), MemoryCorpusWriter)
    memory = CorpusSettings(provider=CorpusProvider.MEMORY)
    assert isinstance(corpus.build_corpus_writer(memory), MemoryCorpusWriter)
    broken = CorpusSettings.model_construct(provider=CorpusProvider.POSTGRES)
    with pytest.raises(ValueError, match="MERITUM_CORPUS_DATABASE_URL"):
        corpus.build_corpus_writer(broken)


@pytest.mark.parametrize(
    "fields",
    [
        {"excluded": True, "exclusion_reason": "robots.txt"},
        {"tdm_reservation": "reserved"},
    ],
)
def test_page_of_excluded_or_reserved_entry_is_never_stored(
    fields: dict[str, object],
) -> None:
    site, store = FakeCatalogSite(pages_per_domain=1), MemoryCorpusWriter()
    page = FetchedPage(
        url="https://urzad.gov.pl/live",
        content_type="text/html",
        untrusted_text="Tekst.",
    )
    report = asyncio.run(
        corpus.store_page(
            page, entry("urzad.gov.pl", **fields), deps(site, store), now=NOW
        )
    )
    assert [f.reason for f in report.failures] == ["entry_not_ingestible"]
    assert asyncio.run(store.documents()) == []
