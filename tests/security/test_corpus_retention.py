"""Which corpus documents retention and a publisher's request select; in memory."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.corpus import Document, DocumentPassage, PublisherRemovalRequest
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.security import (
    InMemoryWorkflowStore,
    build_retention_deps,
    removal_is_late,
    remove_publisher_document,
    run_retention,
)

NOW = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
PUBLISHER = "gus"


def _document(source_id: str, age: timedelta, publisher: str = PUBLISHER) -> Document:
    return Document(
        source_id=source_id,
        url=f"https://stat.gov.pl/{source_id}",
        domain="stat.gov.pl",
        publisher_id=publisher,
        license="CC-BY-4.0",
        fetched_at=NOW - age,
        checksum="c" * 64,
        full_text=f"Tekst {source_id}",
    )


def _passage(source_id: str) -> DocumentPassage:
    return DocumentPassage(
        passage_id=f"{source_id}_p0", text="Fragment", embedding=(0.1, 0.2)
    )


def _store(*documents: Document) -> MemoryCorpusWriter:
    store = MemoryCorpusWriter()
    for document in documents:
        asyncio.run(store.save_document(document, [_passage(document.source_id)]))
    return store


def _retention(store: MemoryCorpusWriter) -> int:
    deps = build_retention_deps(
        DatabaseSettings(provider="memory"),
        None,
        workflows=InMemoryWorkflowStore(),
        corpus_store=store,
    )
    return asyncio.run(run_retention(deps, NOW)).full_texts


def test_retention_clears_full_texts_fetched_more_than_90_days_ago() -> None:
    store = _store(
        _document("old", timedelta(days=91)),
        _document("fresh", timedelta(days=89)),
    )
    assert _retention(store) == 1
    assert asyncio.run(store.full_text("old")) is None
    assert asyncio.run(store.full_text("fresh")) == "Tekst fresh"
    assert asyncio.run(store.document("old")) is not None
    assert "old_p0" in store.passages


def test_refetch_restarts_the_period_and_a_second_run_clears_nothing() -> None:
    store = _store(_document("doc", timedelta(days=91)))
    asyncio.run(store.save_document(_document("doc", timedelta(days=1)), []))
    assert _retention(store) == 0
    assert asyncio.run(store.full_text("doc")) == "Tekst doc"
    old = _store(_document("doc", timedelta(days=100)))
    assert _retention(old) == 1
    assert _retention(old) == 0


def test_publisher_request_removes_only_its_document_and_is_recorded() -> None:
    store = _store(
        _document("doc", timedelta(days=3)), _document("other", timedelta(days=3))
    )
    request = PublisherRemovalRequest(
        url="https://stat.gov.pl/doc",
        publisher_id=PUBLISHER,
        requested_at=NOW - timedelta(days=2),
    )
    removal = asyncio.run(remove_publisher_document(store, request, NOW))
    assert removal.documents == 1
    assert removal.removed_at == NOW
    assert asyncio.run(store.document("doc")) is None
    assert asyncio.run(store.full_text("doc")) is None
    assert "doc_p0" not in store.passages
    assert asyncio.run(store.document("other")) is not None
    assert asyncio.run(store.removals()) == [removal]


def test_publisher_cannot_remove_another_publishers_document() -> None:
    store = _store(_document("doc", timedelta(days=3), publisher="nbp"))
    request = PublisherRemovalRequest(
        url="https://stat.gov.pl/doc", publisher_id=PUBLISHER, requested_at=NOW
    )
    removal = asyncio.run(remove_publisher_document(store, request, NOW))
    assert removal.documents == 0
    assert asyncio.run(store.document("doc")) is not None


def test_request_older_than_7_days_is_still_done_and_flagged_late() -> None:
    store = _store(_document("doc", timedelta(days=30)))
    request = PublisherRemovalRequest(
        url="https://stat.gov.pl/doc",
        publisher_id=PUBLISHER,
        requested_at=NOW - timedelta(days=8),
    )
    removal = asyncio.run(remove_publisher_document(store, request, NOW))
    assert removal.documents == 1
    assert removal_is_late(removal)


@pytest.mark.parametrize("url", ["", "ftp://stat.gov.pl/doc"])
def test_request_needs_an_http_url(url: str) -> None:
    with pytest.raises(ValueError, match="url"):
        PublisherRemovalRequest(url=url, publisher_id=PUBLISHER, requested_at=NOW)
