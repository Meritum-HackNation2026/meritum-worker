"""Ports of the corpus slice: EUvsDisinfo sync, catalogue ingestion and snapshots.

They stay in the worker: only the worker writes the corpus (ADR-32).

Features:
    US-KOR-08, US-KOR-02, US-KOR-03, F-11, F-12, F-13, ADR-32
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.security.injection import InjectionDetectorPort
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.corpus.documents import (
    CorpusSnapshot,
    DiscoveredPage,
    Document,
    DocumentMeta,
    DocumentPassage,
    LegalActs,
)
from meritum_worker.corpus.models import EuvsArticle, EuvsCase, StoredEntry


@runtime_checkable
class EuvsDisinfoPort(Protocol):
    """Paged reads of the EUvsDisinfo database, newest first.

    Features:
        US-KOR-08, F-11, ADR-32
    """

    async def cases(self, *, limit: int, offset: int) -> list[EuvsCase]:
        """Return one page of disinformation cases.

        Args:
            limit: Page size, 1 to 100.
            offset: Cases to skip.

        Returns:
            The page; shorter than ``limit`` on the last page.

        Raises:
            EuvsDisinfoUnavailableError: The server failed or the token is invalid.
        """
        ...

    async def articles(self, *, limit: int, offset: int) -> list[EuvsArticle]:
        """Return one page of analytical articles.

        Args:
            limit: Page size, 1 to 100.
            offset: Articles to skip.

        Returns:
            The page; shorter than ``limit`` on the last page.

        Raises:
            EuvsDisinfoUnavailableError: The server failed or the token is invalid.
        """
        ...


@runtime_checkable
class EuvsCopyPort(Protocol):
    """The local copy of EUvsDisinfo, written only by the sync workflow.

    Features:
        US-KOR-08, F-11
    """

    async def entries(self) -> list[StoredEntry]:
        """Return every stored entry, deleted ones included.

        Returns:
            The entries in no particular order.
        """
        ...

    async def upsert(self, entries: Sequence[StoredEntry]) -> None:
        """Add new entries and replace changed ones, keyed by ``entry.key``.

        Args:
            entries: Entries to write.
        """
        ...

    async def mark_deleted(self, keys: Sequence[str], at: datetime) -> None:
        """Mark entries that vanished from the source; they stay in the copy.

        Args:
            keys: Entry keys.
            at: When the sync noticed.
        """
        ...

    async def flagged_domains(self) -> dict[str, tuple[str, ...]]:
        """Return the domains the domain warning reads (worker/010).

        Returns:
            Domain to the keys of live cases that link to it.
        """
        ...

    async def replace_flagged_domains(
        self, domains: Mapping[str, tuple[str, ...]]
    ) -> None:
        """Replace the domains the domain warning reads (worker/010).

        Args:
            domains: Domain to the keys of live cases that link to it.
        """
        ...


@runtime_checkable
class DocumentDiscoveryPort(Protocol):
    """Finds the pages of one catalogue entry to ingest.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """

    async def pages(self, entry: CatalogEntry) -> list[DiscoveredPage]:
        """Return the entry's pages: the entry page, or what its feed lists.

        Args:
            entry: An ingestible catalogue entry.

        Returns:
            The pages, newest first, with the feed's publication date.

        Raises:
            DiscoveryError: The feed or sitemap could not be fetched or read.
        """
        ...


@runtime_checkable
class CorpusWriterPort(Protocol):
    """Writes catalogue documents, their passages and snapshots to ``corpus``.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-32
    """

    async def documents(self) -> list[DocumentMeta]:
        """Return the metadata of every live document, without the text.

        Returns:
            The documents in no particular order.
        """
        ...

    async def document(self, source_id: str) -> DocumentMeta | None:
        """Return one live document's metadata.

        Args:
            source_id: The document.

        Returns:
            The metadata, None when the corpus has no such document.
        """
        ...

    async def last_attempt(self, domain: str) -> datetime | None:
        """Return when the catalogue ingestion last tried a domain.

        Args:
            domain: A catalogue domain.

        Returns:
            The time, None when it was never tried.
        """
        ...

    async def record_attempt(self, domain: str, at: datetime) -> None:
        """Note that the catalogue ingestion tries a domain now, whatever the outcome.

        Args:
            domain: A catalogue domain.
            at: When the run started.
        """
        ...

    async def save_document(
        self, document: Document, passages: Sequence[DocumentPassage]
    ) -> None:
        """Add or replace a document, keyed by ``source_id``, in one transaction.

        Args:
            document: The document with its full text.
            passages: Its new passages; they retire the earlier ones, which old
                snapshots keep. Empty when the text did not change.
        """
        ...

    async def take_snapshot(self, version: str) -> CorpusSnapshot:
        """Take snapshot ``version`` after every finished write, or return it.

        Args:
            version: The snapshot name; taking it again returns the first one.

        Returns:
            The snapshot with the manifest of every live document.
        """
        ...

    async def snapshot(self, version: str) -> CorpusSnapshot | None:
        """Return a snapshot taken earlier.

        Args:
            version: The snapshot name.

        Returns:
            The snapshot, None when there is none.
        """
        ...


@dataclass(frozen=True)
class IngestDeps:
    """The ports one ingestion run uses.

    Attributes:
        discovery: Finds each entry's pages.
        fetcher: The SSRF-safe fetcher from core; honours robots.txt and Content-Signal.
        embeddings: Multilingual embeddings for passages.
        store: The corpus writer.
        injection: The detector every page is scanned with before it is stored.
        api_fetcher: Core's fetcher over a transport that passes JSON on as
            text, for ``ingest: api`` entries; None leaves them unsupported.
        legal: The acts the Sejm's entry reads in full; none by default.

    Features:
        US-KOR-02, US-KOR-05, US-BEZ-01, F-10, F-12, F-19, ADR-32
    """

    discovery: DocumentDiscoveryPort
    fetcher: PageFetcherPort
    embeddings: EmbeddingsPort
    store: CorpusWriterPort
    injection: InjectionDetectorPort
    api_fetcher: PageFetcherPort | None = None
    legal: LegalActs = field(default_factory=LegalActs)
