"""The `delete_subject` workflow body: erase one person on request (core/019).

Features:
    US-BEZ-05, F-20, ADR-13
"""

from collections.abc import Mapping

from meritum_core.checks import SubjectKind
from meritum_core.jobs.contracts import (
    CHECK,
    CONTRACT_VERSION,
    DELETE_SUBJECT,
    ESCALATE_CLAIM,
    DeleteSubjectOutput,
)

from meritum_worker.security.models import RetentionDeps, StoredWorkflow
from meritum_worker.security.selection import (
    about_checks,
    audio_id,
    find_workflows,
    names_subject,
)


async def erase_subject(
    payload: Mapping[str, object], deps: RetentionDeps
) -> DeleteSubjectOutput:
    """Delete everything stored about one session, user or channel user.

    The person's check workflows (running ones are cancelled first; DBOS stops
    them at their next step, so a step already saving may still finish, and
    retention takes that record later) and the escalations of their checks
    leave DBOS; then the eraser deletes their records, notifications and case
    checks, and their uploaded audio goes. Running it again deletes nothing more.

    Args:
        payload: the ``DeleteSubjectInput`` JSON object the backend enqueued.
        deps: the ports.

    Returns:
        How many records, notifications, workflows and files were deleted.

    Raises:
        ValueError: the payload has an unsupported contract version.

    Features:
        US-BEZ-05, F-20, ADR-13
    """
    subject = DELETE_SUBJECT.input.model_validate(payload)
    if subject.contract_version != CONTRACT_VERSION:
        msg = f"unsupported contract_version {subject.contract_version}"
        raise ValueError(msg)
    kind, value = subject.kind, subject.value
    records = await deps.app.records.list_for(kind, value)
    checks = await _checks_of(deps, kind, value)
    check_ids = {r.check_id for r in records} | {w.workflow_id for w in checks}
    escalations = await find_workflows(
        deps.workflows, ESCALATE_CLAIM.name, lambda p: about_checks(p, check_ids)
    )
    workflow_ids = [w.workflow_id for w in (*checks, *escalations)]
    await deps.workflows.delete(workflow_ids)
    deleted = len(workflow_ids) + await deps.app.eraser.erase(kind, value)
    # A check stopped before saving its record may still sit in cases or inboxes.
    unsaved = list(check_ids - {r.check_id for r in records})
    if unsaved:
        await deps.app.cases.remove_checks(unsaved)
        deleted += await deps.app.notifications.delete_for_checks(unsaved)
    audio = [found for w in checks if (found := audio_id(w.payload)) is not None]
    deleted += await deps.blobs.delete(audio)
    return DeleteSubjectOutput(deleted=deleted)


async def _checks_of(
    deps: RetentionDeps, kind: SubjectKind, value: str
) -> list[StoredWorkflow]:
    return await find_workflows(
        deps.workflows, CHECK.name, lambda p: names_subject(p, kind, value)
    )
