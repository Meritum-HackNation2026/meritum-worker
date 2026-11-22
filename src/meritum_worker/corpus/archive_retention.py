"""Deleting page copies: past their term, and everything one person asked for.

Features:
    US-KOR-07, US-BEZ-05, F-38, F-20
"""

from datetime import datetime

from meritum_worker.corpus.archive_constants import ARCHIVE_PURGE_BATCH
from meritum_worker.corpus.archive_models import ArchiveCopy
from meritum_worker.corpus.archive_ports import ArchiveDeps


async def _purge(deps: ArchiveDeps, copies: list[ArchiveCopy]) -> None:
    for copy in copies:
        # The row goes last, so a failed round selects the copy again next run.
        await deps.blobs.delete(copy.blob_id)
        await deps.registry.delete(copy.archive_id)


async def purge_expired_archives(deps: ArchiveDeps, now: datetime) -> int:
    """Delete the copies past their ``expires_at``: the file, then the row.

    Safe to run again after a failure.

    Args:
        deps: the blob store and registry.
        now: the retention run's time.

    Returns:
        How many copies were deleted.

    Features:
        US-KOR-07, F-38
    """
    deleted = 0
    while copies := await deps.registry.expired(now, ARCHIVE_PURGE_BATCH):
        await _purge(deps, copies)
        deleted += len(copies)
    return deleted


async def purge_archives_of(deps: ArchiveDeps, owner_id: str) -> int:
    """Delete every copy one session or user asked for, whatever its age.

    Args:
        deps: the blob store and registry.
        owner_id: the ``owner_id`` the copies were archived under.

    Returns:
        How many copies were deleted.

    Features:
        US-KOR-07, US-BEZ-05, F-38, F-20
    """
    deleted = 0
    while copies := await deps.registry.owned_by(owner_id, ARCHIVE_PURGE_BATCH):
        await _purge(deps, copies)
        deleted += len(copies)
    return deleted
