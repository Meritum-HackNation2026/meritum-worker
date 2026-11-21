"""Steps of the `check` workflow scenarios in features/checks.feature.

They run the workflow on the core stub model and the in-memory record repository,
with steps called inline instead of through DBOS; no network, no database.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.contracts import CheckRecord
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import CheckDeps, InlineCheckRuntime, run_check

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CHECK_ID = "check-behave-1"
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
DEFAULT_TEXT = "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"


def _deps(fixture: str) -> CheckDeps:
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=FIXTURES / fixture)
    return CheckDeps(llm=build_llm(settings), records=InMemoryCheckRecordRepository())


def _run(context: Context, text: str) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text=text),
        session_id="session-behave-1",
        received_at=RECEIVED_AT,
    )
    context.runtime = InlineCheckRuntime()
    context.result = asyncio.run(
        run_check(job.model_dump(mode="json"), CHECK_ID, context.deps, context.runtime)
    )
    context.record = asyncio.run(context.deps.records.get(CHECK_ID))


@given("worker działa z MERITUM_LLM_PROVIDER=stub")
def worker_runs_on_stub(context: Context) -> None:
    context.deps = _deps("llm_stub_answer.json")


@given("stub zwraca wynik niezgodny z regułami kontraktu")
def stub_breaks_contract(context: Context) -> None:
    context.deps = _deps("llm_stub_broken_answer.json")


@when('workflow "check" dostaje CheckRequest z tekstem "{text}"')
def check_gets_text(context: Context, text: str) -> None:
    _run(context, text)


@when("workflow buduje CheckResult")
def check_builds_result(context: Context) -> None:
    _run(context, DEFAULT_TEXT)


@then("workflow kończy się stanem done z CheckResult zgodnym z kontraktem")
def check_is_done(context: Context) -> None:
    result = context.result.result
    assert result.status == "done"
    assert result.check_id == CHECK_ID
    final = context.runtime.published[-1]
    assert final.result == result
    assert {step.status for step in final.steps} == {"done"}


@then(
    "CheckRecord ma question_masked, channel, received_at, answered_at, "
    "corpus_version, verdicts, source_ids, escalation i retention_until"
)
def record_is_complete(context: Context) -> None:
    record = context.record
    assert isinstance(record, CheckRecord)
    assert record.question_masked == DEFAULT_TEXT
    assert record.channel == "web"
    assert record.received_at == RECEIVED_AT
    assert record.answered_at >= RECEIVED_AT
    assert record.corpus_version
    assert record.verdicts == ["insufficient_evidence"]
    assert record.source_ids == []
    assert record.escalation is None
    assert record.retention_until == RECEIVED_AT + timedelta(days=30)


@then("wynik ma stan technical_failure bez twierdzeń")
def result_is_technical_failure(context: Context) -> None:
    result = context.result.result
    assert result.status == "technical_failure"
    assert result.claims == []


@then("CheckRecord ma status technical_failure")
def record_is_technical_failure(context: Context) -> None:
    assert context.record.status == "technical_failure"
    assert context.record.verdicts == []
