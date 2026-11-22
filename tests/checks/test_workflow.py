import asyncio
import dataclasses
from collections.abc import Callable
from typing import Any, get_args

import pytest
from meritum_core.checks import AnalysisStep
from meritum_core.jobs.contracts import CONTRACT_VERSION, CheckInput, CheckOutput

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    FailingCheckRuntime,
    InlineCheckRuntime,
    pipeline,
    run_check,
    steps,
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
    assert [code for stage in pipeline() for code, _ in stage] == STEP_CODES


def test_research_agents_share_one_stage_one_step_each() -> None:
    (stage,) = [s for s in pipeline() if len(s) > 1]
    research = ["search_corpus", "search_web", "search_fact_checks"]
    assert [code for code, _ in stage] == research
    assert all(len(functions) == 1 for _, functions in stage)


def test_check_publishes_each_step_active_then_done_and_ends_with_result(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    output, runtime = _run(payload, make_deps())
    # The draft adds an update between the start of writing and the next stage.
    statuses = [runtime.published[0]]
    for status in runtime.published[1:]:
        if status.steps != statuses[-1].steps:
            statuses.append(status)
    stages = [[code for code, _ in stage] for stage in pipeline()]
    assert len(statuses) == len(stages) + 1
    for index, status in enumerate(statuses[:-1]):
        before = [code for stage in stages[:index] for code in stage]
        active = stages[index]
        # A text has no link and no audio, and no corpus snapshot is pinned.
        skipped = {"fetch_url", "transcribe_audio", "search_corpus"}
        expected = [
            ("skipped" if code in skipped else "done")
            if code in before
            else "active"
            if code in active
            else "pending"
            for code in STEP_CODES
        ]
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
    assert all(status.draft is None for status in runtime.published)


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


def test_corpus_and_web_search_run_at_the_same_time(
    monkeypatch: pytest.MonkeyPatch,
    payload: Payload,
    make_deps: Callable[..., CheckDeps],
) -> None:
    web_started = asyncio.Event()

    async def search_corpus(state: CheckState, _deps: CheckDeps) -> CheckState:
        # Run one after the other, corpus search would wait for web search forever.
        await asyncio.wait_for(web_started.wait(), timeout=1)
        return state

    async def search_web(state: CheckState, _deps: CheckDeps) -> CheckState:
        web_started.set()
        await asyncio.sleep(0)
        return state

    monkeypatch.setattr(steps, "search_web", search_web)
    monkeypatch.setattr(steps, "search_corpus", search_corpus)
    output, _ = _run(payload, make_deps())
    assert output.result.status == "done"


def test_parallel_steps_that_change_the_same_field_fail_loudly(
    monkeypatch: pytest.MonkeyPatch,
    payload: Payload,
    make_deps: Callable[..., CheckDeps],
) -> None:
    async def corpus_snapshot(state: CheckState, _deps: CheckDeps) -> CheckState:
        await asyncio.sleep(0)
        return state.model_copy(update={"corpus_version": "corpus-a"})

    async def other_snapshot(state: CheckState, _deps: CheckDeps) -> CheckState:
        await asyncio.sleep(0)
        return state.model_copy(update={"corpus_version": "corpus-b"})

    corpus_snapshot.__name__ = "search_corpus"
    other_snapshot.__name__ = "search_web"
    monkeypatch.setattr(steps, "search_corpus", corpus_snapshot)
    monkeypatch.setattr(steps, "search_web", other_snapshot)
    with pytest.raises(ValueError, match="corpus_version"):
        _run(payload, make_deps())


def test_pinned_corpus_version_reaches_the_result(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    deps = dataclasses.replace(make_deps(), corpus_version="2026-11-20T10:00Z")
    output, _ = _run(payload, deps)
    assert output.result.corpus_version == "2026-11-20T10:00Z"


def test_check_input_from_a_newer_backend_runs(
    payload: Payload, make_deps: Callable[..., CheckDeps]
) -> None:
    newer = {
        **payload,
        "from_v_next": 1,
        "request": {**payload["request"], "from_v_next": 1},
    }
    output, _ = _run(newer, make_deps())
    assert output.result.check_id == "check-1"
