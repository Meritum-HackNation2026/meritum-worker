"""The daily retention run: deletes user data older than 30 days.

Features:
    US-BEZ-05, US-POW-04, F-20, ADR-13
"""

from datetime import datetime

from meritum_core.jobs.contracts import DELETE_SUBJECT, ESCALATE_CLAIM

from meritum_worker.security.constants import (
    DATA_RETENTION,
    ERASURE_RESULT_KEPT,
    RETENTION_BATCH,
)
from meritum_worker.security.models import RetentionDeps, RetentionReport
from meritum_worker.security.ports import WorkflowStore
from meritum_worker.security.selection import about_checks, find_workflows


async def run_retention(deps: RetentionDeps, now: datetime) -> RetentionReport:
    """Delete everything past retention; safe to run again after a failure.

    Check records past ``retention_until`` go with their notifications, their
    place in moderator cases and their DBOS workflows, escalations included.
    Then expired notifications, DBOS workflows started more than 30 days ago,
    finished ``delete_subject`` runs, files older than 30 days (orphan audio
    included) and old ids of checks dropped from cases.

    Args:
        deps: the ports.
        now: the run's time (the schedule's time on DBOS).

    Returns:
        How many items of each kind were deleted.

    Features:
        US-BEZ-05, US-POW-04, F-20, ADR-13
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
    old = await _delete_finished(deps.workflows, created_before=cutoff)
    erasures = await _delete_finished(
        deps.workflows,
        created_before=now - ERASURE_RESULT_KEPT,
        name=DELETE_SUBJECT.name,
    )
    return RetentionReport(
        records=len(expired),
        notifications=await deps.app.notifications.delete_expired(now),
        workflows=len(escalations) + old + erasures,
        blobs=await deps.blobs.delete_older_than(cutoff),
        removed_case_checks=await deps.removed_checks.purge(cutoff),
    )


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


async def _delete_finished(
    store: WorkflowStore, *, created_before: datetime, name: str | None = None
) -> int:
    deleted = 0
    while ids := await store.finished(
        limit=RETENTION_BATCH, created_before=created_before, name=name
    ):
        await store.delete(ids)
        deleted += len(ids)
    return deleted
