"""Models of retention: a stored workflow, the ports a run needs and its report.

Features:
    US-BEZ-05, US-POW-04, F-20, ADR-13
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from meritum_core.observability import AppRepositories
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from meritum_worker.security.ports import (
        BlobCleaner,
        RemovedCaseChecks,
        WorkflowStore,
    )


@dataclass(frozen=True)
class StoredWorkflow:
    """One workflow as DBOS keeps it, with the JSON object it was started with.

    Attributes:
        workflow_id: the DBOS workflow id (the ``check_id`` of a check).
        payload: the workflow's first argument; None when it has no JSON object.

    Features:
        US-BEZ-05, F-20
    """

    workflow_id: str
    payload: Mapping[str, object] | None


@dataclass(frozen=True)
class RetentionDeps:
    """The ports the retention and erasure workflows call.

    Attributes:
        app: the app repositories and the eraser of one person.
        workflows: the DBOS workflow data.
        blobs: the uploaded files.
        removed_checks: the ids of checks dropped from moderator cases.

    Features:
        US-BEZ-05, US-POW-04, F-20, ADR-13
    """

    app: AppRepositories
    workflows: WorkflowStore
    blobs: BlobCleaner
    removed_checks: RemovedCaseChecks


class RetentionReport(BaseModel):
    """What one retention run deleted; counts only, never an identifier.

    Attributes:
        records: expired check records.
        notifications: expired notifications.
        workflows: DBOS workflows found and deleted.
        blobs: uploaded files.
        removed_case_checks: forgotten ids of checks dropped from cases.

    Features:
        US-BEZ-05, US-POW-04, F-20, ADR-13
    """

    model_config = ConfigDict(frozen=True)

    records: Annotated[int, Field(ge=0)]
    notifications: Annotated[int, Field(ge=0)]
    workflows: Annotated[int, Field(ge=0)]
    blobs: Annotated[int, Field(ge=0)]
    removed_case_checks: Annotated[int, Field(ge=0)]
