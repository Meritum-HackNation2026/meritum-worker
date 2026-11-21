"""In-memory local copy: the fake for tests and runs without a database.

Features:
    US-KOR-08, F-11
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from meritum_worker.corpus.models import StoredEntry


class MemoryEuvsCopy:
    """Entries and flagged domains held in process.

    Features:
        US-KOR-08, F-11
    """

    def __init__(self) -> None:
        self._entries: dict[str, StoredEntry] = {}
        self.flagged_domains: dict[str, tuple[str, ...]] = {}

    async def entries(self) -> list[StoredEntry]:
        """Return every stored entry (see ``EuvsCopyPort.entries``).

        Returns:
            The entries.
        """
        return list(self._entries.values())

    async def upsert(self, entries: Sequence[StoredEntry]) -> None:
        """Write entries (see ``EuvsCopyPort.upsert``).

        Args:
            entries: Entries to write.
        """
        self._entries.update((stored.entry.key, stored) for stored in entries)

    async def mark_deleted(self, keys: Sequence[str], at: datetime) -> None:
        """Mark entries deleted (see ``EuvsCopyPort.mark_deleted``).

        Args:
            keys: Entry keys.
            at: When the sync noticed.
        """
        for key in keys:
            self._entries[key] = self._entries[key].model_copy(
                update={"deleted_at": at}
            )

    async def replace_flagged_domains(
        self, domains: Mapping[str, tuple[str, ...]]
    ) -> None:
        """Replace flagged domains (see ``EuvsCopyPort.replace_flagged_domains``).

        Args:
            domains: Domain to case keys.
        """
        self.flagged_domains = dict(domains)
