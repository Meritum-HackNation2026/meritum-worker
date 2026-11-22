"""Discovery through RSS, Atom and sitemaps for entries with ``ingest`` rss or sitemap.

Features:
    US-KOR-03, F-13
"""

import logging

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchPurpose, PageFetcherPort, PageFetchError

from meritum_worker.corpus.adapters._entry_pages import EntryPageDiscovery
from meritum_worker.corpus.documents import DiscoveredPage
from meritum_worker.corpus.errors import DiscoveryError, FeedUnreadableError
from meritum_worker.corpus.feeds import (
    FEED_METHODS,
    FEED_UNREADABLE,
    FeedListing,
    feed_url,
    on_entry_site,
    parse_feed,
)

_log = logging.getLogger(__name__)


class FeedDiscovery:
    """DocumentDiscoveryPort that reads each entry's feed or sitemap.

    Static entries keep their entry page. Feeds go through core's fetcher with
    ``purpose=SOURCE``, so robots.txt, Content-Signal and the SSRF guard apply.

    Args:
        fetcher: Core's fetcher on ``FeedTransport``, which reads XML as text.

    Features:
        US-KOR-03, F-13
    """

    def __init__(self, fetcher: PageFetcherPort) -> None:
        self._fetcher = fetcher
        self._entry_pages = EntryPageDiscovery()

    async def pages(self, entry: CatalogEntry) -> list[DiscoveredPage]:
        """Return the pages the feed lists (see ``DocumentDiscoveryPort.pages``).

        Args:
            entry: The catalogue entry.

        Returns:
            The listed pages of the entry's own site, newest first; a sitemap
            index adds its children's.

        Raises:
            DiscoveryError: The feed or sitemap failed; a failed child of a
                sitemap index is skipped instead.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by _read
        if entry.ingest not in FEED_METHODS:
            return await self._entry_pages.pages(entry)
        listing = await self._read(feed_url(entry))
        pages = list(listing.pages)
        for child in listing.sitemaps:
            pages += await self._child_pages(entry, child)
        return [
            page.model_copy(update={"url": url})
            for page in pages
            if (url := on_entry_site(entry, page.url)) is not None
        ]

    async def _child_pages(
        self, entry: CatalogEntry, url: str
    ) -> tuple[DiscoveredPage, ...]:
        # One child sitemap past the size limit (NATO's is 10 MB) or down must not
        # cost the entry the pages of its other children.
        try:
            return (await self._read(url)).pages
        except DiscoveryError as error:
            _log.warning(
                "sitemap %s of %s skipped: %s", url, entry.domain, error.reason
            )
            return ()

    async def _read(self, url: str) -> FeedListing:
        try:
            page = await self._fetcher.fetch(url, purpose=FetchPurpose.SOURCE)
            return parse_feed(page.untrusted_text)
        except PageFetchError as error:
            raise DiscoveryError(url, error.reason.value) from error
        except FeedUnreadableError as error:
            raise DiscoveryError(url, FEED_UNREADABLE) from error
