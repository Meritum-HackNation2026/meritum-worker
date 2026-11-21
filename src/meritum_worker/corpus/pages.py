"""Storing one fetched page: checksum, passages, embeddings and the document row.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-21
"""

import hashlib
from collections.abc import Sequence
from datetime import datetime
from itertools import batched

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.embeddings import EmbeddingsPort, Vector

from meritum_worker.corpus.chunking import chunk_text
from meritum_worker.corpus.constants import (
    EMBED_BATCH,
    EMPTY_TEXT,
    ENTRY_NOT_INGESTIBLE,
    PASSAGE_CHECKSUM_CHARS,
    SOURCE_ID_HASH_CHARS,
    SOURCE_ID_PREFIX,
    TDM_RESERVED,
    TDM_RESERVED_ENTRY,
)
from meritum_worker.corpus.documents import (
    Document,
    DocumentPassage,
    IngestFailure,
    IngestReport,
)
from meritum_worker.corpus.ports import IngestDeps


async def store_page(
    page: FetchedPage,
    entry: CatalogEntry,
    deps: IngestDeps,
    *,
    now: datetime,
    url: str | None = None,
) -> IngestReport:
    """Store one fetched page of a catalogue domain; it joins the next snapshot.

    Also the way in for a page from live web search once it passed the scan
    (ADR-21). Unchanged text keeps its passages and only moves ``fetched_at``.

    Args:
        page: The fetched page.
        entry: The page's catalogue entry (publisher, licence).
        deps: The ports; only ``embeddings`` and ``store`` are used.
        now: The page's ``fetched_at``.
        url: The URL it was fetched from; ``page.url`` when None.

    Returns:
        One added, updated or unchanged document, or one failure; a page of an
        excluded or TDM-reserved entry is always a failure.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-21
    """
    url = url or page.url
    text = page.untrusted_text.strip()
    if entry.excluded or entry.tdm_reservation == TDM_RESERVED_ENTRY:
        return failed_page(entry, url, ENTRY_NOT_INGESTIBLE)
    if page.tdm_reserved:
        return failed_page(entry, url, TDM_RESERVED)
    if not text:
        return failed_page(entry, url, EMPTY_TEXT)
    document = _document(entry, url, text, now)
    previous = await deps.store.document(document.source_id)
    if previous is not None and previous.checksum == document.checksum:
        await deps.store.save_document(document, [])
        return IngestReport(unchanged=1)
    await deps.store.save_document(document, await _passages(document, deps))
    return IngestReport(added=int(previous is None), updated=int(previous is not None))


def failed_page(entry: CatalogEntry, url: str, reason: str) -> IngestReport:
    """A report with one failed page.

    Args:
        entry: The page's catalogue entry.
        url: The page.
        reason: Why it failed.

    Returns:
        The report.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """
    failure = IngestFailure(domain=entry.domain, url=url, reason=reason)
    return IngestReport(failures=(failure,))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _document(entry: CatalogEntry, url: str, text: str, now: datetime) -> Document:
    return Document(
        source_id=f"{SOURCE_ID_PREFIX}{_sha256(url)[:SOURCE_ID_HASH_CHARS]}",
        url=url,
        domain=entry.domain,
        publisher_id=entry.publisher_id,
        license=entry.license,
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
