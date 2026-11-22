"""The `check` workflow body: the 12 AnalysisStep codes in stages, each with its steps.

Features:
    US-SPR-01, US-SPR-02, US-OBS-01, US-BEZ-03, US-SPR-04, US-SPR-06, US-KOR-04,
    F-09, F-13, F-18, F-22, ADR-03, ADR-20
"""

import asyncio
from dataclasses import replace
from typing import Protocol

from meritum_core.checks import AnalysisStatus, AnalysisStep, CheckResult
from meritum_core.jobs.contracts import CHECK, CONTRACT_VERSION, CheckOutput

from meritum_worker import security
from meritum_worker.checks import steps
from meritum_worker.checks.constants import STEP_TIMEOUTS
from meritum_worker.checks.errors import provider_failure
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


type Lane = tuple[str, tuple[Step, ...]]
"""One AnalysisStep code and its step functions, run in order."""


def pipeline() -> tuple[tuple[Lane, ...], ...]:
    """The stages of the check, in order; the lanes of one stage run concurrently.

    Steps outside the 12 codes (image, incidents, sanctions, cases, cost) run
    under the code whose work they extend; their issues only replace modules.
    A lane in a stage with others holds one step, so DBOS starts the
    concurrent steps in a fixed order.

    Returns:
        The stages, each a tuple of lanes.

    Features:
        US-SPR-01, US-SPR-02, US-KOR-04, F-09, F-13, F-22, ADR-20
    """
    return (
        (("receive", (steps.receive, steps.read_image)),),
        (("fetch_url", (steps.fetch_url,)),),
        (("transcribe_audio", (steps.transcribe_audio,)),),
        (("screen_injection", (steps.screen_injection,)),),
        (("extract_claims", (steps.extract_claims, steps.match_incidents)),),
        # The research agents run side by side, never one after another (F-09, F-13).
        (
            ("search_corpus", (steps.search_corpus,)),
            ("search_web", (steps.search_web,)),
            ("search_fact_checks", (steps.search_fact_checks,)),
        ),
        (("assess_evidence", (steps.assess_evidence, steps.search_news)),),
        (("verify_citations", (steps.verify_citations,)),),
        (
            (
                "write_answer",
                (steps.write_answer, steps.sanctions_warning, steps.cost),
            ),
        ),
        (
            (
                "save_record",
                (
                    steps.moderator_cases,
                    steps.notify_new_evidence,
                    steps.notify_done,
                    steps.save_record,
                ),
            ),
        ),
    )


async def run_check(
    payload: dict[str, object], check_id: str, deps: CheckDeps, runtime: CheckRuntime
) -> CheckOutput:
    """Publish progress through the stages and close the stream after the result.

    A stage that raises publishes a technical failure before propagating.

    Args:
        payload: the `CheckInput` JSON object.
        check_id: the check's id (the DBOS workflow id).
        deps: the ports the steps call.
        runtime: runs steps durably and publishes progress.

    Returns:
        The workflow output.

    Raises:
        ValueError: the payload has an unsupported contract version, or two
            parallel steps changed one field (a pipeline bug).

    Features:
        US-SPR-01, US-SPR-02, US-OBS-01, US-KOR-04, US-BEZ-01, F-13, F-19, F-22,
        ADR-03
    """
    job = CHECK.input.model_validate(payload, extra="ignore")
    if job.contract_version != CONTRACT_VERSION:
        msg = f"unsupported contract_version {job.contract_version}"
        raise ValueError(msg)
    # The one path to the model: every prompt passes the detector (US-BEZ-01).
    deps = replace(deps, llm=security.ScreenedLlm(deps.llm, deps.injection))
    state = CheckState(check_id=check_id, job=job)
    stages = pipeline()
    progress = {code: _step(code, "pending") for stage in stages for code, _ in stage}
    for stage in stages:
        progress.update({code: _step(code, "active") for code, _ in stage})
        status = AnalysisStatus(
            check_id=check_id, steps=list(progress.values()), draft=state.draft
        )
        await runtime.publish(status)
        outputs = await asyncio.gather(
            *(_run_lane(lane, state, deps, runtime) for lane in stage),
            return_exceptions=True,
        )
        failures = [o for o in outputs if isinstance(o, BaseException)]
        for (code, _), output in zip(stage, outputs, strict=True):
            progress[code] = _step(code, _lane_outcome(code, state, output))
        if failures:
            failed = state.technical_failure()
            await _finish(runtime, check_id, list(progress.values()), failed)
            raise failures[0]
        state = _merged(state, [o for o in outputs if isinstance(o, CheckState)])
        if status.draft is None and state.draft is not None:
            await runtime.publish(status.model_copy(update={"draft": state.draft}))
    result = state.final_result()
    await _finish(runtime, check_id, list(progress.values()), result)
    return CheckOutput(result=result)


