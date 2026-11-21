import asyncio
from collections.abc import Callable
from typing import Any, get_args

import pytest
from meritum_core.checks import AnalysisStep, CheckResult
from meritum_core.jobs.contracts import CONTRACT_VERSION, CheckInput

from meritum_worker.checks import CheckDeps, pipeline, run_check
from meritum_worker.checks.fakes import InlineCheckRuntime

STEP_CODES = list(get_args(AnalysisStep.model_fields["code"].annotation))

type Payload = dict[str, Any]


@pytest.fixture
def payload(make_job: Callable[..., CheckInput]) -> Payload:
    return make_job().model_dump(mode="json")


def _run(payload: Payload, deps: CheckDeps) -> tuple[Payload, InlineCheckRuntime]:
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
        assert [step.status for step in status.steps] == expected
        assert status.result is None
    final = statuses[-1]
    assert {step.status for step in final.steps} == {"done"}
    assert final.result == CheckResult.model_validate(output["result"])


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
