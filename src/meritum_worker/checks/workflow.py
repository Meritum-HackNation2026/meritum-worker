"""The `check` workflow body: the 12 AnalysisStep codes in order, each with its steps.

Features:
    US-SPR-01, US-SPR-02, US-OBS-01, F-22, ADR-03
"""

from typing import Any, Protocol

from meritum_core.checks import AnalysisStatus, AnalysisStep
from meritum_core.jobs.contracts import CHECK, CONTRACT_VERSION

from meritum_worker.checks import steps
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.checks.ports import CheckRuntime, StepRun


class Step(Protocol):
    """A step module's function: the state and the ports in, the next state out.

    Features:
        US-SPR-01, F-22
    """

    __name__: str

    async def __call__(self, state: CheckState, deps: CheckDeps, /) -> CheckState:
        """Run the step.

        Args:
            state: the check so far.
            deps: the ports.

        Returns:
            The next state.
        """
        ...


def pipeline() -> tuple[tuple[str, tuple[Step, ...]], ...]:
    """The steps run under each AnalysisStep code, in order.

    Steps outside the 12 codes (image, incidents, sanctions, cases, cost) run
    under the code whose work they extend; their issues only replace modules.

    Returns:
        Pairs of the step code and its step functions.

    Features:
        US-SPR-01, US-SPR-02, F-22
    """
    return (
        ("receive", (steps.receive, steps.read_image)),
        ("fetch_url", (steps.fetch_url,)),
        ("transcribe_audio", (steps.transcribe_audio,)),
        ("screen_injection", (steps.screen_injection,)),
        ("extract_claims", (steps.extract_claims,)),
        ("search_corpus", (steps.search_corpus,)),
        ("search_web", (steps.search_web,)),
        ("search_fact_checks", (steps.search_fact_checks,)),
        ("assess_evidence", (steps.assess_evidence, steps.match_incidents)),
        ("verify_citations", (steps.verify_citations,)),
        ("write_answer", (steps.write_answer, steps.sanctions_warning, steps.cost)),
        ("save_record", (steps.moderator_cases, steps.save_record)),
    )


async def run_check(
    payload: dict[str, Any], check_id: str, deps: CheckDeps, runtime: CheckRuntime
) -> dict[str, Any]:
    """Run every step, publishing an AnalysisStatus before and after each code.

    Args:
        payload: the `CheckInput` JSON object.
        check_id: the check's id (the DBOS workflow id).
        deps: the ports the steps call.
        runtime: runs steps durably and publishes progress.

    Returns:
        The `CheckOutput` JSON object.

    Raises:
        ValueError: the payload has an unsupported contract version.

    Features:
        US-SPR-01, US-SPR-02, US-OBS-01, F-22, ADR-03
    """
    job = CHECK.input.model_validate(payload)
    if job.contract_version != CONTRACT_VERSION:
        msg = f"unsupported contract_version {job.contract_version}"
        raise ValueError(msg)
    state = CheckState(check_id=check_id, job=job)
    codes = [code for code, _ in pipeline()]
    progress = [_step(code, "pending") for code in codes]
    for index, (code, functions) in enumerate(pipeline()):
        progress[index] = _step(code, "active")
        await runtime.publish(AnalysisStatus(check_id=check_id, steps=progress))
        for function in functions:
            state = await runtime.step(function.__name__, _bind(function, deps), state)
        progress[index] = _step(code, "done")
    result = state.final_result()
    await runtime.publish(
        AnalysisStatus(check_id=check_id, steps=progress, result=result)
    )
    return CHECK.output(result=result).model_dump(mode="json")


def _step(code: str, status: str) -> AnalysisStep:
    return AnalysisStep.model_validate({"code": code, "status": status})


def _bind(function: Step, deps: CheckDeps) -> StepRun:
    async def run(state: CheckState) -> CheckState:
        return await function(state, deps)

    return run