async def _run_lane(
    lane: Lane, state: CheckState, deps: CheckDeps, runtime: CheckRuntime
) -> CheckState:
    code, functions = lane
    for function in functions:
        run = _bind(code, function, deps)
        state = await runtime.step(function.__name__, run, state)
    return state


def _lane_outcome(
    code: str, before: CheckState, output: CheckState | BaseException
) -> str:
    if isinstance(output, BaseException):
        return "failed"
    return _outcome(code, before, output)


def _merged(before: CheckState, outputs: list[CheckState]) -> CheckState:
    # Lanes start from the same state: lists keep every lane's new items, and
    # any other field takes the value of the one lane that changed it.
    if len(outputs) == 1:  # alone in its stage, a lane may also rewrite a list
        return outputs[0]
    merged = before
    for output in outputs:
        update = {
            name: _field(name, before, merged, output)
            for name in CheckState.model_fields
            if getattr(output, name) != getattr(before, name)
        }
        merged = merged.model_copy(update=update)
    return merged


def _field(
    name: str, before: CheckState, merged: CheckState, output: CheckState
) -> object:
    base, ours, theirs = (getattr(s, name) for s in (before, merged, output))
    if isinstance(base, list) and theirs[: len(base)] == base:  # only appended
        return [*ours, *theirs[len(base) :]]
    if ours != base or isinstance(base, list):
        # Two parallel steps changing one field, or rewriting a list, would
        # lose one step's work without a trace.
        msg = f"parallel steps changed {name} in a way that cannot be merged"
        raise ValueError(msg)
    return theirs


async def _finish(
    runtime: CheckRuntime,
    check_id: str,
    progress: list[AnalysisStep],
    result: CheckResult,
) -> None:
    status = AnalysisStatus(check_id=check_id, steps=progress, result=result)
    await runtime.publish(status)
    await runtime.close()


def _step(code: str, status: str) -> AnalysisStep:
    return AnalysisStep.model_validate({"code": code, "status": status})


def _outcome(code: str, before: CheckState, after: CheckState) -> str:
    # The code whose steps turned the check into a technical failure is "failed".
    if _failed(after) and not _failed(before):
        return "failed"
    if code in after.failed_steps:
        return "failed"
    return "skipped" if code in after.skipped_steps else "done"


def _failed(state: CheckState) -> bool:
    return state.result is not None and state.result.status == "technical_failure"


def _bind(code: str, function: Step, deps: CheckDeps) -> StepRun:
    # A provider failure or a timeout becomes a technical_failure state; after
    # it only save_record runs, so nothing answers from the corpus alone.
    async def run(state: CheckState) -> CheckState:
        if _failed(state) and function.__name__ != steps.save_record.__name__:
            return state
        try:
            async with asyncio.timeout(STEP_TIMEOUTS[code].total_seconds()):
                return await function(state, deps)
        except Exception as error:
            failure = provider_failure(code, error)
            if failure is None:
                raise
            update = {
                "result": state.technical_failure(failure.code),
                "retrieval_errors": [*state.retrieval_errors, failure.reason],
            }
            return state.model_copy(update=update)

    return run
