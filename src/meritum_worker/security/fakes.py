"""In-memory WorkflowStore for tests and behave: no DBOS.

Features:
    US-BEZ-05, F-20
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from meritum_worker.security.models import StoredWorkflow


@dataclass(frozen=True)
class _Run:
    name: str
    payload: Mapping[str, object] | None
    created_at: datetime
    done: bool


class InMemoryWorkflowStore:
    """WorkflowStore fake that keeps workflows in a dict; they have no children.

    Features:
        US-BEZ-05, F-20
    """

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}

    def add(
        self,
        workflow_id: str,
        name: str,
        payload: Mapping[str, object] | None,
        *,
        created_at: datetime,
        done: bool = True,
    ) -> None:
        """Store a workflow as if DBOS had run it.

        Args:
            workflow_id: its id.
            name: its registered name.
            payload: its first argument.
            created_at: when it started.
            done: whether it reached a final status.
        """
        self._runs[workflow_id] = _Run(name, payload, created_at, done)

    def ids(self) -> set[str]:
        """The ids of the stored workflows.

        Returns:
            The ids.
        """
        return set(self._runs)

    def payloads(self) -> list[Mapping[str, object] | None]:
        """The inputs of the stored workflows.

        Returns:
            One per workflow.
        """
        return [run.payload for run in self._runs.values()]

    async def with_inputs(
        self, name: str, *, offset: int, limit: int
    ) -> list[StoredWorkflow]:
        """Read one page of the workflows named ``name``, oldest first.

        Args:
            name: the workflow name.
            offset: how many to skip.
            limit: the most to return.

        Returns:
            The page.
        """
        named = sorted(
            (run.created_at, workflow_id, run.payload)
            for workflow_id, run in self._runs.items()
            if run.name == name
        )
        page = named[offset : offset + limit]
        return [
            StoredWorkflow(workflow_id, payload) for _, workflow_id, payload in page
        ]

    async def finished(
        self,
        *,
        limit: int,
        created_before: datetime | None = None,
        name: str | None = None,
    ) -> list[str]:
        """Select finished workflows.

        Args:
            limit: the most ids to return.
            created_before: only workflows started before this time.
            name: only workflows with this name.

        Returns:
            Their ids.
        """

        def selected(run: _Run) -> bool:
            is_old = created_before is None or run.created_at <= created_before
            return run.done and is_old and name in {None, run.name}

        return [i for i, run in self._runs.items() if selected(run)][:limit]

    async def delete(self, workflow_ids: Sequence[str]) -> None:
        """Drop the given workflows.

        Args:
            workflow_ids: the workflows to drop.
        """
        for workflow_id in workflow_ids:
            self._runs.pop(workflow_id, None)
