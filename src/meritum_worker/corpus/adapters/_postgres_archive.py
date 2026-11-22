"""ArchiveRegistry over the ``page_archives`` table (core migration 0008).

Features:
    US-KOR-07, F-38, ADR-04
"""

from datetime import datetime

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from meritum_worker.corpus.archive_constants import (
    COUNT_ARCHIVES_SQL,
    DELETE_ARCHIVE_SQL,
    INSERT_ARCHIVE_SQL,
    SELECT_ARCHIVE_SQL,
)
from meritum_worker.corpus.archive_models import ArchiveCopy


class PostgresArchiveRegistry:
    """``ArchiveRegistry`` in the app schema the backend reads too.

    Args:
        conninfo: libpq connection string of the app database.

    Features:
        US-KOR-07, F-38, ADR-04
    """

    def __init__(self, conninfo: str) -> None:
        # shortcut: one connection per call; take a pool if archiving gets busy.
        self._conninfo = conninfo

    async def save(self, copy: ArchiveCopy) -> None:
        """Remember a copy (see ``ArchiveRegistry.save``).

        Args:
            copy: the copy.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(
                INSERT_ARCHIVE_SQL,
                (
                    copy.archive_id,
                    copy.blob_id,
                    copy.url,
                    copy.owner_id,
                    copy.sha256,
                    copy.archived_at,
                    copy.expires_at,
                    copy.legal_basis,
                    copy.access_rule,
                    copy.deletion_procedure,
                ),
            )

    async def get(self, archive_id: str) -> ArchiveCopy | None:
        """Return one copy (see ``ArchiveRegistry.get``).

        Args:
            archive_id: the copy's id.

        Returns:
            The copy, or None.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = conn.cursor(row_factory=dict_row)
            await cursor.execute(SELECT_ARCHIVE_SQL, (archive_id,))
            row = await cursor.fetchone()
        return None if row is None else ArchiveCopy.model_validate(row)

    async def delete(self, archive_id: str) -> None:
        """Forget a copy (see ``ArchiveRegistry.delete``).

        Args:
            archive_id: the copy's id.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(DELETE_ARCHIVE_SQL, (archive_id,))

    async def count_since(self, owner_id: str, since: datetime) -> int:
        """Count a person's copies in the window (see ``ArchiveRegistry``).

        Args:
            owner_id: who asked.
            since: the start of the window.

        Returns:
            How many copies were made.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(COUNT_ARCHIVES_SQL, (owner_id, since))
            row = await cursor.fetchone()
        return 0 if row is None else int(row[0])
