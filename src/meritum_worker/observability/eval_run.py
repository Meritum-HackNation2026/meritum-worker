"""The `eval_run` workflow: run the cases, store the EvalRun, tell the staff user.

The workflow body is three functions, so ``main`` runs each as a DBOS step and a
recovered run does not repeat the long one. ``run_eval_run`` calls them in order,
for tests and local runs.

Features:
    US-OBS-06, US-POW-05, F-28, ADR-28, ADR-03
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from meritum_core.checks.contracts import (
    EvalCaseResult,
    EvalMetrics,
    EvalRun,
)
from meritum_core.jobs.contracts import EvalRunInput, EvalRunOutput
from meritum_core.notifications import NotificationRepository

from meritum_worker.checks import save_notification
from meritum_worker.observability.constants import (
    DEFAULT_MAX_CONCURRENCY,
    EVAL_RUN_DONE_KEY,
    EVAL_RUN_LINK,
)
from meritum_worker.observability.ports import EvalCaseSets, EvalRunRepository
from meritum_worker.observability.report import CaseRun, CaseScore, EvalReport
from meritum_worker.observability.runner import DepsFor, run_eval
from meritum_worker.observability.scoring import score_runs


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EvalRunDeps:
    """The ports of the `eval_run` workflow.

    Attributes:
        runs: where the run is stored.
        case_sets: where the golden set and uploaded files come from.
        deps_for: the ports each case's check runs on.
        notifications: the inbox the end of the run is announced in.
        max_concurrency: most cases checked at once.
        clock: the time of ``started_at`` and ``finished_at``.

    Features:
        US-OBS-06, F-28, ADR-28
    """

    runs: EvalRunRepository
    case_sets: EvalCaseSets
    deps_for: DepsFor
    notifications: NotificationRepository
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    clock: Callable[[], datetime] = _now


async def start_eval_run(payload: Mapping[str, object], deps: EvalRunDeps) -> EvalRun:
    """Store the run as running.

    Args:
        payload: the `EvalRunInput` JSON object.
        deps: the ports.

    Returns:
        The stored run, without cases or metrics yet.

    Features:
        US-OBS-06, F-28, ADR-28
    """
    job = EvalRunInput.model_validate(payload)
    run = EvalRun(
        id=job.run_id,
        case_set=job.case_set,
        case_file=job.case_file,
        status="running",
        corpus_version=job.corpus_version,
        user_id=job.user_id,
        started_at=deps.clock(),
    )
    await deps.runs.save(run)
    return run


async def evaluate_eval_run(
    run: EvalRun,
    deps: EvalRunDeps,
    *,
    dataset_blob_id: str | None = None,
) -> EvalRun:
    """Check every case and return the run as done, or failed when it cannot start.

    A case whose check fails stays in the metrics as a technical failure; only a
    case file that is missing or invalid fails the whole run.

    Args:
        run: the running run.
        deps: the ports.
        dataset_blob_id: the blob id from ``EvalRunInput`` for a user file run.

    Returns:
        The finished run; nothing is stored yet.

    Features:
        US-OBS-06, F-28, ADR-28
    """
    try:
        cases = await deps.case_sets.load(
            run.case_set,
            run.case_file,
            dataset_blob_id=dataset_blob_id,
        )
    except LookupError, ValueError, OSError:
        return run.model_copy(update={"status": "failed", "finished_at": deps.clock()})
    runs = await run_eval(cases, deps.deps_for, deps.max_concurrency)
    return _done(run, runs, score_runs(runs), deps.clock())


async def finish_eval_run(run: EvalRun, deps: EvalRunDeps) -> EvalRunOutput:
    """Store the finished run and notify the user who started it.

    The notification id comes from the run id, so a retry replaces it.

    Args:
        run: the done or failed run.
        deps: the ports.

    Returns:
        The run as stored.

    Raises:
        ValueError: the run has no user to notify.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-28
    """
    if run.user_id is None:
        msg = "an eval run notifies the staff user who started it"
        raise ValueError(msg)
    await deps.runs.save(run)
    await save_notification(
        deps.notifications,
        key=EVAL_RUN_DONE_KEY.format(run_id=run.id),
        kind="eval_run_done",
        link=EVAL_RUN_LINK.format(run_id=run.id),
        now=run.finished_at or deps.clock(),
        user_id=run.user_id,
    )
    return EvalRunOutput(run=run)


async def run_eval_run(
    payload: Mapping[str, object], deps: EvalRunDeps
) -> EvalRunOutput:
    """Run the whole workflow in this process, without DBOS steps.

    Args:
        payload: the `EvalRunInput` JSON object.
        deps: the ports.

    Returns:
        The finished or failed run.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-28
    """
    job = EvalRunInput.model_validate(payload)
    running = await start_eval_run(payload, deps)
    done = await evaluate_eval_run(running, deps, dataset_blob_id=job.dataset_blob_id)
    return await finish_eval_run(done, deps)


def _done(
    run: EvalRun, runs: Sequence[CaseRun], report: EvalReport, finished_at: datetime
) -> EvalRun:
    # Validated again: the metrics and cases must satisfy the contract's rules.
    return EvalRun.model_validate(
        run.model_dump()
        | {
            "status": "done",
            "finished_at": max(finished_at, run.started_at),
            "models": report.models,
            "metrics": report.model_dump(include=set(EvalMetrics.model_fields)),
            "scenarios": [s.model_dump() for s in report.scenarios],
            "cases": [
                _case(run.started_at, case, score)
                for case, score in zip(runs, report.outcomes, strict=True)
            ],
        }
    )


def _case(started_at: datetime, run: CaseRun, score: CaseScore) -> EvalCaseResult:
    # The CheckRecord times are not kept per case; the case starts with the run.
    # The contract derives the outcome from expected and predicted, so a hit on
    # an acceptable alternative is stored with that alternative as expected.
    expected = score.predicted if score.outcome == "correct" else score.expected
    return EvalCaseResult.model_validate(
        score.model_dump(include={"scenario", "predicted", "outcome"})
        | {
            "expected": expected,
            "case_id": score.id,
            "check_id": run.result.check_id,
            "received_at": started_at,
            "answered_at": started_at + timedelta(seconds=score.seconds),
            "cost_usd": run.cost_usd,
        }
    )
