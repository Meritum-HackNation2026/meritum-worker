import asyncio

import pytest
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.pii import NullPiiGate

from meritum_worker import corpus
from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import FakeWebSearch, LiveSearchPorts, search_live
from meritum_worker.corpus.ingest_constants import INGEST_SKIPPED
from meritum_worker.security import CleanInjectionDetector

CATALOG = load_catalog()
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
