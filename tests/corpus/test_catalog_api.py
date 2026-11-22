import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.catalog_api import (
    ApiRecord,
    InvalidApiResponseError,
    api_listings,
    parse_listing,
)
from meritum_worker.corpus.documents import DocumentMeta
from meritum_worker.corpus.fakes import FakeCatalogSite, FakePublicApi
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "api"
SEJM = "https://api.sejm.gov.pl/eli/acts/DU/2026"


def entry(domain: str, **fields: object) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": "Urząd",
            "publisher_id": "sejm",
            "kind": "dane_publiczne",
            "tier": "primary",
            "license": "materiał urzędowy",
            "ingest": "api",
            "qualified_because": "Oficjalne API.",
            **fields,
        }
    )


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def parsed(domain: str, *names: str) -> list[ApiRecord]:
    listings = api_listings(entry(domain), NOW)
    assert len(listings) == len(names)
    return [
        record
        for listing, name in zip(listings, names, strict=True)
        for record in parse_listing(listing, recorded(name))
    ]


def run(
    api: FakePublicApi, *entries: CatalogEntry
) -> tuple[corpus.IngestReport, list[DocumentMeta]]:
    store = MemoryCorpusWriter()
    site = FakeCatalogSite(pages_per_domain=1)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=CleanInjectionDetector(),
        api_fetcher=api.fetcher(),
    )
    report = asyncio.run(corpus.ingest_catalog(list(entries), deps, now=NOW))
    return report, asyncio.run(store.documents())


def test_sejm_acts_become_dated_records_with_their_eli() -> None:
    records = parsed("api.sejm.gov.pl", "sejm-eli-du.json")
    assert [r.url for r in records] == [
        "https://api.sejm.gov.pl/eli/acts/DU/2026/1530",
        "https://api.sejm.gov.pl/eli/acts/DU/2026/1529",
        "https://api.sejm.gov.pl/eli/acts/DU/2026/1528",
    ]
    assert records[0].published_at == date(2026, 11, 19)
    assert "Rozporządzenie Ministra Cyfryzacji" in records[0].text
    assert "Dz.U. 2026 poz. 1530" in records[0].text


def test_nbp_tables_and_gold_prices_name_values_and_days() -> None:
    records = parsed("api.nbp.pl", "nbp-tables-a.json", "nbp-gold.json")
    table = records[0]
    assert table.url == "https://api.nbp.pl/api/exchangerates/tables/A/2026-11-19/"
    assert "dolar amerykański (USD) = 4.0176 zł" in table.text
    gold = records[-1]
    assert gold.url == "https://api.nbp.pl/api/cenyzlota/2026-11-20/"
    assert gold.published_at == date(2026, 11, 20)
    assert "481.23 zł" in gold.text
    assert len(records) == 2 + 3


def test_dane_datasets_drop_html_and_keep_their_licence() -> None:
    records = parsed("dane.gov.pl", "dane-datasets.json")
    first = records[0]
    assert first.url.startswith("https://dane.gov.pl/pl/dataset/32812,")
    assert "<p>" not in first.text
    assert "Licencja zbioru: CC0 1.0." in first.text
    assert first.published_at == date(2026, 11, 21)


def test_bdl_subjects_and_eurostat_series() -> None:
    subjects = parsed("bdl.stat.gov.pl", "bdl-subjects.json")
    assert subjects[0].text == "Dziedzina Banku Danych Lokalnych GUS K15: CENY."
    listing = api_listings(entry("ec.europa.eu/eurostat"), NOW)[0]
    (series,) = parse_listing(listing, recorded("eurostat-hicp.json"))
    assert series.url == listing.url
    assert series.text.splitlines()[1:] == [
        "2025-10: 2.9",
        "2025-11: 2.6",
        "2025-12: 2.5",
    ]
    assert "Poland" in series.text


@pytest.mark.parametrize("body", ["not json", "{}", '{"items": [{"title": 1}]}'])
def test_answer_of_another_shape_is_invalid(body: str) -> None:
    listing = api_listings(entry("api.sejm.gov.pl"), NOW)[0]
    with pytest.raises(InvalidApiResponseError):
        parse_listing(listing, body)


def test_api_entry_stores_each_record_with_catalogue_metadata() -> None:
    api = FakePublicApi()
    api.answer(SEJM, recorded("sejm-eli-du.json"))
    report, documents = run(api, entry("api.sejm.gov.pl"))
    assert report.added == len(documents) == 3
    assert {(d.publisher_id, d.license) for d in documents} == {
        ("sejm", "materiał urzędowy")
    }
    assert "https://api.sejm.gov.pl/robots.txt" in api.requested


def test_failing_api_is_reported_and_other_entries_still_load() -> None:
    api = FakePublicApi()
    api.answer(SEJM, '{"error": "boom"}', status=500)
    report, documents = run(
        api, entry("api.sejm.gov.pl"), entry("urzad.gov.pl", ingest="static")
    )
    (failure,) = report.failures
    assert (failure.domain, failure.url, failure.reason) == (
        "api.sejm.gov.pl",
        SEJM,
        "http_error",
    )
    assert {d.domain for d in documents} == {"urzad.gov.pl"}


def test_robots_txt_still_guards_api_requests() -> None:
    api = FakePublicApi()
    api.answer(
        "https://api.sejm.gov.pl/robots.txt",
        "User-agent: *\nDisallow: /",
        content_type="text/plain",
    )
    api.answer(SEJM, recorded("sejm-eli-du.json"))
    report, documents = run(api, entry("api.sejm.gov.pl"))
    assert [f.reason for f in report.failures] == ["robots_disallowed"]
    assert documents == []


def test_json_answer_reaches_untrusted_text_and_html_stays_html() -> None:
    api = FakePublicApi()
    api.answer(
        "https://dane.gov.pl/x", '{"a": 1}', content_type="application/vnd.api+json"
    )
    api.answer("https://dane.gov.pl/y", "%PDF", content_type="application/pdf")
    fetcher = api.fetcher()
    page = asyncio.run(
        fetcher.fetch("https://dane.gov.pl/x", purpose=FetchPurpose.SOURCE)
    )
    assert page.untrusted_text == '{"a": 1}'
    with pytest.raises(PageFetchError, match="unsupported_content"):
        asyncio.run(fetcher.fetch("https://dane.gov.pl/y", purpose=FetchPurpose.SOURCE))


def test_private_address_is_refused_before_the_transport() -> None:
    api = FakePublicApi()
    with pytest.raises(PageFetchError, match="blocked_address"):
        asyncio.run(
            api.fetcher().fetch("https://127.0.0.1/", purpose=FetchPurpose.SOURCE)
        )
    assert api.requested == []


def test_api_without_parser_or_fetcher_is_unsupported() -> None:
    report, _ = run(FakePublicApi(), entry("nieznane-api.gov.pl"))
    assert [f.reason for f in report.failures] == ["api_not_supported"]


def test_ingest_deps_carry_the_api_fetcher() -> None:
    deps = corpus.build_ingest_deps(
        CorpusSettings(provider=CorpusProvider.MEMORY),
        build_embeddings(EmbeddingsSettings()),
        CleanInjectionDetector(),
    )
    assert deps.api_fetcher is not None
