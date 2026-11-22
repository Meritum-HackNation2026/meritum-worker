"""Storing one fetched page: checksum, passages, embeddings and the document row.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-21
"""

import hashlib
from collections.abc import Sequence
from datetime import date, datetime
from itertools import batched

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsPort, Vector
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.corpus.chunking import chunk_text
from meritum_worker.corpus.constants import (
    EMBED_BATCH,
    EMPTY_TEXT,
    ENTRY_NOT_INGESTIBLE,
    INJECTION_FOUND,
    PASSAGE_CHECKSUM_CHARS,
    SOURCE_ID_HASH_CHARS,
    SOURCE_ID_PREFIX,
    TDM_RESERVED,
    TDM_RESERVED_ENTRY,
)
from meritum_worker.corpus.documents import (
    DiscoveredPage,
    Document,
    DocumentPassage,
    IngestFailure,
    IngestReport,
)
from meritum_worker.corpus.ingest_constants import INJECTION_UNAVAILABLE
from meritum_worker.corpus.ports import IngestDeps


async def store_page(
    page: FetchedPage,
    entry: CatalogEntry,
    deps: IngestDeps,
    *,
    now: datetime,
    found: DiscoveredPage | None = None,
) -> IngestReport:
    """Store one fetched page of a catalogue domain; it joins the next snapshot.

    Also the way in for a page from live web search once it passed the scan
    (ADR-21). Unchanged text keeps its passages and only moves ``fetched_at``.

    Args:
        page: The fetched page.
        entry: The page's catalogue entry (publisher, licence).
        deps: The ports; ``injection``, ``embeddings`` and ``store`` are used.
        now: The page's ``fetched_at``.
        found: The discovered page it was fetched for: its URL and feed date
            win over ``page.url`` and the page's metadata; None for live search.

    Returns:
        One added, updated or unchanged document, or one failure; a page of an
        excluded or TDM-reserved entry, one carrying an instruction for the
        model, or one the injection detector could not scan (its classifier's
        provider failed), is always a failure.

    Features:
        US-KOR-02, US-KOR-05, US-BEZ-01, F-10, F-12, F-19, ADR-21
    """
    url = found.url if found else page.url
    text = page.untrusted_text.strip()
    rejected = await _rejection(page, entry, text, deps)
    if rejected is not None:
        return failed_page(entry, url, rejected)
    published_on = (found.published_on if found else None) or page.published_at
    document = _document(entry, url, text, now, published_on)
    previous = await deps.store.document(document.source_id)
    if previous is not None and previous.checksum == document.checksum:
        await deps.store.save_document(document, [])
        return IngestReport(unchanged=1)
    await deps.store.save_document(document, await _passages(document, deps))
    return IngestReport(added=int(previous is None), updated=int(previous is not None))


async def _rejection(
    page: FetchedPage, entry: CatalogEntry, text: str, deps: IngestDeps
) -> str | None:
    if entry.excluded or entry.tdm_reservation == TDM_RESERVED_ENTRY:
        return ENTRY_NOT_INGESTIBLE
    if page.tdm_reserved:
        return TDM_RESERVED
    if not text:
        return EMPTY_TEXT
    try:
        scan = await deps.injection.scan(text)
    except ProviderUnavailableError:  # unscanned text never enters the corpus
        return INJECTION_UNAVAILABLE
    return INJECTION_FOUND if scan.detected else None


def failed_page(
    entry: CatalogEntry, url: str, reason: str, *, at: datetime | None = None
) -> IngestReport:
    """A report with one failed page.

    Args:
        entry: The page's catalogue entry.
        url: The page.
        reason: Why it failed.
        at: When the run started; None outside a run.

    Returns:
        The report.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """
    failure = IngestFailure(domain=entry.domain, url=url, reason=reason, at=at)
    return IngestReport(failures=(failure,))


def source_id_for(url: str) -> str:
    """The ``source_id`` a page fetched from ``url`` is stored under.

    Args:
        url: The page.

    Returns:
        ``doc-`` and a hash of the URL.

    Features:
        US-KOR-02, US-KOR-03, F-10, F-13
    """
    return f"{SOURCE_ID_PREFIX}{_sha256(url)[:SOURCE_ID_HASH_CHARS]}"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _document(
    entry: CatalogEntry, url: str, text: str, now: datetime, published_on: date | None
) -> Document:
    return Document(
        source_id=source_id_for(url),
        url=url,
        domain=entry.domain,
        publisher_id=entry.publisher_id,
        license=entry.license,
        published_on=published_on,
        fetched_at=now,
        checksum=_sha256(text),
        full_text=text,
    )


async def _passages(document: Document, deps: IngestDeps) -> list[DocumentPassage]:
    texts = chunk_text(document.full_text)
    vectors = await _embed(texts, deps.embeddings)
    # Text and fetch time: a text that comes back after a change gets new ids,
    # so a retired passage never reappears in an old snapshot.
    checksum = document.checksum[:PASSAGE_CHECKSUM_CHARS]
    prefix = f"{document.source_id}:{checksum}:{int(document.fetched_at.timestamp())}"
    return [
        DocumentPassage(passage_id=f"{prefix}:{i}", text=text, embedding=vector)
        for i, (text, vector) in enumerate(zip(texts, vectors, strict=True))
    ]


async def _embed(texts: Sequence[str], embeddings: EmbeddingsPort) -> list[Vector]:
    vectors: list[Vector] = []
    for chunk in batched(texts, EMBED_BATCH, strict=False):
        vectors += await embeddings.embed_documents(chunk)
    return vectors
