"""Cassette adapters: record a provider's answers, replay them without it."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetchError,
)
from meritum_core.security.pii import MaskedText, PiiGateUnavailableError
from meritum_core.shared.llm import (
    LlmResult,
    LlmUsage,
    Prompt,
    ProviderUnavailableError,
)
from pydantic import BaseModel

from meritum_worker.checks import FakePageFetcher
from meritum_worker.observability import Cassette, CassetteMissError
from meritum_worker.observability.adapters import (
    CassetteLlm,
    CassettePages,
    CassettePii,
)

PROMPT = Prompt(instructions="Wyodrębnij twierdzenia.", data=("Tekst.",))
PAGE = FetchedPage(
    url="https://example.org/a", content_type="text/html", untrusted_text="Treść."
)
URL = "https://example.org/a"
OTHER_URL = "https://example.org/b"
NOW = datetime(2026, 11, 20, 10, tzinfo=UTC)


class _Answer(BaseModel):
    text: str


USAGE = LlmUsage(
    provider="vertex", model="m", region="eu", input_tokens=3, output_tokens=2
)


class _Answers:
    """LlmPort answering "a", "b", ... on successive calls."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete[T: BaseModel](
        self,
        prompt: Prompt,  # ruff: ignore[unused-method-argument]  # the protocol names it; answers ignore it
        output: type[T],
    ) -> LlmResult[T]:
        text = "ab"[self.calls]
        self.calls += 1
        return LlmResult[T](output=output.model_validate({"text": text}), usage=USAGE)


class _Broken:
    @staticmethod
    async def complete[T: BaseModel](prompt: Prompt, output: type[T]) -> LlmResult[T]:
        raise ProviderUnavailableError(prompt, output)


def _ask(llm: CassetteLlm) -> LlmResult[_Answer]:
    return asyncio.run(llm.complete(PROMPT, _Answer))


def _get(pages: CassettePages, url: str) -> FetchedPage:
    return asyncio.run(pages.fetch(url, purpose=FetchPurpose.USER_LINK))


def test_replay_returns_recorded_answers_in_order(tmp_path: Path) -> None:
    cassette = Cassette()
    recorder = CassetteLlm(cassette, _Answers())
    recorded = [_ask(recorder) for _ in range(2)]
    cassette.save(tmp_path / "cassette.json")
    replay = CassetteLlm(Cassette.load(tmp_path / "cassette.json"), None)
    assert [_ask(replay) for _ in range(2)] == recorded
    assert [r.output.text for r in recorded] == ["a", "b"]
    with pytest.raises(CassetteMissError):
        _ask(replay)


def test_recorded_provider_failure_replays_as_failure() -> None:
    cassette = Cassette()
    with pytest.raises(ProviderUnavailableError):
        _ask(CassetteLlm(cassette, _Broken()))
    with pytest.raises(ProviderUnavailableError):
        _ask(CassetteLlm(cassette, None))


def test_unrecorded_prompt_is_a_miss() -> None:
    with pytest.raises(CassetteMissError):
        _ask(CassetteLlm(Cassette(), None))


def test_pages_replay_page_and_failure_with_fetch_time() -> None:
    cassette = Cassette()
    page = _get(CassettePages(cassette, FakePageFetcher(PAGE), lambda: NOW), URL)
    with pytest.raises(PageFetchError):
        _get(CassettePages(cassette, FakePageFetcher(), lambda: NOW), OTHER_URL)
    replay = CassettePages(cassette, None)
    assert _get(replay, URL) == page
    with pytest.raises(PageFetchError) as error:
        _get(replay, OTHER_URL)
    assert error.value.reason is FetchFailureReason.UNREACHABLE
    [take] = cassette.pages[CassettePages.key(URL, FetchPurpose.USER_LINK)]
    assert take is not None
    assert take.fetched_at == NOW


def test_unrecorded_page_is_a_miss() -> None:
    with pytest.raises(CassetteMissError):
        _get(CassettePages(Cassette(), None), URL)


class _Masker:
    @staticmethod
    async def mask(text: str) -> MaskedText:
        return MaskedText(text=text.replace("Jan Kowalski", "[OSOBA]"), replaced=1)


class _BrokenMasker:
    @staticmethod
    async def mask(text: str) -> MaskedText:
        raise PiiGateUnavailableError(len(text))


def test_pii_replays_masked_text_and_gate_failure() -> None:
    cassette = Cassette()
    masked = asyncio.run(CassettePii(cassette, _Masker()).mask("Pisze Jan Kowalski."))
    with pytest.raises(PiiGateUnavailableError):
        asyncio.run(CassettePii(cassette, _BrokenMasker()).mask("Inny tekst."))
    replay = CassettePii(cassette, None)
    assert asyncio.run(replay.mask("Pisze Jan Kowalski.")) == masked
    with pytest.raises(PiiGateUnavailableError):
        asyncio.run(replay.mask("Inny tekst."))
    assert "Jan Kowalski" not in cassette.model_dump_json()


class _SlowFetcher:
    @staticmethod
    async def fetch(url: str, *, purpose: FetchPurpose) -> FetchedPage:
        await asyncio.sleep(1)
        raise AssertionError(url, purpose)


async def _within_deadline(pages: CassettePages) -> FetchedPage:
    async with asyncio.timeout(0.01):
        return await pages.fetch(URL, purpose=FetchPurpose.SOURCE)


def test_call_cut_off_by_the_deadline_replays_as_the_same_timeout() -> None:
    cassette = Cassette()
    with pytest.raises(TimeoutError):
        asyncio.run(_within_deadline(CassettePages(cassette, _SlowFetcher())))
    with pytest.raises(TimeoutError):
        asyncio.run(_within_deadline(CassettePages(cassette, None)))
