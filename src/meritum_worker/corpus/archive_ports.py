"""Ports of the page archive: the registry of copies and the ports a request uses.

Features:
    US-KOR-07, F-38
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.shared.blobs import BlobStore

from meritum_worker.corpus.archive_models import ArchiveCopy


class ArchiveRegistry(Protocol):
    """Metadata of the stored copies; the text itself is in the ``BlobStore``.

    Features:
        US-KOR-07, F-38
    """

    async def save(self, copy: ArchiveCopy) -> None:
        """Remember a copy.

        Args:
            copy: the copy to remember.
        """
        ...

    async def get(self, archive_id: str) -> ArchiveCopy | None:
        """Return one copy.

        Args:
            archive_id: the copy's id.

        Returns:
            The copy, or None when there is none.
        """
        ...

    async def delete(self, archive_id: str) -> None:
        """Forget a copy; a missing one is ignored.

        Args:
            archive_id: the copy's id.
        """
        ...

    async def count_since(self, owner_id: str, since: datetime) -> int:
        """Count the copies one person made since ``since``.

        Args:
            owner_id: who asked.
            since: the start of the window.

        Returns:
            How many copies were made.
        """
        ...


@dataclass(frozen=True)
class ArchiveDeps:
    """Ports of the archiving workflow.

    Attributes:
        pages: core's SSRF-safe fetcher, the only way a URL is read.
        blobs: where the copies' text is stored.
        registry: the copies' metadata.

    Features:
        US-KOR-07, F-38
    """

    pages: PageFetcherPort
    blobs: BlobStore
    registry: ArchiveRegistry
