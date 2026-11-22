"""Steps for the public API scenarios of corpus.feature (worker#82)."""

import asyncio
import dataclasses
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from catalog_ingest_steps import NOW, entry, ingest, start

from meritum_worker.corpus.fakes import FakePublicApi

SEJM_ACTS = "https://api.sejm.gov.pl/eli/acts/DU/2026"
RECORDED = Path(__file__).parents[2] / "tests" / "corpus" / "fixtures" / "api"


def start_with_api(context: Context, api: FakePublicApi, *, others: int) -> None:
    sejm = entry("api.sejm.gov.pl", ingest="api", license="materiał urzędowy")
    start(context, [sejm, *(entry(f"urzad{i}.gov.pl") for i in range(others))])
    context.deps = dataclasses.replace(context.deps, api_fetcher=api.fetcher())


@given(
    "pozycja katalogu z ingest = api dla api.sejm.gov.pl i odpowiedź API"
    " z {count:d} aktami prawnymi"
)
def sejm_api(context: Context, count: int) -> None:
    api = FakePublicApi()
    recorded = (RECORDED / "sejm-eli-du.json").read_text(encoding="utf-8")
    api.answer(SEJM_ACTS, recorded)
    start_with_api(context, api, others=0)
    context.expected = count


@given("API pozycji katalogu odpowiada błędem 500")
def failing_api(context: Context) -> None:
    api = FakePublicApi()
    api.answer(SEJM_ACTS, '{"error": "Internal Server Error"}', status=500)
    start_with_api(context, api, others=2)


@when("workflow wczytywania katalogu działa")
def ingestion_runs(context: Context) -> None:
    ingest(context)


@then("{count:d} dokumenty trafiają do korpusu z publisher_id i licencją z katalogu")
def api_documents(context: Context, count: int) -> None:
    documents = asyncio.run(context.store.documents())
    assert len(documents) == count == context.expected
    for document in documents:
        assert document.publisher_id == "api-sejm-gov-pl"
        assert document.license == "materiał urzędowy"
        assert document.fetched_at == NOW
        assert document.url.startswith("https://api.sejm.gov.pl/eli/acts/DU/2026/")


@then("błąd jest w raporcie przebiegu z domeną, a pozostałe pozycje są wczytane")
def failure_reported(context: Context) -> None:
    (failure,) = context.report.failures
    assert (failure.domain, failure.url, failure.reason) == (
        "api.sejm.gov.pl",
        SEJM_ACTS,
        "http_error",
    )
    domains = {d.domain for d in asyncio.run(context.store.documents())}
    assert domains == {"urzad0.gov.pl", "urzad1.gov.pl"}
