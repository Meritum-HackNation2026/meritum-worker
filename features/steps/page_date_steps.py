"""Steps of the page publication date scenarios in features/checks.feature.

The extraction prompt carries the date of a linked page and a date from the
future is dropped; stub model, no network.
"""

from dataclasses import replace
from datetime import date

from behave import given, then
from behave.runner import Context
from check_support import RECEIVED_AT, deps
from check_workflow_steps import ARTICLE_TEXT
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.shared.llm import LlmPort, LlmResult, Prompt
from pydantic import BaseModel

from meritum_worker.checks import FakePageFetcher


class _PromptRecorder:
    """Passes calls to the stub model and keeps every prompt."""

    def __init__(self, llm: LlmPort) -> None:
        self.llm = llm
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.prompts.append(prompt)
        return await self.llm.complete(prompt, output)


@given("artykuł opublikowany {day} mówi „wczoraj rząd przyjął ustawę”")
def article_says_yesterday(context: Context, day: str) -> None:
    page = FetchedPage(
        url="https://example.com/ustawa",
        content_type="text/html",
        untrusted_text="Wczoraj rząd przyjął ustawę.",
        published_at=date.fromisoformat(day),
    )
    stub = deps("claims_yesterday.json", FakePageFetcher(page))
    context.recorder = _PromptRecorder(stub.llm)
    context.deps = replace(stub, llm=context.recorder)
    context.link = page.url
    context.received_at = RECEIVED_AT.replace(year=2026, month=11, day=21)


@given("metadane strony podają datę publikacji {day}, późniejszą niż chwila pobrania")
def page_dated_in_the_future(context: Context, day: str) -> None:
    page = FetchedPage(
        url="https://example.com/artykul",
        content_type="text/html",
        untrusted_text=ARTICLE_TEXT,
        published_at=date.fromisoformat(day),
    )
    assert page.published_at is not None
    assert page.published_at > RECEIVED_AT.date()
    context.deps = deps("claims_article.json", FakePageFetcher(page))
    context.link = page.url


@then("prompt ekstrakcji podaje datę {published}, a twierdzenie ma claim_date {day}")
def relative_date_from_publication(context: Context, published: str, day: str) -> None:
    assert published in context.recorder.prompts[0].instructions
    (claim,) = context.result.result.claims
    assert claim.claim_date == date.fromisoformat(day)


@then("twierdzenie bez daty w tekście nie dostaje daty {day}")
def future_date_dropped(context: Context, day: str) -> None:
    undated = context.result.result.claims[0]
    assert undated.claim_date != date.fromisoformat(day)
    assert undated.claim_date_source == "today"
