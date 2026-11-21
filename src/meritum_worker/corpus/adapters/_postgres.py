"""Local copy in the shared ``corpus`` schema; survives worker restarts and deploys.

The tables come from meritum-core's corpus migration ``0002_euvsdisinfo_copy.sql``.

Features:
    US-KOR-08, F-11, ADR-26
"""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime

from meritum_core.checks.contracts import Source
from meritum_core.shared.embeddings import Vector
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from meritum_worker.corpus.models import Entry, StoredEntry

type _Row = tuple[
    dict[str, object], str, str | None, dict[str, object] | None, datetime | None
]


def _vector_text(vector: Vector | None) -> str | None:
    # pgvector's text form is a JSON array.
    return None if vector is None else json.dumps(list(vector))


def _vector(text: str) -> Vector:
    return tuple(float(x) for x in json.loads(text))


def _stored(row: _Row) -> StoredEntry:
    entry, description, fact, source, deleted_at = row
    return StoredEntry(
        entry=Entry.model_validate(entry),
        description_vector=_vector(description),
        fact_vector=None if fact is None else _vector(fact),
        source=None if source is None else Source.model_validate(source),
        deleted_at=deleted_at,
    )


def _params(stored: StoredEntry) -> tuple[object, ...]:
    source = stored.source
    return (
        stored.entry.key,
        stored.entry.kind,
        Jsonb(stored.entry.model_dump(mode="json")),
        _vector_text(stored.description_vector),
        _vector_text(stored.fact_vector),
        None if source is None else Jsonb(source.model_dump(mode="json")),
        stored.deleted_at,
    )


class PostgresEuvsCopy:
    """EuvsCopyPort over ``corpus.euvsdisinfo_entries`` and its flagged domains.

    Args:
        conninfo: libpq connection string of the database with the ``corpus`` schema.

    Features:
        US-KOR-08, F-11, ADR-26
    """

    def __init__(self, conninfo: str) -> None:
        self._conninfo = conninfo

    async def entries(self) -> list[StoredEntry]:
        """Return every stored entry (see ``EuvsCopyPort.entries``).

        Returns:
            The entries, deleted ones included.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(
                "SELECT entry, description_embedding::text, fact_embedding::text,"
                " source, deleted_at FROM corpus.euvsdisinfo_entries"
            )
            return [_stored(row) for row in await cursor.fetchall()]

    async def upsert(self, entries: Sequence[StoredEntry]) -> None:
        """Write entries in one transaction (see ``EuvsCopyPort.upsert``).

        Args:
            entries: Entries to write.
        """
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.cursor() as cursor,
        ):
            await cursor.executemany(
                """
                INSERT INTO corpus.euvsdisinfo_entries (key, kind, entry,
                    description_embedding, fact_embedding, source, deleted_at)
                VALUES (%s, %s, %s, %s::vector, %s::vector, %s, %s)
                ON CONFLICT (key) DO UPDATE SET kind = excluded.kind,
                    entry = excluded.entry,
                    description_embedding = excluded.description_embedding,
                    fact_embedding = excluded.fact_embedding,
                    source = excluded.source, deleted_at = excluded.deleted_at
                """,
                [_params(s) for s in entries],
            )

    async def mark_deleted(self, keys: Sequence[str], at: datetime) -> None:
        """Mark entries deleted (see ``EuvsCopyPort.mark_deleted``).

        Args:
            keys: Entry keys.
            at: When the sync noticed.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            await conn.execute(
                "UPDATE corpus.euvsdisinfo_entries SET deleted_at = %s"
                " WHERE key = ANY(%s)",
                (at, list(keys)),
            )

    async def flagged_domains(self) -> dict[str, tuple[str, ...]]:
        """Return flagged domains (see ``EuvsCopyPort.flagged_domains``).

        Returns:
            Domain to case keys.
        """
        async with await AsyncConnection.connect(self._conninfo) as conn:
            cursor = await conn.execute(
                "SELECT domain, case_keys FROM corpus.euvsdisinfo_flagged_domains"
            )
            return {domain: tuple(keys) for domain, keys in await cursor.fetchall()}

    async def replace_flagged_domains(
        self, domains: Mapping[str, tuple[str, ...]]
    ) -> None:
        """Replace flagged domains in one transaction (see the port).

        Args:
            domains: Domain to case keys.
        """
        async with (
            await AsyncConnection.connect(self._conninfo) as conn,
            conn.cursor() as cursor,
        ):
            await cursor.execute("DELETE FROM corpus.euvsdisinfo_flagged_domains")
            await cursor.executemany(
                "INSERT INTO corpus.euvsdisinfo_flagged_domains (domain, case_keys)"
                " VALUES (%s, %s)",
                [(domain, list(keys)) for domain, keys in domains.items()],
            )
