"""Corpus retention over ``corpus.documents``, ``passages`` and the removal ledger.

``corpus.documents`` and ``passages`` come from meritum-core's corpus migrations
0001 and 0003; the ledger ``corpus.publisher_removals`` from migration 0006
(worker#77). A removal takes ``CORPUS_WRITE_LOCK`` shared, like a document write,
so a snapshot never sees half of it.

Features:
    US-KOR-05, F-10, ADR-13, ADR-32
"""

from dataclasses import dataclass
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import class_row

from meritum_worker.corpus.constants import CORPUS_WRITE_LOCK
from meritum_worker.corpus.removals import PublisherRemoval, PublisherRemovalRequest


@dataclass(frozen=True)
class _Text:
    full_text: str | None


class PostgresCorpusRetention:
    """CorpusRetentionPort over the shared ``corpus`` schema.

    Args:
        conninfo: libpq connection string of a role that may write ``corpus``.

    Features:
        US-KOR-05, F-10, ADR-13, ADR-32
    """

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    async def full_text(self, source_id: str) -> str | None:
        """Return a document's text (see ``CorpusWriterPort.full_text``).

        Args:
            source_id: The document.

        Returns:
            The text or None.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = conn.cursor(row_factory=class_row(_Text))
            await cursor.execute(
                "SELECT full_text FROM corpus.documents"
                " WHERE source_id = %s AND retired_at IS NULL",
                (source_id,),
            )
            row = await cursor.fetchone()
            return None if row is None else row.full_text

    async def clear_full_texts(self, *, fetched_before: datetime, limit: int) -> int:
        """Clear old texts (see ``CorpusWriterPort.clear_full_texts``).

        A refetch committed meanwhile moved ``fetched_at``, so the outer check
        keeps its new text.

        Args:
            fetched_before: The retention cutoff.
            limit: The most documents cleared.

        Returns:
            How many were cleared.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(
                """
UPDATE corpus.documents SET full_text = NULL
WHERE fetched_at < %(cutoff)s AND source_id IN (
    SELECT source_id FROM corpus.documents
    WHERE full_text IS NOT NULL AND fetched_at < %(cutoff)s
    ORDER BY fetched_at LIMIT %(limit)s FOR UPDATE SKIP LOCKED)
""",
                {"cutoff": fetched_before, "limit": limit},
            )
            return cursor.rowcount

    async def remove_for_publisher(
        self, request: PublisherRemovalRequest, removed_at: datetime
    ) -> PublisherRemoval:
        """Remove a publisher's page in one transaction (see the port).

        Args:
            request: The publisher's request.
            removed_at: When the removal runs.

        Returns:
            The ledger row.
        """
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.cursor() as cursor,
        ):
            await cursor.execute(
                "SELECT pg_advisory_xact_lock_shared(%s)", (CORPUS_WRITE_LOCK,)
            )
            await cursor.execute(
                "DELETE FROM corpus.documents WHERE url = %s AND publisher_id = %s"
                " RETURNING source_id",
                (request.url, request.publisher_id),
            )
            gone = [source_id for (source_id,) in await cursor.fetchall()]
            await cursor.execute(
                "DELETE FROM corpus.passages WHERE source_id = ANY(%s)", (gone,)
            )
            removal = PublisherRemoval(
                **request.model_dump(), removed_at=removed_at, documents=len(gone)
            )
            await cursor.execute(
                """
INSERT INTO corpus.publisher_removals (url, publisher_id, requested_at,
    removed_at, documents)
VALUES (%(url)s, %(publisher_id)s, %(requested_at)s, %(removed_at)s, %(documents)s)
ON CONFLICT (url, publisher_id, requested_at) DO NOTHING
""",
                removal.model_dump(),
            )
            return removal

    async def removals(self) -> list[PublisherRemoval]:
        """Return the ledger (see ``CorpusWriterPort.removals``).

        Returns:
            Every removal, oldest first.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = conn.cursor(row_factory=class_row(PublisherRemoval))
            await cursor.execute(
                "SELECT url, publisher_id, requested_at, removed_at, documents"
                " FROM corpus.publisher_removals ORDER BY removed_at"
            )
            return await cursor.fetchall()
