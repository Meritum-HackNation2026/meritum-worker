"""BlobCleaner over core's BlobStore, plus a sweep of the files volume by age.

Features:
    US-BEZ-05, F-20, ADR-13, ADR-31
"""

import asyncio
import os
import re
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from meritum_core.shared.blobs import BLOB_ID_PATTERN, BlobNotFoundError, BlobStore


def _is_blob(name: str) -> bool:
    # A finished file is named by its id; one still being written ends in ".part".
    return re.fullmatch(BLOB_ID_PATTERN, name.removesuffix(".part")) is not None


def _sweep(directory: Path, cutoff: datetime) -> int:
    deleted = 0
    with os.scandir(directory) as entries:
        for entry in entries:
            is_file = entry.is_file(follow_symlinks=False) and _is_blob(entry.name)
            stored = entry.stat(follow_symlinks=False).st_mtime if is_file else None
            if stored is not None and stored < cutoff.timestamp():
                Path(entry.path).unlink(missing_ok=True)
                deleted += 1
    return deleted


class StoreBlobCleaner:
    """Deletes files through the BlobStore; sweeps the filesystem store's directory.

    Args:
        store: the configured blob store.
        directory: the filesystem store's directory; None for stores that expire
            files themselves (the GCS bucket rule) or keep them in memory.

    Features:
        US-BEZ-05, F-20, ADR-13, ADR-31
    """

    def __init__(self, store: BlobStore, directory: Path | None) -> None:
        self._store = store
        self._directory = directory

    async def delete(self, blob_ids: Sequence[str]) -> int:
        """Delete the given files, skipping malformed ids.

        Args:
            blob_ids: the ids to delete.

        Returns:
            How many well-formed ids were deleted or already gone.
        """
        deleted = 0
        for blob_id in blob_ids:
            try:
                await self._store.delete(blob_id)
            except BlobNotFoundError:
                continue
            deleted += 1
        return deleted

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete files last written before ``cutoff`` from the directory.

        Args:
            cutoff: older files go.

        Returns:
            How many files were deleted; 0 without a directory.
        """
        if self._directory is None:
            return 0
        return await asyncio.to_thread(_sweep, self._directory, cutoff)


class NullBlobCleaner:
    """BlobCleaner for a worker without ``MERITUM_BLOB_PROVIDER``: nothing to delete.

    Features:
        US-BEZ-05, F-20
    """

    async def delete(self, blob_ids: Sequence[str]) -> int:  # ruff: ignore[no-self-use]  # BlobCleaner is an instance protocol
        """Delete nothing.

        Args:
            blob_ids: ignored.

        Returns:
            0.
        """
        del blob_ids
        return 0

    async def delete_older_than(self, cutoff: datetime) -> int:  # ruff: ignore[no-self-use]  # BlobCleaner is an instance protocol
        """Delete nothing.

        Args:
            cutoff: ignored.

        Returns:
            0.
        """
        del cutoff
        return 0
