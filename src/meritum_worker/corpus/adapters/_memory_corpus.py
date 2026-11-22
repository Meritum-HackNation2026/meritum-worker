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


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _meta(document: Document) -> DocumentMeta:
    return DocumentMeta.model_validate(document.model_dump(exclude={"full_text"}))


class MemoryCorpusWriter:
    """Documents, passages and snapshots held in process.

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
