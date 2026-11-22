"""In-memory archive registry: the fake for tests and runs without a database.

Features:
    US-KOR-07, F-38
"""

from datetime import datetime

from meritum_worker.corpus.archive_models import ArchiveCopy


class MemoryArchiveRegistry:
    """``ArchiveRegistry`` that keeps the copies in process.

    Features:
        US-KOR-07, F-38
    """

    def __init__(self) -> None:
        self._copies: dict[str, ArchiveCopy] = {}

    async def save(self, copy: ArchiveCopy) -> None:
        """Remember a copy (see ``ArchiveRegistry.save``).

        Args:
            copy: the copy.
        """
        self._copies[copy.archive_id] = copy

    async def get(self, archive_id: str) -> ArchiveCopy | None:
        """Return one copy (see ``ArchiveRegistry.get``).

        Args:
            archive_id: the copy's id.

        Returns:
            The copy, or None.
        """
        return self._copies.get(archive_id)

    async def delete(self, archive_id: str) -> None:
        """Forget a copy (see ``ArchiveRegistry.delete``).

        Args:
            archive_id: the copy's id.
        """
        self._copies.pop(archive_id, None)

    async def expired(self, now: datetime, limit: int) -> list[ArchiveCopy]:
        """Select the copies past their term (see ``ArchiveRegistry``).

        Args:
            now: the retention run's time.
            limit: the most copies to return.

        Returns:
            The copies, oldest first.
        """
        found = [c for c in self._copies.values() if c.expires_at <= now]
        return sorted(found, key=lambda c: c.expires_at)[:limit]

    async def owned_by(self, owner_id: str, limit: int) -> list[ArchiveCopy]:
        """Select one person's copies (see ``ArchiveRegistry``).

        Args:
            owner_id: who asked.
            limit: the most copies to return.

        Returns:
            Their copies.
        """
        found = [c for c in self._copies.values() if c.owner_id == owner_id]
        return found[:limit]

    async def count_since(self, owner_id: str, since: datetime) -> int:
        """Count a person's copies in the window (see ``ArchiveRegistry``).

        Args:
            owner_id: who asked.
            since: the start of the window.

        Returns:
            How many copies were made.
        """
        return sum(
            c.owner_id == owner_id and c.archived_at >= since
            for c in self._copies.values()
        )
