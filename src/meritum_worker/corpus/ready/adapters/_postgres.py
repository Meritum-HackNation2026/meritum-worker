"""corpus_ready store: reads ``corpus.documents``, writes ``corpus_ready`` (PostgreSQL).

Never writes ``corpus.*``. The tables come from core's ``corpus/ready/migrations``,
applied by ``prepare`` (core's ``apply_corpus_ready_migrations``).

Features:
    US-KOR-02, F-12
"""

import asyncio
import json
from collections.abc import Sequence
from typing import Final, LiteralString

from meritum_core.corpus.ready import GoldChunk
from meritum_core.corpus.ready.adapters import apply_corpus_ready_migrations
from meritum_core.shared.embeddings import Vector
from psycopg import AsyncConnection
from psycopg.rows import class_row

from meritum_worker.corpus.ready.models import BronzeDocument, BuildReport

_LIVE: Final[LiteralString] = """
SELECT source_id, checksum FROM corpus.documents
WHERE retired_at IS NULL AND full_text IS NOT NULL
"""
"""Live bronze documents with text and their checksums."""
_DOCUMENTS: Final[LiteralString] = """
SELECT source_id, url, domain, checksum, full_text, published_on
FROM corpus.documents
WHERE source_id = ANY(%s) AND retired_at IS NULL AND full_text IS NOT NULL
"""
"""Live bronze documents with full text, by id."""
_INSERT_CHUNK: Final[LiteralString] = """
INSERT INTO corpus_ready.gold_chunks (chunk_id, source_id, checksum,
    start_offset, end_offset, text, header, kind, published_on, valid_from,
    valid_to, eli, subject, topic, numbers, summary, weight, embedding, build_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s::vector, %s)
"""
"""One gold chunk row."""
_UPSERT_SILVER: Final[LiteralString] = """
INSERT INTO corpus_ready.silver_documents
    (source_id, checksum, text, dropped_chars, build_id)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (source_id) DO UPDATE SET checksum = EXCLUDED.checksum,
    text = EXCLUDED.text, dropped_chars = EXCLUDED.dropped_chars,
    build_id = EXCLUDED.build_id, built_at = now()
"""
"""One silver row, replaced on a new checksum."""

_RECORD: Final[LiteralString] = """
INSERT INTO corpus_ready.builds (build_id, finished_at, documents, chunks)
VALUES (%s, now(), %s, %s)
ON CONFLICT (build_id) DO UPDATE SET finished_at = now(),
    documents = EXCLUDED.documents, chunks = EXCLUDED.chunks
"""
"""One build report row."""


class PostgresReadyStore:
    """ReadyStorePort over the shared database (bronze read, corpus_ready write).

    Args:
        conninfo: libpq connection string of the role that owns ``corpus_ready``.

    Features:
        US-KOR-02, F-12
    """

    def __init__(self, conninfo: str) -> None:
        # shortcut: one connection per call; take a pool if the build gets slow.
        self._conninfo = conninfo

    async def prepare(self) -> None:
        """Apply the corpus_ready migrations (see ``ReadyStorePort.prepare``)."""
        await asyncio.to_thread(apply_corpus_ready_migrations, self._conninfo)

    async def live_versions(self) -> dict[str, str]:
        """Live bronze versions (see ``ReadyStorePort.live_versions``).

        Returns:
            ``source_id -> checksum``.
        """
        return await self._pairs(_LIVE)

    async def built_versions(self) -> dict[str, str]:
        """Silver versions (see ``ReadyStorePort.built_versions``).

        Returns:
            ``source_id -> checksum``.
        """
        return await self._pairs(
            "SELECT source_id, checksum FROM corpus_ready.silver_documents"
        )

    async def documents(self, source_ids: Sequence[str]) -> list[BronzeDocument]:
        """Read bronze documents (see ``ReadyStorePort.documents``).

        Args:
            source_ids: The documents to read.

        Returns:
            The live ones with full text.
        """
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.cursor(row_factory=class_row(BronzeDocument)) as cursor,
        ):
            await cursor.execute(_DOCUMENTS, (list(source_ids),))
            return await cursor.fetchall()

    async def replace(
        self,
        doc: BronzeDocument,
        silver: str,
        chunks: Sequence[tuple[GoldChunk, Vector]],
        build_id: str,
    ) -> None:
        """Replace silver and gold of one document (see ``ReadyStorePort.replace``).

        Args:
            doc: The bronze document.
            silver: Its cleaned text.
            chunks: Its gold chunks with embeddings.
            build_id: The running build.
        """
        dropped = len(doc.full_text) - len(silver)
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.transaction(),
        ):
            await conn.execute(
                "DELETE FROM corpus_ready.gold_chunks WHERE source_id = %s",
                (doc.source_id,),
            )
            await conn.execute(
                _UPSERT_SILVER, (doc.source_id, doc.checksum, silver, dropped, build_id)
            )
            async with conn.cursor() as cursor:
                await cursor.executemany(
                    _INSERT_CHUNK, [_row(c, v, build_id) for c, v in chunks]
                )

    async def remove(self, source_ids: Sequence[str]) -> None:
        """Forget documents no longer live (see ``ReadyStorePort.remove``).

        Args:
            source_ids: The documents to forget.
        """
        if not source_ids:
            return
        ids = (list(source_ids),)
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.transaction(),
        ):
            await conn.execute(
                "DELETE FROM corpus_ready.gold_chunks WHERE source_id = ANY(%s)", ids
            )
            await conn.execute(
                "DELETE FROM corpus_ready.silver_documents WHERE source_id = ANY(%s)",
                ids,
            )

    async def record(self, report: BuildReport) -> None:
        """Store the build's report (see ``ReadyStorePort.record``).

        Args:
            report: What the build did.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(
                _RECORD,
                (report.build_id, report.documents, report.chunks),
            )

    async def _pairs(self, sql: LiteralString) -> dict[str, str]:
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(sql)
            return {str(a): str(b) for a, b in await cursor.fetchall()}


def _row(chunk: GoldChunk, vector: Vector, build_id: str) -> tuple[object, ...]:
    numbers = json.dumps([n.model_dump() for n in chunk.numbers], ensure_ascii=False)
    return (
        chunk.chunk_id,
        chunk.source_id,
        chunk.checksum,
        chunk.start_offset,
        chunk.end_offset,
        chunk.text,
        chunk.header,
        chunk.kind.value,
        chunk.published_on,
        chunk.valid_from,
        chunk.valid_to,
        chunk.eli,
        chunk.subject,
        chunk.topic,
        numbers,
        chunk.summary,
        chunk.weight,
        "[" + ",".join(map(str, vector)) + "]",
        build_id,
    )
