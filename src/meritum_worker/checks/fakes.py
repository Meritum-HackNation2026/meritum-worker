"""In-process CheckRuntime for tests and behave: no DBOS, no database.

Features:
    US-SPR-01, F-22
"""

from meritum_core.checks import AnalysisStatus

from meritum_worker.checks.models import CheckState
from meritum_worker.checks.ports import StepRun


class InlineCheckRuntime:
    """Runs each step at once and keeps every published status.

    State and statuses go through JSON, as DBOS keeps them, so a model that does
    not survive the round trip fails here too.

    Attributes:
        published: every AnalysisStatus, in order.
        step_names: the name of every step run, in order.

    Features:
        US-SPR-01, US-SPR-02, F-22
    """

    def __init__(self) -> None:
        self.published: list[AnalysisStatus] = []
        self.step_names: list[str] = []

    async def step(self, name: str, run: StepRun, state: CheckState) -> CheckState:
        """Run the step on a JSON copy of the state.

        Args:
            name: the step's name.
            run: the step.
            state: its input.

        Returns:
            A JSON copy of the step's output.
        """
        self.step_names.append(name)
        output = await run(CheckState.model_validate_json(state.model_dump_json()))
        return CheckState.model_validate_json(output.model_dump_json())

    async def publish(self, status: AnalysisStatus) -> None:
        """Keep a JSON copy of ``status``.

        Args:
            status: the progress to publish.
        """
        self.published.append(
            AnalysisStatus.model_validate_json(status.model_dump_json())
        )
