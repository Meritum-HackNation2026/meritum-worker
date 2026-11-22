"""SnapshotCorpusPort over the shared ``corpus`` schema, read only.

The tables come from meritum-core's corpus migrations 0001 and 0003. A
snapshot sees the passages added by and not retired at its ``taken_at``, the
same filter the corpus search applies (ADR-19).

Features:
    US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
"""

from dataclasses import dataclass
from datetime import datetime

from meritum_core.corpus import Passage, UnknownCorpusVersionError
from psycopg import AsyncConnection
from psycopg.rows import class_row

from meritum_worker.observability.snapshot import SnapshotCorpus


@dataclass(frozen=True)
class _Taken:
    taken_at: datetime


@dataclass(frozen=True)
class _Url:
    source_id: str
    url: str


class PostgresSnapshotCorpus:
    """Reads a snapshot's passages and their documents' URLs.

    Args:
        conninfo: libpq connection string of a role that may read ``corpus``.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27, ADR-19
    """

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    async def read(self, version: str) -> SnapshotCorpus:
        """Return the passages ``version`` sees (see ``SnapshotCorpusPort.read``).

        Args:
            version: The ``corpus_version``.

        Returns:
            The snapshot.

        Raises:
            UnknownCorpusVersionError: No snapshot has this version.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            taken = await conn.cursor(row_factory=class_row(_Taken)).execute(
                "SELECT taken_at FROM corpus.snapshots WHERE version = %s", (version,)
            )
            row = await taken.fetchone()
            if row is None:
                raise UnknownCorpusVersionError(version)
            at = {"taken_at": row.taken_at}
            passages = await conn.cursor(row_factory=class_row(Passage)).execute(
                """
                SELECT passage_id, source_id, text, published_on, fetched_at
                FROM corpus.passages
                WHERE added_at <= %(taken_at)s
                  AND (retired_at IS NULL OR retired_at > %(taken_at)s)
                ORDER BY passage_id
                """,
                at,
            )
            found = await passages.fetchall()
            urls = await conn.cursor(row_factory=class_row(_Url)).execute(
                """
                SELECT source_id, url FROM corpus.documents
                WHERE source_id IN (
                    SELECT DISTINCT source_id FROM corpus.passages
                    WHERE added_at <= %(taken_at)s
                      AND (retired_at IS NULL OR retired_at > %(taken_at)s)
                )
                """,
                at,
            )
            documents = await urls.fetchall()
        return SnapshotCorpus(
            version=version,
            taken_at=row.taken_at,
            urls={d.source_id: d.url for d in documents},
            passages=tuple(found),
        )
