"""WorkflowStore over the DBOS system tables of this environment.

Call it only from a DBOS step or outside a workflow: inside a step DBOS does not
record these calls, so the inputs it reads never land in a step's output.

Features:
    US-BEZ-05, F-20, ADR-13
"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from dbos import DBOS, WorkflowStatus

from meritum_worker.security.constants import FINISHED_STATUSES
from meritum_worker.security.models import StoredWorkflow


def _payload(status: WorkflowStatus) -> Mapping[str, object] | None:
    args = () if status.input is None else status.input["args"]
    first = args[0] if args else None
    if not isinstance(first, Mapping):
        return None
    return {str(key): value for key, value in first.items()}


class DbosWorkflowStore:
    """Reads and deletes workflows with ``DBOS.list_workflows`` and its siblings.

    Deleting removes the status row, input, output and step results; events and
    streams go with the status row (cascade).

    Features:
        US-BEZ-05, F-20, ADR-13
    """

    async def with_inputs(  # ruff: ignore[no-self-use]  # WorkflowStore is an instance protocol
        self, name: str, *, offset: int, limit: int
    ) -> list[StoredWorkflow]:
        """Read one page of the workflows named ``name`` with their input.

        Args:
            name: the registered workflow name.
            offset: how many to skip.
            limit: the most to return.

        Returns:
            The page, oldest first.
        """
        found = await DBOS.list_workflows_async(
            name=name, offset=offset, limit=limit, load_input=True, load_output=False
        )
        return [StoredWorkflow(s.workflow_id, _payload(s)) for s in found]

    async def finished(  # ruff: ignore[no-self-use]  # WorkflowStore is an instance protocol
        self,
        *,
        limit: int,
        created_before: datetime | None = None,
        name: str | None = None,
    ) -> list[str]:
        """Select workflows in a final status.

        Args:
            limit: the most ids to return.
            created_before: only workflows started before this time.
            name: only workflows with this name.

        Returns:
            Their ids.
        """
        found = await DBOS.list_workflows_async(
            status=list(FINISHED_STATUSES),
            end_time=None if created_before is None else created_before.isoformat(),
            name=name,
            limit=limit,
            load_input=False,
            load_output=False,
        )
        return [s.workflow_id for s in found]

    async def delete(self, workflow_ids: Sequence[str]) -> None:  # ruff: ignore[no-self-use]  # WorkflowStore is an instance protocol
        """Cancel the active ones, then delete all with their children.

        Args:
            workflow_ids: the workflows to delete.
        """
        ids = list(workflow_ids)
        if ids:
            await DBOS.cancel_workflows_async(ids, cancel_children=True)
            await DBOS.delete_workflows_async(ids, delete_children=True)
