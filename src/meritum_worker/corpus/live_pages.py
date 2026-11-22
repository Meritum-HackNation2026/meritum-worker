"""Pages found by live web search, handed to the corpus for the next snapshot.

A page that passed quarantine in a check is stored like a catalogue page: the
snapshot the check searched stays as it is and the next one takes the page in
(ADR-21). Only a worker whose role may write ``corpus`` is given this port.

Features:
    US-KOR-04, US-KOR-05, F-12, F-13, ADR-19, ADR-21
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import catalog_entry_for
from meritum_core.shared.embeddings import EmbeddingsUnavailableError

from meritum_worker.corpus.constants import EMBEDDINGS_UNAVAILABLE
from meritum_worker.corpus.documents import DiscoveredPage, IngestReport
from meritum_worker.corpus.pages import failed_page, store_page
from meritum_worker.corpus.ports import IngestDeps


@runtime_checkable
class LivePagesPort(Protocol):
    """Takes pages found by live search into the corpus for the next snapshot.

    Features:
        US-KOR-04, US-KOR-05, F-12, F-13, ADR-21
    """

    async def enqueue(self, pages: Sequence[FetchedPage]) -> IngestReport:
        """Store pages that passed quarantine; the current snapshot stays as it is.

        Args:
            pages: Pages past the injection scan of a check.

        Returns:
            What was stored and what failed.
        """
        ...


class CorpusLivePages:
    """``LivePagesPort`` that stores the pages with the catalogue ingestion's ports.

    Args:
        deps: The ingestion ports; ``injection``, ``embeddings`` and ``store`` are used.
        catalog: The loaded catalogue; gives each page its publisher and licence.
        clock: The time a page's ``fetched_at`` is set to.

    Features:
        US-KOR-04, US-KOR-05, F-12, F-13, ADR-21
    """

    def __init__(
        self,
        deps: IngestDeps,
        catalog: Sequence[CatalogEntry],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._deps = deps
        self._catalog = catalog
        self._clock = clock

    async def enqueue(self, pages: Sequence[FetchedPage]) -> IngestReport:
        """Store each page; it joins the next snapshot, never the current one.

        A page outside the catalogue is skipped. One that is excluded, reserves
        text and data mining, holds an instruction or cannot be embedded is
        reported as a failure; the next page follows.

        Args:
            pages: Pages that passed quarantine in a check.

        Returns:
            The summed report.

        Features:
            US-KOR-04, US-KOR-05, F-12, F-13, ADR-21
        """
        report = IngestReport()
        now = self._clock()
        for page in pages:
            entry = catalog_entry_for(page.url, self._catalog)
            if entry is None:
                continue
            try:
                found = DiscoveredPage(url=page.url, via="web_search")
                report += await store_page(
                    page, entry, self._deps, now=now, found=found
                )
            except EmbeddingsUnavailableError:
                report += failed_page(entry, page.url, EMBEDDINGS_UNAVAILABLE)
        return report
