"""Run every case through the `check` workflow with pydantic-evals (ADR-28).

Features:
    US-OBS-04, US-OBS-05, F-27, ADR-28
"""

import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from meritum_core.checks import SESSIONLESS_CHANNELS, CheckRequest
from meritum_core.jobs.contracts import CheckInput
from pydantic_evals import Case, Dataset

from meritum_worker.checks import CheckDeps, CheckState, InlineCheckRuntime, run_check
from meritum_worker.observability.constants import EVAL_NAME
from meritum_worker.observability.models import GoldenCase, GoldenSet
from meritum_worker.observability.report import CaseRun

type DepsFor = Callable[[GoldenCase], CheckDeps]
"""The ports a case's check runs on (a forced fault swaps one)."""


async def run_eval(
    cases: GoldenSet, deps_for: DepsFor, max_concurrency: int
) -> list[CaseRun]:
    """Check every case; a case whose check raises ends as a technical failure.

    Args:
        cases: The validated case file.
        deps_for: The ports per case.
        max_concurrency: Most cases checked at once.

    Returns:
        One run per case, in file order.

    Features:
        US-OBS-04, US-OBS-05, F-27, ADR-28
    """

    async def task(case: GoldenCase) -> CaseRun:
        return await _check(case, deps_for(case))

    dataset = Dataset[GoldenCase, CaseRun, None](
        name=EVAL_NAME,
        cases=[Case(name=case.id, inputs=case) for case in cases.root],
    )
    report = await dataset.evaluate(
        task, name=EVAL_NAME, max_concurrency=max_concurrency, progress=False
    )
    runs = {run.name: run.output for run in report.cases}
    return [runs[case.id] for case in cases.root]


async def _check(case: GoldenCase, deps: CheckDeps) -> CaseRun:
    check_id = uuid.uuid4().hex
    job = _job(case, datetime.now(UTC))
    try:
        output = await run_check(
            job.model_dump(mode="json"), check_id, deps, InlineCheckRuntime()
        )
        result = output.result
    except Exception:  # ruff: ignore[blind-except]  # the task returns a state, so the case stays in the median
        result = CheckState(check_id=check_id, job=job).technical_failure()
    record = await deps.records.get(check_id)
    answered_at = record.answered_at if record else datetime.now(UTC)
    models = record.models if record else []
    return CaseRun(
        case=case,
        result=result,
        seconds=(answered_at - job.received_at).total_seconds(),
        input_tokens=sum(m.input_tokens for m in models),
        output_tokens=sum(m.output_tokens for m in models),
        cost_usd=sum(m.cost_usd for m in models),
        models=tuple(sorted({f"{m.provider}/{m.model}" for m in models})),
    )


def _job(case: GoldenCase, received_at: datetime) -> CheckInput:
    # Screenshots go without the image: there is no OCR yet (README).
    session = hashlib.sha256((case.session or case.id).encode()).hexdigest()
    sessionless = case.channel in SESSIONLESS_CHANNELS
    return CheckInput(
        request=CheckRequest(channel=case.channel, text=case.text, url=case.url),
        session_id=session,
        channel_user_hash=session if sessionless else None,
        received_at=received_at,
    )
