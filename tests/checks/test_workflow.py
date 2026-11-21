import asyncio
from collections.abc import Callable
from typing import Any, get_args

import pytest
from meritum_core.checks import AnalysisStep
from meritum_core.jobs.contracts import CONTRACT_VERSION, CheckInput, CheckOutput

from meritum_worker.checks import (
    CheckDeps,
    FailingCheckRuntime,
    InlineCheckRuntime,
    pipeline,
    run_check,
)
from meritum_worker.checks.constants import TECHNICAL_FAILURE_CODE

STEP_CODES = list(get_args(AnalysisStep.model_fields["code"].annotation))

type Payload = dict[str, Any]


@pytest.fixture
def payload(make_job: Callable[..., CheckInput]) -> Payload:
    return make_job().model_dump(mode="json")


def _run(payload: Payload, deps: CheckDeps) -> tuple[CheckOutput, InlineCheckRuntime]:
    runtime = InlineCheckRuntime()
    return asyncio.run(run_check(payload, "check-1", deps, runtime)), runtime


def test_pipeline_covers_every_analysis_step_in_contract_order() -> None:
    assert [code for code, _ in pipeline()] == STEP_CODES


def test_check_publishes_each_step_active_then_done_and_ends_with_result(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    output, runtime = _run(payload, make_deps())
    statuses = runtime.published
    assert len(statuses) == len(STEP_CODES) + 1
    for index, status in enumerate(statuses[:-1]):
        pending = len(STEP_CODES) - index - 1
        expected = ["done"] * index + ["active"] + ["pending"] * pending
        if index > 1:  # a text has no link: fetch_url, the second code, is skipped
            expected[1] = "skipped"
        assert [step.status for step in status.steps] == expected
        assert status.result is None
    final = statuses[-1]
    assert {step.status for step in final.steps} == {"done", "skipped"}
    assert final.result == output.result


def test_check_runs_placeholder_steps_outside_the_analysis_codes(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    _, runtime = _run(payload, make_deps())
    names = runtime.step_names
    for extra in ("read_image", "match_incidents", "sanctions_warning", "cost"):
        assert extra in names
    assert names.index("moderator_cases") < names.index("save_record")
    assert (names[0], names[-1]) == ("receive", "save_record")


def test_check_rejects_other_contract_version(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    payload["contract_version"] = CONTRACT_VERSION + 1
    with pytest.raises(ValueError, match="contract_version"):
        _run(payload, make_deps())


def test_check_marks_the_step_that_failed_technically_as_failed(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    _, runtime = _run(payload, make_deps("llm_stub_broken_answer.json"))
    final = runtime.published[-1]
    failed = [step.code for step in final.steps if step.status == "failed"]
    assert failed == ["write_answer"]
    assert final.result is not None
    assert final.result.status == "technical_failure"


def test_check_closes_progress_stream_after_the_status_with_the_result(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    output, runtime = _run(payload, make_deps())
    assert runtime.closed_after == len(runtime.published)
    assert runtime.published[-1].result == output.result


def test_check_publishes_technical_failure_before_closing_after_step_exception(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    runtime = FailingCheckRuntime("search_web")

    with pytest.raises(RuntimeError, match="step failed"):
        asyncio.run(run_check(payload, "check-1", make_deps(), runtime))

    final = runtime.published[-1]
    failed = [step.code for step in final.steps if step.status == "failed"]
    assert failed == ["search_web"]
    assert final.result is not None
    assert final.result.status == "technical_failure"
    assert final.result.failure_code == TECHNICAL_FAILURE_CODE
    assert runtime.closed_after == len(runtime.published)
