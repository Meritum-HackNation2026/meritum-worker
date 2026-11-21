"""Port of the `check` workflow runtime: durable steps and the progress stream.

Features:
    US-SPR-01, US-SPR-02, F-22, ADR-03
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from meritum_core.checks import AnalysisStatus

from meritum_worker.checks.models import CheckState

type StepRun = Callable[[CheckState], Awaitable[CheckState]]
"""One bound step: takes the state, returns the next one."""


class CheckRuntime(Protocol):
    """Runs workflow steps durably and publishes progress (DBOS in production).

    Features:
        US-SPR-01, US-SPR-02, F-22, ADR-03
    """

    async def step(self, name: str, run: StepRun, state: CheckState) -> CheckState:
        """Run one step and checkpoint its output.

        Args:
            name: the step's name in the workflow history.
            run: the step.
            state: its input.

        Returns:
            The step's output; a replayed step returns the checkpoint.
        """
        ...

    async def publish(self, status: AnalysisStatus) -> None:
        """Append ``status`` to the workflow's progress stream (PROGRESS_KEY).

        Args:
            status: the steps so far, and the result once the check finished.
        """
        ...
