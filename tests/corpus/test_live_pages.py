import asyncio
from datetime import UTC, datetime

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.injection import (
    DetectionLayer,
    InjectionScan,
    InjectionSpan,
)
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.fakes import FakeCatalogSite
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 20, 10, 40, tzinfo=UTC)
SCHEDULED = datetime(2026, 11, 20, 11, 0, tzinfo=UTC)
RCB = "https://www.gov.pl/web/rcb/ostrzezenie"


class _Flagging:
    @staticmethod
    async def scan(text: str) -> InjectionScan:
        return InjectionScan(
            text=text,
            spans=(InjectionSpan(start=0, end=1, layer=DetectionLayer.PATTERNS),),
        )


def _page(url: str = RCB, **fields: object) -> FetchedPage:
    return FetchedPage.model_validate(
        {
            "url": url,
            "content_type": "text/html",
            "untrusted_text": "RCB ostrzega przed burzami.",
            **fields,
        }
    )


def _queue(
    store: MemoryCorpusWriter,
    catalog: tuple[CatalogEntry, ...] | None = None,
    injection: object | None = None,
) -> corpus.CorpusLivePages:
    site = FakeCatalogSite(pages_per_domain=1)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=injection or CleanInjectionDetector(),  # ty: ignore[invalid-argument-type]
    )
    return corpus.CorpusLivePages(deps, catalog or load_catalog(), clock=lambda: NOW)


def test_page_is_stored_for_the_next_snapshot_not_the_current_one() -> None:
    store = MemoryCorpusWriter()
    current = asyncio.run(corpus.take_snapshot(store, scheduled=NOW))
    report = asyncio.run(_queue(store).enqueue([_page()]))
    assert report.added == 1
    assert asyncio.run(store.snapshot(current.version)) == current
    following = asyncio.run(corpus.take_snapshot(store, scheduled=SCHEDULED))
    (entry,) = following.manifest
    assert entry.fetched_at == NOW


def test_page_from_live_search_is_stored_as_found_by_web_search() -> None:
    store = MemoryCorpusWriter()
    asyncio.run(_queue(store).enqueue([_page()]))
    (document,) = asyncio.run(store.documents())
    assert document.via == "web_search"


def test_page_outside_the_catalogue_is_not_stored() -> None:
    store = MemoryCorpusWriter()
    report = asyncio.run(_queue(store).enqueue([_page("https://example.com/x")]))
    assert report.added == 0
    assert asyncio.run(store.documents()) == []


def test_tdm_reserved_page_is_not_stored() -> None:
    store = MemoryCorpusWriter()
    report = asyncio.run(_queue(store).enqueue([_page(tdm_reserved=True)]))
    assert [f.reason for f in report.failures] == ["tdm_reserved"]
    assert asyncio.run(store.documents()) == []


def test_page_with_an_instruction_is_not_stored() -> None:
    store = MemoryCorpusWriter()
    report = asyncio.run(_queue(store, injection=_Flagging()).enqueue([_page()]))
    assert [f.reason for f in report.failures] == ["injection_found"]
    assert asyncio.run(store.documents()) == []


def test_search_result_hands_on_the_pages_that_passed_quarantine() -> None:
    page = _page()
    ports = corpus.LiveSearchPorts(
        web_search=corpus.FakeWebSearch(
            (
                WebSearchCandidate(
                    url=RCB, domain="www.gov.pl/web/rcb", publisher_id="rcb"
                ),
            )
        ),
        pages=FakePageFetcher(page),
        injection=CleanInjectionDetector(),
        pii=NullPiiGate(),
        catalog=load_catalog(),
    )
    found = asyncio.run(corpus.search_live(["RCB ostrzega"], ports))
    assert found.pages == [page]
