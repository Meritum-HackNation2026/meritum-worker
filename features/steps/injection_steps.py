"""Steps of the injection scenarios in features/security.feature.

The check runs inline on the core stub model and the core layered detector
(patterns plus the stub's isolated classifier); no network, no database.
"""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from behave import given, then, when
from behave.runner import Context
from check_support import deps, run
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.security.injection import NullInjectionGate, build_injection_detector
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings
from meritum_core.shared.llm import LlmPort, LlmResult, Prompt
from pydantic import BaseModel

from meritum_worker import corpus
from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus.fakes import FakeCatalogSite

PAGE_URL = "https://example.com/wroclaw"
INSTRUCTION = "instructions"
NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)


class _SeenLlm:
    # Records every data part the model gets, then answers from the stub.
    def __init__(self, llm: LlmPort) -> None:
        self.llm = llm
        self.data: list[str] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.data += prompt.data
        return await self.llm.complete(prompt, output)


def _checked(context: Context, pages: FakePageFetcher | None = None) -> None:
    context.deps = deps("llm_stub_answer.json", pages)
    seen = _SeenLlm(context.deps.llm)
    detector = build_injection_detector(llm=context.deps.llm, gate=NullInjectionGate())
    context.seen = seen
    context.deps = replace(context.deps, llm=seen, injection=detector)


@given('tekst "{text}" i detektor wstrzyknięć z core')
def text_with_detector(context: Context, text: str) -> None:
    context.input_text = text
    _checked(context)


@given('link do strony z tekstem "{text}" i detektor wstrzyknięć z core')
def link_with_detector(context: Context, text: str) -> None:
    context.page_text = text
    page = FetchedPage(url=PAGE_URL, content_type="text/html", untrusted_text=text)
    _checked(context, FakePageFetcher(page))


@when("system sprawdza tekst")
def system_checks_text(context: Context) -> None:
    run(context, text=context.input_text)


@when("system sprawdza link")
def system_checks_link(context: Context) -> None:
    run(context, url=PAGE_URL)


@then(
    "model dostaje tekst bez polecenia, a CheckRecord ma InjectionEvent"
    " z location = input i action = instruction_removed"
)
def model_gets_clean_text(context: Context) -> None:
    assert context.seen.data, "the model was never called"
    assert all("Zignoruj" not in part for part in context.seen.data), context.seen.data
    assert any("mikroczipy" in part for part in context.seen.data)
    events = context.record.injection_events
    assert [(e.location, e.action) for e in events] == [
        ("input", "instruction_removed")
    ], events


@then(
    "model nie dostaje tekstu strony, CheckRecord ma InjectionEvent z location"
    " = source i action = source_dropped, a limitations to odnotowują"
)
def page_dropped(context: Context) -> None:
    assert all(INSTRUCTION not in part for part in context.seen.data)
    assert all("Wrocław" not in part for part in context.seen.data)
    events = context.record.injection_events
    assert [(e.location, e.action, str(e.source_url)) for e in events] == [
        ("source", "source_dropped", PAGE_URL)
    ], events
    assert any(PAGE_URL in limit for limit in context.result.result.limitations)


@given('strona katalogu z tekstem "{text}"')
def catalog_page(context: Context, text: str) -> None:
    context.entry = CatalogEntry.model_validate(
        {
            "domain": "urzad.gov.pl",
            "publisher": "Urząd",
            "publisher_id": "urzad-gov-pl",
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY 4.0",
            "ingest": "static",
            "qualified_because": "Źródło z listy organizatora konkursu.",
            "tdm_reservation": "none",
        }
    )
    context.page = FetchedPage(
        url="https://urzad.gov.pl/komunikat",
        content_type="text/html",
        untrusted_text=text,
    )
    llm = deps("llm_stub_answer.json").llm
    site = FakeCatalogSite(pages_per_domain=1)
    context.store = corpus.build_corpus_writer()
    context.ingest = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=context.store,
        injection=build_injection_detector(llm=llm, gate=NullInjectionGate()),
    )


@when("strona jest wczytywana do korpusu")
def page_is_ingested(context: Context) -> None:
    context.report = asyncio.run(
        corpus.store_page(context.page, context.entry, context.ingest, now=NOW)
    )


@then('nie trafia do korpusu, a raport podaje powód "{reason}"')
def page_not_stored(context: Context, reason: str) -> None:
    assert [f.reason for f in context.report.failures] == [reason], context.report
    assert context.report.added == 0
