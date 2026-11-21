"""Steps of scenario J in features/checks.feature: a provider fails or times out.

The web search step and the model are replaced with fakes; no network.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import (
    LlmPort,
    LlmProvider,
    LlmResult,
    LlmSettings,
    Prompt,
    build_llm,
)
from meritum_core.shared.llm import ProviderUnavailableError as Unavailable
from pydantic import BaseModel

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    FakePageFetcher,
    InlineCheckRuntime,
    run_check,
    steps,
)
from meritum_worker.checks.constants import STEP_TIMEOUTS

CHECK_ID = "check-behave-j"
TEXT = "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"


class _Failing503Llm:
    """LlmPort after the core adapter's 3 attempts all got 503: it gives up."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        del prompt, output
        self.calls += 1
        msg = "503 from vertex, key MERITUM_LLM_API_KEY"
        raise Unavailable(msg)


def _deps(llm: LlmPort | None = None) -> CheckDeps:
    return CheckDeps(
        llm=llm or build_llm(LlmSettings(provider=LlmProvider.STUB)),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
    )


def _run(context: Context) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text=TEXT),
        session_id="session-behave-j",
        received_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
    )
    output = asyncio.run(
        run_check(
            job.model_dump(mode="json"), CHECK_ID, context.deps, InlineCheckRuntime()
        )
    )
    context.result = output
    context.record = asyncio.run(context.deps.records.get(CHECK_ID))


@given("sprawdzenie czeka na wynik wyszukiwania w sieci")
def waits_for_web_search(context: Context) -> None:
    context.deps = _deps()

    async def search_web(state: CheckState, _deps: CheckDeps) -> CheckState:
        await asyncio.sleep(3600)
        return state

    for patcher in (
        patch.object(steps, "search_web", search_web),
        patch.dict(STEP_TIMEOUTS),
    ):
        patcher.start()
        context.add_cleanup(patcher.stop)


@when("wyszukiwarka nie odpowiada przez 10 s")
def web_search_hangs(context: Context) -> None:
    assert STEP_TIMEOUTS["search_web"] == timedelta(seconds=10)
    # The real limit is checked above; the run uses a short one to stay fast.
    STEP_TIMEOUTS["search_web"] = timedelta(milliseconds=10)
    _run(context)


@then("wynik ma stan technical_failure bez twierdzeń i bez werdyktu")
def failed_without_verdict(context: Context) -> None:
    result = context.result.result
    assert result.status == "technical_failure"
    assert result.failure_code == "web_search_unavailable"
    assert result.claims == []
    assert context.record.verdicts == []


@then("CheckRecord.retrieval_errors zapisuje przekroczenie czasu")
def record_has_timeout(context: Context) -> None:
    assert context.record.retrieval_errors == ["search_web: timeout"]


@given("adapter modelu zwraca błąd 503 przy każdej z 3 prób")
def model_fails_three_times(context: Context) -> None:
    context.llm = _Failing503Llm()
    context.deps = _deps(context.llm)


@when("workflow kończy krok")
def workflow_ends_step(context: Context) -> None:
    _run(context)


@then(
    "wynik ma stan technical_failure, a komunikat nie zawiera nazwy klucza ani dostawcy"
)
def failed_without_key_or_provider(context: Context) -> None:
    result = context.result.result
    assert context.llm.calls == 1
    assert result.status == "technical_failure"
    assert result.failure_code == "provider_unavailable"
    shown = result.model_dump_json() + context.record.model_dump_json()
    assert "API_KEY" not in shown
    assert "vertex" not in shown
