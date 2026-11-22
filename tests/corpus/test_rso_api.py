import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

from meritum_core.corpus.catalog import load_catalog
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.catalog_api import api_listings, parse_listing
from meritum_worker.corpus.fakes import FakeCatalogSite, FakePublicApi
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "api"
RCB = "www.gov.pl/web/gov/ostrzezenia"
RSO = "www.gov.pl/web/mswia/regionalny-system-ostrzegania"
PROXY = (
    "https://www.gov.pl/api/data/proxy/rso/komunikatyxml/wszystkie/{}/0?_format=json"
)
RCB_CATEGORIES = ("meteorologiczne", "hydrologiczne", "informacje-drogowe", "ogolne")
DETAIL = "https://www.gov.pl/web/gov/ostrzezenia#/_/szczgoly/{}"
CATALOG = {e.domain: e for e in load_catalog()}


def recorded(category: str) -> str:
    return (FIXTURES / f"rso-{category}.json").read_text(encoding="utf-8")


def recorded_api() -> FakePublicApi:
    api = FakePublicApi()
    for category in (*RCB_CATEGORIES, "atak-z-powietrza"):
        api.answer(PROXY.format(category), recorded(category))
    return api


def test_rcb_entry_reads_the_categories_of_the_govpl_warnings_page() -> None:
    listings = api_listings(CATALOG[RCB], NOW)
    assert [listing.url for listing in listings] == [
        PROXY.format(category) for category in RCB_CATEGORIES
    ]


def test_rso_entry_reads_air_attack_communiques_the_warnings_page_leaves_out() -> None:
    (listing,) = api_listings(CATALOG[RSO], NOW)
    assert listing.url == PROXY.format("atak-z-powietrza")
    assert parse_listing(listing, recorded("atak-z-powietrza")) == []


def test_alert_rcb_becomes_a_dated_communique_with_region_and_text() -> None:
    ogolne = api_listings(CATALOG[RCB], NOW)[3]
    alert, _ = parse_listing(ogolne, recorded("ogolne"))
    assert alert.url == DETAIL.format(23521833)
    assert alert.published_at == date(2026, 11, 19)
    assert alert.text.startswith("Alert RCB\n\nKomunikat RSO, kategoria: Ogólne.")
    assert "Województwa: dolnośląskie." in alert.text
    assert "Ważny od 2026-11-19 17:06 do 2026-11-22 23:59." in alert.text
    assert "wysłano Alert RCB o treści" in alert.text


def test_each_category_names_itself_and_its_regions() -> None:
    meteo = api_listings(CATALOG[RCB], NOW)[0]
    storm, drought = parse_listing(meteo, recorded("meteorologiczne"))
    assert "kategoria: Meteorologiczne." in storm.text
    assert "Województwa: Pomorskie." in storm.text
    assert "Województwa: małopolskie." in drought.text
    assert drought.published_at == date(2026, 11, 5)


def test_both_entries_are_ingested_through_the_api_with_catalogue_metadata() -> None:
    planned = {e.domain for e in corpus.ingestible(CATALOG.values())}
    assert {RCB, RSO} <= planned
    api = recorded_api()
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
    entries = [CATALOG[RCB], CATALOG[RSO]]
    report = asyncio.run(corpus.ingest_catalog(entries, deps, now=NOW))
    documents = asyncio.run(store.documents())
    assert not report.failures
    assert report.added == len(documents) == 6
    assert {(d.domain, d.publisher_id) for d in documents} == {(RCB, "rcb")}
    assert all(d.url.startswith(DETAIL.format("")) for d in documents)
    assert "https://www.gov.pl/robots.txt" in api.requested
