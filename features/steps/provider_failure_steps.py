"""Steps of scenario J in features/checks.feature: a provider fails or times out.

The web search step and the model are replaced with fakes; no network.
"""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override
from unittest.mock import patch

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import MaskedText, NullPiiGate
from meritum_core.shared.llm import (
    LlmPort,
    LlmProvider,
    LlmResult,
    LlmSettings,
    Prompt,
    ProviderUnavailableError,
    build_llm,
)
from pydantic import BaseModel

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    corpus_ports,
    run_check,
    web_ports,
)
from meritum_worker.corpus import WEB_SEARCH_TIMEOUT, FakeWebSearch, live_search

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "llm_stub_answer.json"
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
        raise ProviderUnavailableError(msg)


def _deps(llm: LlmPort | None = None) -> CheckDeps:
    return CheckDeps(
        llm=llm
        or build_llm(LlmSettings(provider=LlmProvider.STUB, stub_fixtures=FIXTURE)),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
        **corpus_ports(),
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
    class _HangingSearch(FakeWebSearch):
        @override
        async def search(
            self, query: MaskedText, *, limit: int = 10
        ) -> list[WebSearchCandidate]:
            await asyncio.sleep(3600)
            return await super().search(query, limit=limit)

    context.deps = replace(_deps(), web_search=_HangingSearch())


@when("wyszukiwarka nie odpowiada przez 10 s")
def web_search_hangs(context: Context) -> None:
    assert timedelta(seconds=10) == WEB_SEARCH_TIMEOUT
    # The real limit is checked above; the run uses a short one to stay fast.
    with patch.object(live_search, "WEB_SEARCH_TIMEOUT", timedelta(milliseconds=10)):
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
    assert context.record.retrieval_errors == ["extract_claims: provider_unavailable"]
    shown = result.model_dump_json() + context.record.model_dump_json()
    assert "API_KEY" not in shown
    assert "vertex" not in shown
