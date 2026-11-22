"""CheckResults over the `check` and `recheck_claim` workflows DBOS keeps.

Call it only from a DBOS step or outside a workflow, like ``DbosWorkflowStore``.

Features:
    US-MOD-01, US-MOD-02, F-24
"""

from collections.abc import Sequence
from datetime import datetime

from dbos import DBOS, WorkflowStatus
from meritum_core.checks import CheckResult
from meritum_core.jobs.contracts import CheckOutput
from pydantic import ValidationError

from meritum_worker.moderation.constants import (
    CHECK_RESULT_WORKFLOWS,
    HISTORY_LIMIT,
    UNANSWERED_VERDICT,
)
from meritum_worker.moderation.models import PastClaim


def _result(status: WorkflowStatus) -> CheckResult | None:
    try:
        return CheckOutput.model_validate(status.output).result
    except ValidationError:
        return None


class DbosCheckResults:
    """Reads finished checks with ``DBOS.list_workflows_async``.

    A recheck after a new snapshot is a check too: its claims reach the
    moderators and join the unanswered history.

    Features:
        US-MOD-01, US-MOD-02, US-POW-03, F-24, F-39
    """

    async def claim(self, check_id: str, claim_index: int) -> str | None:  # ruff: ignore[no-self-use]  # CheckResults is an instance protocol
        """Read one claim of a finished check.

        Args:
            check_id: the check's workflow id.
            claim_index: the position in its result.

        Returns:
            The claim text, or None.
        """
        found = await DBOS.list_workflows_async(
            workflow_ids=[check_id],
            name=list(CHECK_RESULT_WORKFLOWS),
            load_input=False,
        )
        result = _result(found[0]) if found else None
        if result is None or claim_index >= len(result.claims):
            return None
        return result.claims[claim_index].claim

    async def unanswered_since(self, since: datetime) -> Sequence[PastClaim]:  # ruff: ignore[no-self-use]  # CheckResults is an instance protocol
        """List unanswered claims of the latest HISTORY_LIMIT succeeded checks.

        Args:
            since: the window's start.

        Returns:
            The claims, latest check first.
        """
        found = await DBOS.list_workflows_async(
            name=list(CHECK_RESULT_WORKFLOWS),
            status="SUCCESS",
            start_time=since.isoformat(),
            limit=HISTORY_LIMIT,
            sort_desc=True,
            load_input=False,
        )
        results = [(s.workflow_id, _result(s)) for s in found]
        return [
            PastClaim(check_id, c.claim)
            for check_id, result in results
            if result is not None
            for c in result.claims
            if c.verdict == UNANSWERED_VERDICT
        ]
