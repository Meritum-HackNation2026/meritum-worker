"""Steps of the corpus retention and publisher removal scenarios (security.feature).

They run on the in-memory corpus writer and app repositories; no DBOS, no database.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from behave import given, then, when
from behave.runner import Context
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.corpus import Document, DocumentPassage, PublisherRemovalRequest
from meritum_worker.corpus.fakes import MemoryCorpusWriter
from meritum_worker.security import (
    InMemoryWorkflowStore,
    build_retention_deps,
    removal_is_late,
    remove_publisher_document,
    run_retention,
)

NOW = datetime.now(UTC)
SOURCE, PASSAGE = "src_gus_1", "src_gus_1:abc:1"
URL, PUBLISHER = "https://stat.gov.pl/obszary-tematyczne/1", "gus"


def _seed(context: Context, age: timedelta) -> None:
    document = Document(
        source_id=SOURCE,
        url=URL,
        domain="stat.gov.pl",
        publisher_id=PUBLISHER,
        license="CC-BY-4.0",
        fetched_at=NOW - age,
        checksum="c" * 64,
        full_text="Przeciętne wynagrodzenie wyniosło 8 000 zł.",
    )
    passage = DocumentPassage(
        passage_id=PASSAGE, text="Przeciętne wynagrodzenie", embedding=(0.1, 0.2)
    )
    context.corpus = MemoryCorpusWriter()
    asyncio.run(context.corpus.save_document(document, [passage]))


@given("dokument z fetched_at sprzed 91 dni")
def old_document(context: Context) -> None:
    _seed(context, timedelta(days=91))


@when("workflow retencji działa")
def corpus_retention_runs(context: Context) -> None:
    deps = build_retention_deps(
        DatabaseSettings(provider="memory"),
        None,
        workflows=InMemoryWorkflowStore(),
        corpus_store=context.corpus,
    )
    context.report = asyncio.run(run_retention(deps, NOW))


@then(
    "pełny tekst jest usunięty, a metadane i fragmenty cytowane w istniejących"
    " zapisach zostają"
)
def full_text_is_gone(context: Context) -> None:
    store = context.corpus
    assert context.report.full_texts == 1
    assert asyncio.run(store.full_text(SOURCE)) is None
    meta = asyncio.run(store.document(SOURCE))
    assert meta is not None
    assert meta.url == URL
    assert PASSAGE in store.passages


@given("wydawca prosi o usunięcie dokumentu")
def publisher_asks(context: Context) -> None:
    _seed(context, timedelta(days=10))
    context.request = PublisherRemovalRequest(
        url=URL, publisher_id=PUBLISHER, requested_at=NOW - timedelta(days=1)
    )


@when("workflow usuwania na wniosek wydawcy kończy się")
def publisher_removal_finishes(context: Context) -> None:
    context.removal = asyncio.run(
        remove_publisher_document(context.corpus, context.request, NOW)
    )


@then("dokumentu nie ma w korpusie, a wniosek jest zapisany w ewidencji")
def document_is_gone_and_logged(context: Context) -> None:
    store = context.corpus
    assert asyncio.run(store.document(SOURCE)) is None
    assert asyncio.run(store.full_text(SOURCE)) is None
    assert PASSAGE not in store.passages
    ledger = asyncio.run(store.removals())
    assert [(r.url, r.publisher_id, r.documents) for r in ledger] == [
        (URL, PUBLISHER, 1)
    ]
    assert not removal_is_late(ledger[0])
