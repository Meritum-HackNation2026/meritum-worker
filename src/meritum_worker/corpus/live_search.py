"""Live web search for a check: catalogue addresses, fetched, then held in quarantine.

A search gives addresses only. Each one is fetched by the SSRF-safe fetcher,
which honours robots.txt and Content-Signal for sources, and becomes evidence
only after the injection detector finds no instruction in it (ADR-07, ADR-12).
The page never joins the shared corpus during the check: the result hands it on
and ``LivePagesPort`` adds it to the next snapshot (worker#90).

Features:
    US-KOR-04, US-SPR-04, US-WTY-03, F-13, ADR-07, ADR-12
"""

import asyncio
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, time

from meritum_core.checks import InjectionEvent
from meritum_core.checks.contracts import CatalogEntry, Source, kind_for
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchPurpose,
    PageFetcherPort,
    PageFetchError,
)
from meritum_core.corpus.web_search import (
    WebSearchCandidate,
    WebSearchPort,
    catalog_entry_for,
)
from meritum_core.evidence.models import SourceDocument
from meritum_core.security.injection import InjectionDetectorPort
from meritum_core.security.pii import PiiGatePort, mask_personal_data
from meritum_core.shared.llm import ProviderUnavailableError
from pydantic import BaseModel, ConfigDict

from meritum_worker.corpus.constants import (
    INJECTION_EXCERPT_MAX_CHARS,
    MAX_PAGE_TEXT_CHARS,
    MAX_PARALLEL_CLAIMS,
    WEB_QUERIES_PER_CHECK,
    WEB_RESULTS_PER_QUERY,
    WEB_SEARCH_TIMEOUT,
    WEB_SOURCE_ID_HASH_CHARS,
    WEB_SOURCE_ID_PREFIX,
    WEB_TITLE_MAX_CHARS,
)
from meritum_worker.corpus.language import detect_language

_log = logging.getLogger(__name__)


class LiveSearchResult(BaseModel):
    """What live search found for one check.

    Attributes:
        calls: how many web searches were sent.
        documents: pages that passed quarantine, as evidence with their text.
        pages: the same pages as fetched, for the corpus to take in (worker#90).
        dropped: one ``source_dropped`` event per page that held an instruction.

    Features:
        US-KOR-04, US-SPR-04, F-13
    """

    model_config = ConfigDict(frozen=True)

    calls: int
    documents: list[SourceDocument]
    pages: list[FetchedPage]
    dropped: list[InjectionEvent]


@dataclass(frozen=True, slots=True)
class LiveSearchPorts:
    """The ports live search calls; built from the check's deps.

    Attributes:
        web_search: the port, already limited to catalogue domains.
        pages: the SSRF-safe fetcher.
        injection: the detector every page is scanned with.
        pii: the masking gate every query goes through before it leaves.
        catalog: the loaded catalogue, for the publisher shown with the page.

    Features:
        US-KOR-04, US-SPR-04, F-13
    """

    web_search: WebSearchPort
    pages: PageFetcherPort
    injection: InjectionDetectorPort
    pii: PiiGatePort
    catalog: tuple[CatalogEntry, ...]


async def search_live(
    queries: Sequence[str], ports: LiveSearchPorts
) -> LiveSearchResult:
    """Mask and search each query, then fetch and scan every catalogue page.

    At most ``WEB_QUERIES_PER_CHECK`` queries are masked and searched,
    ``MAX_PARALLEL_CLAIMS`` at a time. One deadline, ``WEB_SEARCH_TIMEOUT``
    from the call, covers the masking, the searches, the fetches and the
    scans. Our catalogue filter checks every address before the fetch and the
    final one after redirects. A page that cannot be fetched (robots.txt,
    Content-Signal, network), is empty, could not be scanned or is not scanned
    by the deadline is left out with a log line; the check goes on.

    Args:
        queries: the checked facts, as extracted from the masked input.
        ports: web search, fetcher, detector, masking gate and catalogue.

    Returns:
        The evidence and the dropped pages.

    Masking and searches not done by the deadline raise TimeoutError and a web
    search failure propagates; the workflow maps both to technical_failure.

    Features:
        US-KOR-04, US-SPR-04, US-WTY-03, F-13, ADR-07, ADR-12
    """
    asked = queries[:WEB_QUERIES_PER_CHECK]
    deadline = asyncio.get_running_loop().time() + WEB_SEARCH_TIMEOUT.total_seconds()
    async with asyncio.timeout_at(deadline):
        slots = asyncio.Semaphore(MAX_PARALLEL_CLAIMS)
        found = await asyncio.gather(*(_ask(query, ports, slots) for query in asked))
    urls = [c.url for candidates in found for c in candidates]
    return await _admitted(urls, ports, deadline, calls=len(asked))


