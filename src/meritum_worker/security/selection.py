"""Which stored workflows belong to a person or to given checks.

Features:
    US-BEZ-05, F-20, ADR-13
"""

from collections.abc import Callable, Collection, Mapping

from meritum_core.checks import SubjectKind

from meritum_worker.security.constants import (
    AUDIO_ID_FIELD,
    CHECK_ID_FIELD,
    OLD_CHECK_ID_FIELD,
    REQUEST_FIELD,
    WORKFLOW_PAGE,
)
from meritum_worker.security.models import StoredWorkflow
from meritum_worker.security.ports import WorkflowStore

type Payload = Mapping[str, object] | None
"""A workflow's first argument as DBOS returns it: a JSON object, or None."""


def names_subject(payload: Payload, kind: SubjectKind, value: str) -> bool:
    """Whether a ``CheckInput`` names the person.

    Args:
        payload: the workflow's input.
        kind: which identifier names the person.
        value: its value.

    Returns:
        True when the input's ``kind`` field equals ``value``.

    Features:
        US-BEZ-05, F-20
    """
    return payload is not None and payload.get(kind) == value


def about_checks(payload: Payload, check_ids: Collection[str]) -> bool:
    """Whether an input such as ``EscalateClaimInput`` is about one of the checks.

    Args:
        payload: the workflow's input.
        check_ids: the checks being deleted.

    Returns:
        True when the input's ``check_id`` is one of them.

    Features:
        US-BEZ-05, F-20
    """
    check_id = None if payload is None else payload.get(CHECK_ID_FIELD)
    return isinstance(check_id, str) and check_id in check_ids


def repeats_checks(payload: Payload, check_ids: Collection[str]) -> bool:
    """Whether a recheck's input names one of the checks, new or earlier.

    Args:
        payload: the workflow's input.
        check_ids: the checks being deleted.

    Returns:
        True when its ``check_id`` or ``old_check_id`` is one of them.

    Features:
        US-BEZ-05, US-POW-03, F-20, F-39
    """
    if payload is None:
        return False
    found = (payload.get(CHECK_ID_FIELD), payload.get(OLD_CHECK_ID_FIELD))
    return any(isinstance(i, str) and i in check_ids for i in found)


def audio_id(payload: Payload) -> str | None:
    """The uploaded audio a ``CheckInput`` points at.

    Args:
        payload: the workflow's input.

    Returns:
        ``request.audio_id``, or None when there is none.

    Features:
        US-BEZ-05, F-20, ADR-31
    """
    request = None if payload is None else payload.get(REQUEST_FIELD)
    found = request.get(AUDIO_ID_FIELD) if isinstance(request, Mapping) else None
    return found if isinstance(found, str) else None


async def find_workflows(
    store: WorkflowStore, name: str, keep: Callable[[Payload], bool]
) -> list[StoredWorkflow]:
    """Read every workflow named ``name`` and keep those whose input matches.

    Args:
        store: the DBOS workflow data.
        name: the workflow name, e.g. ``check``.
        keep: the test on the input.

    Returns:
        The matching workflows, oldest first.

    Features:
        US-BEZ-05, F-20
    """
    found: list[StoredWorkflow] = []
    offset = 0
    while page := await store.with_inputs(name, offset=offset, limit=WORKFLOW_PAGE):
        found += [workflow for workflow in page if keep(workflow.payload)]
        offset += len(page)
    return found
