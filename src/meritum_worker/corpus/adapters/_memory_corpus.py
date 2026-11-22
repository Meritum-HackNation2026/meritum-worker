"""In-memory corpus writer: the fake for tests and runs without a database.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-19
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from meritum_worker.corpus.documents import (
    CorpusSnapshot,
    Document,
    DocumentMeta,
    DocumentPassage,
    ManifestEntry,
)
from meritum_worker.corpus.removals import PublisherRemoval, PublisherRemovalRequest


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _meta(document: Document) -> DocumentMeta:
    return DocumentMeta.model_validate(document.model_dump(exclude={"full_text"}))


class MemoryCorpusWriter:
    """Documents, passages, snapshots and the removal ledger held in process.

    It is the in-memory CorpusRetentionPort too.

    Args:
        clock: Gives a snapshot's ``taken_at``; the wall clock by default.

    Attributes:
        passages: Every passage written, retired ones included, by id.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19
    """

    def __init__(self, clock: Callable[[], datetime] = _utc_now) -> None:
        self._clock = clock
        self._documents: dict[str, Document] = {}
        self._cleared: set[str] = set()
        self._passage_sources: dict[str, str] = {}
        self._removals: list[PublisherRemoval] = []
        self._snapshots: dict[str, CorpusSnapshot] = {}
        self._attempts: dict[str, datetime] = {}
        self.passages: dict[str, DocumentPassage] = {}

    async def documents(self) -> list[DocumentMeta]:
        """Return live documents (see ``CorpusWriterPort.documents``).

        Returns:
            Their metadata.
        """
        return [_meta(d) for d in self._documents.values()]

    async def document(self, source_id: str) -> DocumentMeta | None:
        """Return one document (see ``CorpusWriterPort.document``).

        Args:
            source_id: The document.

        Returns:
            Its metadata or None.
        """
        found = self._documents.get(source_id)
        return None if found is None else _meta(found)

    async def last_attempt(self, domain: str) -> datetime | None:
        """Return a domain's last attempt (see ``CorpusWriterPort.last_attempt``).

        Args:
            domain: The catalogue domain.

        Returns:
            The time or None.
        """
        return self._attempts.get(domain)

    async def record_attempt(self, domain: str, at: datetime) -> None:
        """Note an attempt (see ``CorpusWriterPort.record_attempt``).

        Args:
            domain: The catalogue domain.
            at: When.
        """
        self._attempts[domain] = at

    async def save_document(
        self, document: Document, passages: Sequence[DocumentPassage]
    ) -> None:
        """Write a document (see ``CorpusWriterPort.save_document``).

        Args:
            document: The document.
            passages: Its new passages.
        """
        self._documents[document.source_id] = document
        self._cleared.discard(document.source_id)
        self._passage_sources.update(
            (p.passage_id, document.source_id) for p in passages
        )
        self.passages.update((p.passage_id, p) for p in passages)

    async def take_snapshot(self, version: str) -> CorpusSnapshot:
        """Take a snapshot (see ``CorpusWriterPort.take_snapshot``).

        Args:
            version: The snapshot name.

        Returns:
            The snapshot.
        """
        if version not in self._snapshots:
            manifest = tuple(
                ManifestEntry(
                    source_id=d.source_id, checksum=d.checksum, fetched_at=d.fetched_at
                )
                for d in sorted(self._documents.values(), key=lambda d: d.source_id)
            )
            self._snapshots[version] = CorpusSnapshot(
                version=version, taken_at=self._clock(), manifest=manifest
            )
        return self._snapshots[version]

    async def snapshot(self, version: str) -> CorpusSnapshot | None:
        """Return a snapshot (see ``CorpusWriterPort.snapshot``).

        Args:
            version: The snapshot name.

        Returns:
            The snapshot or None.
        """
        return self._snapshots.get(version)

    async def full_text(self, source_id: str) -> str | None:
        """Return a document's text (see ``CorpusWriterPort.full_text``).

        Args:
            source_id: The document.

        Returns:
            The text or None.
        """
        found = self._documents.get(source_id)
        if found is None or source_id in self._cleared:
            return None
        return found.full_text

    async def clear_full_texts(self, *, fetched_before: datetime, limit: int) -> int:
        """Clear old texts (see ``CorpusWriterPort.clear_full_texts``).

        Args:
            fetched_before: The retention cutoff.
            limit: The most documents cleared.

        Returns:
            How many were cleared.
        """
        due = [
            d.source_id
            for d in self._documents.values()
            if d.fetched_at < fetched_before and d.source_id not in self._cleared
        ][:limit]
        self._cleared.update(due)
        return len(due)

    async def remove_for_publisher(
        self, request: PublisherRemovalRequest, removed_at: datetime
    ) -> PublisherRemoval:
        """Remove a publisher's page (see ``CorpusWriterPort.remove_for_publisher``).

        Args:
            request: The publisher's request.
            removed_at: When the removal runs.

        Returns:
            The ledger row.
        """
        gone = {
            d.source_id
            for d in self._documents.values()
            if d.url == request.url and d.publisher_id == request.publisher_id
        }
        for source_id in gone:
            del self._documents[source_id]
            self._cleared.discard(source_id)
        for passage_id, source_id in list(self._passage_sources.items()):
            if source_id in gone:
                del self.passages[passage_id], self._passage_sources[passage_id]
        removal = PublisherRemoval(
            **request.model_dump(), removed_at=removed_at, documents=len(gone)
        )
        self._removals.append(removal)
        return removal

    async def removals(self) -> list[PublisherRemoval]:
        """Return the ledger (see ``CorpusWriterPort.removals``).

        Returns:
            Every removal, oldest first.
        """
        return list(self._removals)
