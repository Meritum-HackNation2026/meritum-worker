"""Discovery through RSS, Atom and sitemaps, and the news listings of gov.pl sections.

Features:
    US-KOR-03, F-13
"""

import logging
import re
from collections.abc import Iterable
from urllib.parse import urlsplit

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
    govpl_listing_url,
    on_entry_site,
    parse_feed,
    parse_govpl_listing,
)
from meritum_worker.corpus.ingest_constants import SKIPPED_PAGES

_log = logging.getLogger(__name__)


class FeedDiscovery:
    """DocumentDiscoveryPort that reads each entry's feed or sitemap.

    Static entries keep their entry page; a gov.pl section adds the articles its
    news listing names. Feeds and listings go through core's fetcher with
    ``purpose=SOURCE``, so robots.txt, Content-Signal and the SSRF guard apply.

    Args:
        fetcher: Core's fetcher on ``FeedTransport``, which reads XML and HTML
            as text.

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
            The listed pages of the entry's own site, newest first, less those
            in ``SKIPPED_PAGES``; a sitemap index adds its children's. A static
            entry gives its entry page, followed by the articles of a gov.pl
            section's news listing.

        Raises:
            DiscoveryError: The feed, sitemap or news listing failed; a failed
                child of a sitemap index is skipped instead.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by _read and _fetch
        if entry.ingest not in FEED_METHODS:
            return await self._static_pages(entry)
        listing = await self._read(feed_url(entry))
        pages = list(listing.pages)
        for child in listing.sitemaps:
            pages += await self._child_pages(entry, child)
        return _on_entry_site(entry, pages)

    async def _static_pages(self, entry: CatalogEntry) -> list[DiscoveredPage]:
        pages = await self._entry_pages.pages(entry)
        listing = govpl_listing_url(entry)
        if listing is None:
            return pages
        articles = parse_govpl_listing(await self._fetch(listing), listing)
        return pages + _on_entry_site(entry, articles)

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
            return parse_feed(await self._fetch(url))
        except FeedUnreadableError as error:
            raise DiscoveryError(url, FEED_UNREADABLE) from error

    async def _fetch(self, url: str) -> str:
        try:
            page = await self._fetcher.fetch(url, purpose=FetchPurpose.SOURCE)
        except PageFetchError as error:
            raise DiscoveryError(url, error.reason.value) from error
        return page.untrusted_text


def _on_entry_site(
    entry: CatalogEntry, pages: Iterable[DiscoveredPage]
) -> list[DiscoveredPage]:
    skipped = SKIPPED_PAGES.get(entry.domain, r"(?!)")  # (?!) matches nothing
    return [
        page.model_copy(update={"url": url})
        for page in pages
        if (url := on_entry_site(entry, page.url)) is not None
        and re.search(skipped, urlsplit(url).path) is None
    ]
