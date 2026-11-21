"""CheckRuntime on DBOS: each step is a checkpointed DBOS step.

Features:
    US-SPR-01, US-SPR-02, F-22, ADR-03
"""

from dbos import DBOS, WorkflowSerializationFormat
from meritum_core.checks import AnalysisStatus
from meritum_core.jobs.constants import PROGRESS_KEY

from meritum_worker.checks.models import CheckState
from meritum_worker.checks.ports import StepRun


class DbosCheckRuntime:
    """Runs steps with ``DBOS.run_step_async`` and writes the progress stream.

    Call it only inside a DBOS workflow.

    Features:
        US-SPR-01, US-SPR-02, F-22, ADR-03
    """

    async def step(  # ruff: ignore[no-self-use]  # CheckRuntime is an instance protocol
        self, name: str, run: StepRun, state: CheckState
    ) -> CheckState:
        """Run ``run`` as a DBOS step; the checkpoint is the state as JSON.

        Args:
            name: the step's name in the workflow history.
            run: the step.
            state: its input.

        Returns:
            The step's output; on recovery the checkpointed one.
        """

        async def checkpointed(data: str) -> str:
            output = await run(CheckState.model_validate_json(data))
            return output.model_dump_json()

        output = await DBOS.run_step_async(
            {"name": name}, checkpointed, state.model_dump_json()
        )
        return CheckState.model_validate_json(output)

    async def publish(  # ruff: ignore[no-self-use]  # CheckRuntime is an instance protocol
        self, status: AnalysisStatus
    ) -> None:
        """Write ``status`` to the PROGRESS_KEY stream as portable JSON.

        Args:
            status: the progress to publish.
        """
        await DBOS.write_stream_async(
            PROGRESS_KEY,
            status.model_dump(mode="json"),
            serialization_type=WorkflowSerializationFormat.PORTABLE,
        )
