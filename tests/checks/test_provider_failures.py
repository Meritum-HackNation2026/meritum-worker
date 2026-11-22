import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta

import pytest
from meritum_core.checks.contracts import CheckRecord, CheckResult
from meritum_core.checks.transcription import TranscriptionUnavailableError
from meritum_core.corpus.web_search import (
    WebSearchCandidate,
    WebSearchRateLimitError,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
)
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import MaskedText
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    InlineCheckRuntime,
    run_check,
    steps,
)
from meritum_worker.checks.constants import STEP_TIMEOUTS
from meritum_worker.corpus import WEB_SEARCH_MARGIN, WEB_SEARCH_TIMEOUT

MISSING_KEY = "vertex: no credentials in MERITUM_LLM_API_KEY"
RATE_LIMIT = "vertex: 429 quota exceeded for MERITUM_LLM_API_KEY"
"""What a provider error may say; none of it may reach the result or the record."""


def _check(
    make_job: Callable[..., CheckInput], deps: CheckDeps
) -> tuple[CheckResult, CheckRecord]:
    payload = make_job().model_dump(mode="json")
    output = asyncio.run(run_check(payload, "check-1", deps, InlineCheckRuntime()))
    record = asyncio.run(deps.records.get("check-1"))
    assert record is not None
    return output.result, record


def _raising(name: str, error: Exception) -> Callable[..., object]:
    async def step(_state: CheckState, _deps: CheckDeps) -> CheckState:
        await asyncio.sleep(0)
        raise error

    step.__name__ = name
    return step


def test_web_search_with_its_pages_waits_at_most_10_seconds() -> None:
    assert timedelta(seconds=10) == WEB_SEARCH_TIMEOUT
    assert timedelta(seconds=1) >= WEB_SEARCH_MARGIN
    assert STEP_TIMEOUTS["search_web"] == WEB_SEARCH_TIMEOUT + WEB_SEARCH_MARGIN


def test_web_search_timeout_ends_as_technical_failure_and_is_recorded(
    monkeypatch: pytest.MonkeyPatch,
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
) -> None:
    async def hanging(state: CheckState, _deps: CheckDeps) -> CheckState:
        await asyncio.sleep(60)
        return state

    hanging.__name__ = "search_web"
    monkeypatch.setattr(steps, "search_web", hanging)
    monkeypatch.setitem(STEP_TIMEOUTS, "search_web", timedelta(milliseconds=10))
    result, record = _check(make_job, make_deps())
    assert result.status == "technical_failure"
    assert result.failure_code == "web_search_unavailable"
    assert result.claims == []
    assert record.status == "technical_failure"
    assert record.retrieval_errors == ["search_web: timeout"]


@pytest.mark.parametrize(
    "case",
    [
        (
            "extract_claims",
            ProviderUnavailableError(MISSING_KEY),
            "provider_unavailable",
        ),
        ("search_web", ProviderUnavailableError(RATE_LIMIT), "web_search_unavailable"),
        (
            "transcribe_audio",
            TranscriptionUnavailableError(RATE_LIMIT),
            "transcription_failed",
        ),
    ],
    ids=["missing-key", "rate-limit", "transcription"],
)
def test_provider_error_ends_as_technical_failure_without_the_key(
    monkeypatch: pytest.MonkeyPatch,
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    case: tuple[str, Exception, str],
) -> None:
    code, error, failure_code = case
    monkeypatch.setattr(steps, code, _raising(code, error))
    result, record = _check(make_job, make_deps())
    assert result.status == "technical_failure"
    assert result.failure_code == failure_code
    assert record.status == "technical_failure"
    assert record.retrieval_errors == [f"{code}: {failure_code}"]
    dumped = result.model_dump_json() + record.model_dump_json()
    assert "API_KEY" not in dumped
    assert "vertex" not in dumped


class _FailingWebSearch:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def search(
        self, query: MaskedText, *, limit: int = 10
    ) -> list[WebSearchCandidate]:
        del query, limit
        raise self.error


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (WebSearchRateLimitError(RATE_LIMIT), "web_search_unavailable"),
        (WebSearchUnavailableError(MISSING_KEY), "web_search_unavailable"),
        (WebSearchTimeoutError("no answer in 10.0 s"), "timeout"),
    ],
    ids=["rate-limit", "unavailable", "timeout"],
)
def test_web_search_failure_in_the_real_step_ends_as_technical_failure(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    error: Exception,
    reason: str,
) -> None:
    deps = replace(make_deps(), web_search=_FailingWebSearch(error))
    result, record = _check(make_job, deps)
    assert result.status == "technical_failure"
    assert result.failure_code == "web_search_unavailable"
    assert record.retrieval_errors == [f"search_web: {reason}"]
    assert "API_KEY" not in record.model_dump_json()
