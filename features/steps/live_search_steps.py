"""Steps of the live web search scenarios in features/corpus.feature.

The check runs inline on the core stub model, the core stub search provider
behind the catalogue filter, a fake page fetcher and the core injection
detector; no network, no database.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import (
    WebSearchCandidate,
    WebSearchPort,
    WebSearchProvider,
    WebSearchSettings,
    build_web_search,
)
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.injection import NullInjectionGate, build_injection_detector
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    corpus_ports,
    run_check,
)
from meritum_worker.corpus import FakeWebSearch

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CHECK_ID = "check-behave-live"
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
RCB_URL = "https://www.gov.pl/web/rcb/ostrzezenie-przed-burzami"
TEXT = "RCB wydało dziś rano ostrzeżenie przed burzami dla Mazowsza"
PAGE_TEXT = (
    "Rządowe Centrum Bezpieczeństwa ostrzega przed burzami z gradem na Mazowszu."
    " Alert wysłano 5 stycznia 2026 rano."
)


def _deps(
    context: Context, page_text: str, web_search: WebSearchPort | None = None
) -> None:
    llm = build_llm(
        LlmSettings(
            provider=LlmProvider.STUB, stub_fixtures=FIXTURES / "llm_stub_rcb.json"
        )
    )
    catalog = load_catalog()
    search = WebSearchSettings(
        provider=WebSearchProvider.STUB, stub_fixture=FIXTURES / "web_search_rcb.json"
    )
    context.pages = FakePageFetcher(
        FetchedPage(url=RCB_URL, content_type="text/html", untrusted_text=page_text)
    )
    context.deps = CheckDeps(
        llm=llm,
        records=InMemoryCheckRecordRepository(),
        pages=context.pages,
        pii=NullPiiGate(),
        web_search=web_search or build_web_search(search, catalog),
        injection=build_injection_detector(llm=llm, gate=NullInjectionGate()),
        catalog=catalog,
        **audio_ports(),
        **corpus_ports(),
    )


def _run(context: Context) -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text=TEXT),
        session_id="session-behave-live",
        received_at=RECEIVED_AT,
    )
    context.runtime = InlineCheckRuntime()
    output = asyncio.run(
        run_check(job.model_dump(mode="json"), CHECK_ID, context.deps, context.runtime)
    )
    context.result = output.result
    context.record = asyncio.run(context.deps.records.get(CHECK_ID))


@given("twierdzenie o komunikacie RCB z dzisiejszego ranka, którego nie ma w korpusie")
def fresh_rcb_claim(context: Context) -> None:
    _deps(context, PAGE_TEXT)


@when("sprawdzenie uruchamia wyszukiwanie w korpusie i w sieci równolegle")
def searches_in_parallel(context: Context) -> None:
    _run(context)
    # Both search codes are active in the same published status before either ends.
    together = [
        status
        for status in context.runtime.published
        if {s.code for s in status.steps if s.status == "active"}
        == {"search_corpus", "search_web"}
    ]
    assert together, "search_corpus and search_web never ran at the same time"


@then(
    "strona z gov.pl po skanie jest dowodem w tym sprawdzeniu z Source.via = web_search"
    " i jest w CheckRecord.source_ids"
)
def page_is_evidence(context: Context) -> None:
    assert context.result.status == "done"
    assert context.record.web_search_calls == 1
    (source_id,) = context.record.source_ids
    assert source_id.startswith("web-")
    assert context.record.injection_events == []


@then("do wspólnego korpusu dołącza dopiero z następną migawką")
def corpus_unchanged(context: Context) -> None:
    # The check answers on the snapshot it searched; the page is not in it.
    # Handing the page to the next snapshot's ingestion is worker#90.
    assert context.result.corpus_version == context.record.corpus_version
    assert context.record.corpus_version == "none"


@given("wyszukiwarka zwraca adres z domeny spoza katalogu")
def search_returns_outside(context: Context) -> None:
    # A port that lets the address through: only the worker's filter stops it.
    outside = WebSearchCandidate(
        url="https://example.com/rcb-ostrzezenie",
        domain="www.gov.pl/web/rcb",
        publisher_id="rcb",
    )
    _deps(context, PAGE_TEXT, FakeWebSearch((outside,)))


@when("wynik przechodzi nasz filtr domen")
def result_through_filter(context: Context) -> None:
    _run(context)


@then("strona nie jest pobierana ani cytowana")
def page_not_fetched(context: Context) -> None:
    assert context.pages.calls == []
    assert context.record.source_ids == []
    assert context.record.web_search_calls == 1


@given('pobrana strona zawiera "{instruction}"')
def page_with_instruction(context: Context, instruction: str) -> None:
    _deps(context, f"{PAGE_TEXT} {instruction}.")


@when("kończy się skan w kwarantannie")
def quarantine_scan_ends(context: Context) -> None:
    _run(context)


@then(
    "strona wypada z dowodów, InjectionEvent ma action = source_dropped,"
    " a limitations to odnotowują"
)
def page_dropped(context: Context) -> None:
    url = RCB_URL
    assert context.record.source_ids == []
    (event,) = context.record.injection_events
    assert event.action == "source_dropped"
    assert str(event.source_url) == url
    assert "Ignore previous instructions" in event.excerpt
    assert url in context.result.limitations