async def admit_pages(urls: Sequence[str], ports: LiveSearchPorts) -> LiveSearchResult:
    """Fetch and scan fact-check articles the catalogue allows, like search results.

    An address outside the catalogue or on an excluded domain (Demagog, AFP
    Sprawdzam) is never fetched; the rest follows ``search_live``: the
    SSRF-safe fetcher, robots.txt, Content-Signal, quarantine, one deadline
    of ``WEB_SEARCH_TIMEOUT``.

    Args:
        urls: Links of fact-checks the rating pointed to.
        ports: The fetcher, detector and catalogue.

    Returns:
        The pages that passed quarantine and the dropped ones; ``calls`` is 0.

    Features:
        US-KOR-01, US-KOR-04, F-13, F-14, ADR-07, ADR-12, ADR-34
    """
    deadline = asyncio.get_running_loop().time() + WEB_SEARCH_TIMEOUT.total_seconds()
    return await _admitted(urls, ports, deadline, calls=0)


async def _admitted(
    urls: Sequence[str], ports: LiveSearchPorts, deadline: float, *, calls: int
) -> LiveSearchResult:
    quarantine = _Quarantine(ports, deadline)
    scanned = await asyncio.gather(*map(quarantine.admit, dict.fromkeys(urls)))
    # Two results may redirect to one page: it is one document, kept once.
    documents = {s.source.id: s for s in scanned if isinstance(s, SourceDocument)}
    return LiveSearchResult(
        calls=calls,
        documents=list(documents.values()),
        pages=[quarantine.passed[source_id] for source_id in documents],
        dropped=[s for s in scanned if isinstance(s, InjectionEvent)],
    )


async def _ask(
    query: str, ports: LiveSearchPorts, slots: asyncio.Semaphore
) -> list[WebSearchCandidate]:
    async with slots:
        masked = await mask_personal_data(query, ports.pii)
        return await ports.web_search.search(masked, limit=WEB_RESULTS_PER_QUERY)


@dataclass(frozen=True, slots=True)
class _Quarantine:
    ports: LiveSearchPorts
    deadline: float
    passed: dict[str, FetchedPage] = field(default_factory=dict)

    async def admit(self, url: str) -> SourceDocument | InjectionEvent | None:
        # Fail closed: a page not scanned in time, or at all, is never evidence.
        try:
            async with asyncio.timeout_at(self.deadline):
                return await self._scanned(url)
        except (TimeoutError, PageFetchError, ProviderUnavailableError) as error:
            # The address and the reason only: page text never reaches the log.
            _log.info("live search page dropped: %s (%s)", url, type(error).__name__)
            return None

    async def _scanned(self, url: str) -> SourceDocument | InjectionEvent | None:
        if catalog_entry_for(url, self.ports.catalog) is None:
            return None
        page = await self.ports.pages.fetch(url, purpose=FetchPurpose.SOURCE)
        # A redirect may leave the catalogue: the final address is checked again.
        entry = catalog_entry_for(page.url, self.ports.catalog)
        text = page.untrusted_text[:MAX_PAGE_TEXT_CHARS]
        if entry is None or not text.strip():
            return None
        scan = await self.ports.injection.scan(text)
        if not scan.detected:
            source = _source(page, entry, text)
            self.passed[source.id] = page
            return SourceDocument(source=source, text=text)
        first = scan.spans[0]
        return InjectionEvent(
            location="source",
            action="source_dropped",
            source_url=page.url,
            excerpt=text[first.start : first.end][:INJECTION_EXCERPT_MAX_CHARS],
        )


def _source(page: FetchedPage, entry: CatalogEntry, text: str) -> Source:
    digest = hashlib.sha256(page.url.encode()).hexdigest()[:WEB_SOURCE_ID_HASH_CHARS]
    published = page.published_at
    return Source(
        id=f"{WEB_SOURCE_ID_PREFIX}{digest}",
        # The fetcher gives no title; the address names the page until ingestion does.
        title=page.url[:WEB_TITLE_MAX_CHARS],
        publisher=entry.publisher,
        publisher_id=entry.publisher_id,
        url=page.url,
        domain=entry.domain,
        kind=kind_for(entry, page.url),
        tier=entry.tier,
        published_at=None
        if published is None
        else datetime.combine(published, time(), UTC),
        fetched_at=datetime.now(UTC),
        via="web_search",
        language=detect_language(text),
    )
