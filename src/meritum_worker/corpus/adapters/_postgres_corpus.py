"""Corpus writer over the shared ``corpus`` schema (documents, passages, snapshots).

The tables come from meritum-core's corpus migrations 0001, 0003 and 0007
(``documents.via``). Document
writes take ``CORPUS_WRITE_LOCK`` shared and a snapshot takes it exclusive, so
``taken_at`` (the database clock) follows every write it covers and no later
commit can change a published snapshot (ADR-19).

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-32
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import class_row

from meritum_worker.corpus.constants import CORPUS_WRITE_LOCK
from meritum_worker.corpus.documents import (
    CorpusSnapshot,
    Document,
    DocumentMeta,
    DocumentPassage,
    ManifestEntry,
)


@dataclass(frozen=True)
class _Attempt:
    attempted_at: datetime


class PostgresCorpusWriter:
    """CorpusWriterPort over ``corpus.documents``, ``passages`` and snapshots.

    Args:
        conninfo: libpq connection string of a role that may write ``corpus``.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-32
    """

    def __init__(self, conninfo: str) -> None:
        # shortcut: one connection per call, each call one transaction (psycopg
        # commits on a clean exit); take a pool if ingestion gets slow.
        self._conninfo = conninfo

    async def documents(self) -> list[DocumentMeta]:
        """Return live documents (see ``CorpusWriterPort.documents``).

        Returns:
            Their metadata.
        """
        return await self._metas(None)

    async def document(self, source_id: str) -> DocumentMeta | None:
        """Return one document (see ``CorpusWriterPort.document``).

        Args:
            source_id: The document.

        Returns:
            Its metadata or None.
        """
        found = await self._metas(source_id)
        return found[0] if found else None

    async def _metas(self, source_id: str | None) -> list[DocumentMeta]:
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = conn.cursor(row_factory=class_row(DocumentMeta))
            await cursor.execute(
                """
                SELECT source_id, url, domain, publisher_id, license,
                    published_on, fetched_at, checksum, via
                FROM corpus.documents
                WHERE retired_at IS NULL
                  AND (%(id)s::text IS NULL OR source_id = %(id)s)
                """,
                {"id": source_id},
            )
            return await cursor.fetchall()

    async def last_attempt(self, domain: str) -> datetime | None:
        """Return a domain's last attempt (see ``CorpusWriterPort.last_attempt``).

        Args:
            domain: The catalogue domain.

        Returns:
            The time or None.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = conn.cursor(row_factory=class_row(_Attempt))
            await cursor.execute(
                "SELECT attempted_at FROM corpus.ingest_attempts WHERE domain = %s",
                (domain,),
            )
            row = await cursor.fetchone()
            return None if row is None else row.attempted_at

    async def record_attempt(self, domain: str, at: datetime) -> None:
        """Note an attempt (see ``CorpusWriterPort.record_attempt``).

        Args:
            domain: The catalogue domain.
            at: When.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(
                "INSERT INTO corpus.ingest_attempts (domain, attempted_at)"
                " VALUES (%s, %s) ON CONFLICT (domain)"
                " DO UPDATE SET attempted_at = excluded.attempted_at",
                (domain, at),
            )

    async def save_document(
        self, document: Document, passages: Sequence[DocumentPassage]
    ) -> None:
        """Write a document in one transaction (see the port).

        Args:
            document: The document.
            passages: Its new passages; they retire the earlier ones.
        """
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.cursor() as cursor,
        ):
            await cursor.execute(
                "SELECT pg_advisory_xact_lock_shared(%s)", (CORPUS_WRITE_LOCK,)
            )
            await cursor.execute(
                """
INSERT INTO corpus.documents (source_id, url, domain, publisher_id, license,
    published_on, fetched_at, checksum, full_text, via, added_at)
VALUES (%(source_id)s, %(url)s, %(domain)s, %(publisher_id)s, %(license)s,
    %(published_on)s, %(fetched_at)s, %(checksum)s, %(full_text)s, %(via)s,
    clock_timestamp())
ON CONFLICT (source_id) DO UPDATE SET url = excluded.url, domain = excluded.domain,
    publisher_id = excluded.publisher_id, license = excluded.license,
    published_on = excluded.published_on, fetched_at = excluded.fetched_at,
    checksum = excluded.checksum, full_text = excluded.full_text, via = excluded.via,
    retired_at = NULL
""",
                document.model_dump(),
            )
            if not passages:
                return
            await cursor.execute(
                (
                    "UPDATE corpus.passages SET retired_at = clock_timestamp()"
                    " WHERE source_id = %s AND retired_at IS NULL"
                ),
                (document.source_id,),
            )
            await cursor.executemany(
                """
INSERT INTO corpus.passages (passage_id, source_id, text, published_on,
    fetched_at, added_at, embedding)
VALUES (%s, %s, %s, %s, %s, clock_timestamp(), %s::vector)
ON CONFLICT (passage_id) DO NOTHING
""",
                [_passage_row(document, p) for p in passages],
            )

    async def take_snapshot(self, version: str) -> CorpusSnapshot:
        """Take a snapshot in one transaction (see the port).

        Args:
            version: The snapshot name.

        Returns:
            The snapshot, the existing one when already taken.

        Raises:
            LookupError: The snapshot vanished right after it was written.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (CORPUS_WRITE_LOCK,))
            found = await _read_snapshot(conn, version)
            if found is not None:
                return found
            await conn.execute(
                (
                    "INSERT INTO corpus.snapshots (version, taken_at)"
                    " VALUES (%s, clock_timestamp())"
                ),
                (version,),
            )
            await conn.execute(
                """
INSERT INTO corpus.snapshot_manifest (version, source_id, checksum, fetched_at)
SELECT %s, source_id, checksum, fetched_at FROM corpus.documents
WHERE retired_at IS NULL
""",
                (version,),
            )
            snapshot = await _read_snapshot(conn, version)
        if snapshot is None:  # the insert above made it; only a bug gets here
            raise LookupError(version)
        return snapshot

    async def snapshot(self, version: str) -> CorpusSnapshot | None:
        """Return a snapshot (see ``CorpusWriterPort.snapshot``).

        Args:
            version: The snapshot name.

        Returns:
            The snapshot or None.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            return await _read_snapshot(conn, version)


async def _read_snapshot(conn: AsyncConnection, version: str) -> CorpusSnapshot | None:
    row = await (
        await conn.execute(
            ("SELECT taken_at FROM corpus.snapshots WHERE version = %s"), (version,)
        )
    ).fetchone()
    if row is None:
        return None
    cursor = conn.cursor(row_factory=class_row(ManifestEntry))
    await cursor.execute(
        (
            "SELECT source_id, checksum, fetched_at FROM corpus.snapshot_manifest"
            " WHERE version = %s ORDER BY source_id"
        ),
        (version,),
    )
    manifest = tuple(await cursor.fetchall())
    return CorpusSnapshot(version=version, taken_at=row[0], manifest=manifest)


def _passage_row(document: Document, passage: DocumentPassage) -> tuple[object, ...]:
    return (
        passage.passage_id,
        document.source_id,
        passage.text,
        document.published_on,
        document.fetched_at,
        json.dumps(list(passage.embedding)),  # pgvector's text form is a JSON array
    )
