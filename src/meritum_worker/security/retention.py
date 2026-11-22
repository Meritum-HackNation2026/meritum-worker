"""The retention run, started hourly: deletes user data older than 30 days.

It also clears corpus full texts 90 days after their fetch.

Features:
    US-BEZ-05, US-POW-04, US-KOR-05, F-10, F-20, ADR-13
"""

from datetime import datetime

from meritum_core.jobs.contracts import DELETE_SUBJECT, ESCALATE_CLAIM

from meritum_worker.security.constants import (
    DATA_RETENTION,
    ERASURE_RESULT_KEPT,
    FULL_TEXT_RETENTION,
    RETENTION_BATCH,
)
from meritum_worker.security.models import RetentionDeps, RetentionReport
from meritum_worker.security.ports import WorkflowStore
from meritum_worker.security.selection import about_checks, find_workflows


async def run_retention(deps: RetentionDeps, now: datetime) -> RetentionReport:
    """Delete everything past retention; safe to run again after a failure.

    Check records past ``retention_until`` go with their notifications, their
    place in moderator cases and their DBOS workflows, escalations included.
    Then expired notifications, DBOS workflows started more than 30 days ago
    (stuck ones too), finished ``delete_subject`` runs, files older than 30
    days (orphan audio included) and old ids of checks dropped from cases.
    Last, corpus documents fetched more than 90 days ago lose their full text;
    their metadata and the passages records cite stay.

    Args:
        deps: the ports.
        now: the run's time (the schedule's time on DBOS).

    Returns:
        How many items of each kind were deleted.

    Features:
        US-BEZ-05, US-POW-04, US-KOR-05, F-10, F-20, ADR-13
    """
    cutoff = now - DATA_RETENTION
    expired = await _delete_expired_records(deps, now)
    escalations = (
        await find_workflows(
            deps.workflows, ESCALATE_CLAIM.name, lambda p: about_checks(p, expired)
        )
        if expired
        else []
    )
    await deps.workflows.delete([w.workflow_id for w in escalations])
    old = await _delete_older(deps.workflows, created_before=cutoff)
    erasures = await _delete_older(
        deps.workflows,
        created_before=now - ERASURE_RESULT_KEPT,
        name=DELETE_SUBJECT.name,
        finished_only=True,
    )
    return RetentionReport(
        records=len(expired),
        notifications=await deps.app.notifications.delete_expired(now),
        workflows=len(escalations) + old + erasures,
        blobs=await deps.blobs.delete_older_than(cutoff),
        removed_case_checks=await deps.removed_checks.purge(cutoff),
        full_texts=await _clear_full_texts(deps, now - FULL_TEXT_RETENTION),
    )


async def _clear_full_texts(deps: RetentionDeps, fetched_before: datetime) -> int:
    cleared = 0
    while count := await deps.corpus.clear_full_texts(
        fetched_before=fetched_before, limit=RETENTION_BATCH
    ):
        cleared += count
    return cleared


async def _delete_expired_records(deps: RetentionDeps, now: datetime) -> set[str]:
    app, deleted = deps.app, set[str]()
    while check_ids := await app.records.expired(now, limit=RETENTION_BATCH):
        # The record goes last, so a failed round is selected again next run.
        await app.cases.remove_checks(check_ids)
        await app.notifications.delete_for_checks(check_ids)
        await deps.workflows.delete(check_ids)
        await app.records.delete(check_ids)
        deleted.update(check_ids)
    return deleted


async def _delete_older(
    store: WorkflowStore,
    *,
    created_before: datetime,
    name: str | None = None,
    finished_only: bool = False,
) -> int:
    deleted = 0
    while ids := await store.older(
        limit=RETENTION_BATCH,
        created_before=created_before,
        name=name,
        finished_only=finished_only,
    ):
        await store.delete(ids)
        deleted += len(ids)
    return deleted
