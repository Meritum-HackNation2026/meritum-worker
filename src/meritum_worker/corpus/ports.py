"""Ports of the EUvsDisinfo sync: the MCP client and the local copy.

The client port stays in the worker: only the worker calls it (ADR-32).

Features:
    US-KOR-08, F-11, ADR-32
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from meritum_worker.corpus.models import EuvsArticle, EuvsCase, StoredEntry


@runtime_checkable
class EuvsDisinfoPort(Protocol):
    """Paged reads of the EUvsDisinfo database, newest first.

    Features:
        US-KOR-08, F-11, ADR-32
    """

    async def cases(self, *, limit: int, offset: int) -> list[EuvsCase]:
        """Return one page of disinformation cases.

        Args:
            limit: Page size, 1 to 100.
            offset: Cases to skip.

        Returns:
            The page; shorter than ``limit`` on the last page.

        Raises:
            EuvsDisinfoUnavailableError: The server failed or the token is invalid.
        """
        ...

    async def articles(self, *, limit: int, offset: int) -> list[EuvsArticle]:
        """Return one page of analytical articles.

        Args:
            limit: Page size, 1 to 100.
            offset: Articles to skip.

        Returns:
            The page; shorter than ``limit`` on the last page.

        Raises:
            EuvsDisinfoUnavailableError: The server failed or the token is invalid.
        """
        ...


@runtime_checkable
class EuvsCopyPort(Protocol):
    """The local copy of EUvsDisinfo, written only by the sync workflow.

    Features:
        US-KOR-08, F-11
    """

    async def entries(self) -> list[StoredEntry]:
        """Return every stored entry, deleted ones included.

        Returns:
            The entries in no particular order.
        """
        ...

    async def upsert(self, entries: Sequence[StoredEntry]) -> None:
        """Add new entries and replace changed ones, keyed by ``entry.key``.

        Args:
            entries: Entries to write.
        """
        ...

    async def mark_deleted(self, keys: Sequence[str], at: datetime) -> None:
        """Mark entries that vanished from the source; they stay in the copy.

        Args:
            keys: Entry keys.
            at: When the sync noticed.
        """
        ...

    async def replace_flagged_domains(
        self, domains: Mapping[str, tuple[str, ...]]
    ) -> None:
        """Replace the domains the domain warning reads (worker/010).

        Args:
            domains: Domain to the keys of live cases that link to it.
        """
        ...
