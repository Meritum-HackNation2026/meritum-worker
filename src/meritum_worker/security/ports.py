"""Ports of retention: the DBOS workflow data, uploaded files and removed case checks.

Features:
    US-BEZ-05, US-POW-04, F-20, ADR-13
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from meritum_worker.security.models import StoredWorkflow


class WorkflowStore(Protocol):
    """The workflows DBOS keeps with their inputs, outputs and step results (port).

    Features:
        US-BEZ-05, F-20, ADR-13
    """

    async def with_inputs(
        self, name: str, *, offset: int, limit: int
    ) -> list[StoredWorkflow]:
        """Read one page of the workflows named ``name`` with their input, oldest first.

        Args:
            name: the registered workflow name, e.g. ``check``.
            offset: how many workflows to skip.
            limit: the most workflows to return.

        Returns:
            The page; empty past the last workflow.
        """
        ...

    async def finished(
        self,
        *,
        limit: int,
        created_before: datetime | None = None,
        name: str | None = None,
    ) -> list[str]:
        """Select workflows that will not run again.

        Args:
            limit: the most ids to return.
            created_before: only workflows started before this time.
            name: only workflows with this name.

        Returns:
            Their workflow ids.
        """
        ...

    async def delete(self, workflow_ids: Sequence[str]) -> None:
        """Stop the given workflows, then delete them, their children and their data.

        Unknown ids are ignored.

        Args:
            workflow_ids: the workflows to delete.
        """
        ...


class BlobCleaner(Protocol):
    """Deletes uploaded audio and images from the blob store (port, ADR-31).

    Features:
        US-BEZ-05, F-20, ADR-13, ADR-31
    """

    async def delete(self, blob_ids: Sequence[str]) -> int:
        """Delete the given files; missing ones and malformed ids are skipped.

        Args:
            blob_ids: ids as ``CheckRequest.audio_id`` carries them.

        Returns:
            How many ids were valid and deleted.
        """
        ...

    async def delete_older_than(self, cutoff: datetime) -> int:
        """Delete every file stored before ``cutoff``, used by a check or not.

        A store whose provider expires files itself (the GCS bucket rule from
        infra/003) deletes nothing here.

        Args:
            cutoff: files written before it go.

        Returns:
            How many files were deleted.
        """
        ...


class RemovedCaseChecks(Protocol):
    """The ids of checks dropped from moderator cases (port).

    Kept so a stale save cannot bring them back (core#74); no personal data.

    Features:
        US-BEZ-05, F-20, ADR-13
    """

    async def purge(self, before: datetime) -> int:
        """Forget checks removed before ``before``.

        Args:
            before: entries removed earlier go.

        Returns:
            How many entries were deleted.
        """
        ...
