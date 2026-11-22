"""Ports of the notifications slice.

Features:
    US-POW-03, F-39
"""

from typing import Protocol

from meritum_worker.corpus import CorpusSnapshot


class SnapshotReader(Protocol):
    """Reads corpus snapshots taken earlier; the corpus writer satisfies it.

    Features:
        US-POW-03, F-39
    """

    async def snapshot(self, version: str) -> CorpusSnapshot | None:
        """Return a snapshot taken earlier.

        Args:
            version: The snapshot name.

        Returns:
            The snapshot, None when there is none.
        """
        ...
