"""The ``archive_page`` workflow body, without DBOS.

Features:
    US-KOR-07, F-38, ADR-03
"""

from datetime import datetime
from typing import Any

from meritum_core.jobs.contracts import ARCHIVE_PAGE

from meritum_worker.corpus.archive import archive_page
from meritum_worker.corpus.archive_models import ArchiveRequest
from meritum_worker.corpus.archive_ports import ArchiveDeps


async def run_archive_page(
    payload: dict[str, Any], deps: ArchiveDeps, *, now: datetime
) -> dict[str, Any]:
    """Archive the page of one ``archive_page`` job.

    Args:
        payload: the ``ArchivePageInput`` JSON object.
        deps: the fetcher, blob store and registry.
        now: the archiving time.

    Returns:
        The ``ArchivePageOutput`` JSON object: the copy or the refusal.

    Features:
        US-KOR-07, F-38, ADR-03
    """
    job = ARCHIVE_PAGE.input.model_validate(payload)
    request = ArchiveRequest(
        url=job.url, owner_id=job.owner_id, archive_id=job.archive_id
    )
    outcome = await archive_page(request, deps, now=now)
    copy = outcome.archive
    output = ARCHIVE_PAGE.output(
        archive_id=job.archive_id,
        owner_id=job.owner_id,
        url=None if copy is None else copy.url,
        sha256=None if copy is None else copy.sha256,
        archived_at=None if copy is None else copy.archived_at,
        expires_at=None if copy is None else copy.expires_at,
        refusal=None if outcome.refusal is None else outcome.refusal.value,
        message=outcome.message,
    )
    return output.model_dump(mode="json", exclude_none=True)
