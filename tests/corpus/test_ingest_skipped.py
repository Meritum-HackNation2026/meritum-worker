import asyncio

import pytest
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.pii import NullPiiGate

from meritum_worker import corpus
from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import FakeWebSearch, LiveSearchPorts, search_live
from meritum_worker.corpus.fakes import FakeFeedServer
from meritum_worker.corpus.ingest_constants import INGEST_SKIPPED, SKIPPED_PAGES
from meritum_worker.security import CleanInjectionDetector

CATALOG = load_catalog()


def urlset(*locs: str) -> str:
    urls = "".join(f"<url><loc>{loc}</loc></url>" for loc in locs)
    return (
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    )


SKIPPED = {
    "ulc.gov.pl": "https://ulc.gov.pl/prawa-pasazera",
    "www.sar.gov.pl": "https://www.sar.gov.pl/ratownictwo",
    "eur-lex.europa.eu": "https://eur-lex.europa.eu/eli/reg/2004/261/oj",
    "odyseusz.gov.pl": "https://odyseusz.gov.pl/rejestracja",
}


def test_entries_blocked_for_robots_are_left_out_of_the_ingestion() -> None:
    planned = {e.domain for e in corpus.ingestible(CATALOG)}
    assert set(SKIPPED) <= {e.domain for e in CATALOG}
    assert planned.isdisjoint(SKIPPED)
    assert set(INGEST_SKIPPED) == set(SKIPPED)
    assert all(INGEST_SKIPPED.values())


@pytest.mark.parametrize(("domain", "url"), SKIPPED.items())
def test_live_search_still_cites_an_entry_left_out_of_the_ingestion(
    domain: str, url: str
) -> None:
    entry = next(e for e in CATALOG if e.domain == domain)
    page = FetchedPage(url=url, content_type="text/html", untrusted_text="Treść.")
    candidate = WebSearchCandidate(
        url=url, domain=domain, publisher_id=entry.publisher_id
    )
    ports = LiveSearchPorts(
        web_search=FakeWebSearch((candidate,)),
        pages=FakePageFetcher(page),
        injection=CleanInjectionDetector(),
        pii=NullPiiGate(),
        catalog=CATALOG,
    )
    found = asyncio.run(search_live(("zapytanie",), ports))
    (document,) = found.documents
    assert document.source.domain == domain


def test_pkw_election_results_pages_are_skipped_and_its_news_kept() -> None:
    pkw = next(e for e in CATALOG if e.domain == "pkw.gov.pl")
    kept = "https://pkw.gov.pl/aktualnosci/informacje/komunikat-o-wyborach"
    results = (
        "https://pkw.gov.pl/wybory-i-referenda/referenda-ogolnokrajowe/referendum-2015/wyniki-glosowania",
        "https://pkw.gov.pl/wybory-i-referenda/wybory-samorzadowe/wybory-2014/wyniki-wyborow",
        "https://pkw.gov.pl/wybory-i-referenda/senat/okreg-nr-59/wizualizacja-wynikow",
    )
    server = FakeFeedServer()
    server.serve(
        "https://pkw.gov.pl/sitemaps/sitemap_1.xml",
        urlset(kept, *results),
        "text/xml; charset=utf-8",
    )
    found = asyncio.run(server.discovery().pages(pkw))
    assert [p.url for p in found] == [kept]
    assert "pkw.gov.pl" in SKIPPED_PAGES
