"""News listings of gov.pl sections: the articles a section's "Aktualności" page lists.

gov.pl publishes no RSS and no sitemap, so a section entry
(``www.gov.pl/web/<section>``) would give only its entry page. Its news listing
is static HTML: each article tile has a ``span.date`` and a ``div.title`` link.

Features:
    US-KOR-03, F-13
"""

from datetime import date, datetime
from html.parser import HTMLParser
from typing import override
from urllib.parse import urljoin

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.documents import DiscoveredPage
from meritum_worker.corpus.feeds.constants import (
    GOVPL_DATE_CLASS,
    GOVPL_DATE_FORMAT,
    GOVPL_LISTING_PATH,
    GOVPL_LISTING_URLS,
    GOVPL_SECTION_PREFIX,
    GOVPL_TITLE_CLASS,
    MAX_PAGES_PER_ENTRY,
)


def govpl_listing_url(entry: CatalogEntry) -> str | None:
    """Return the news listing of a gov.pl section entry.

    Args:
        entry: A catalogue entry.

    Returns:
        ``GOVPL_LISTING_URLS`` or ``https://<domain>/aktualnosci`` for a whole
        section (``www.gov.pl/web/<section>``); None for any other entry,
        including a page inside a section (``www.gov.pl/web/gov/ostrzezenia``),
        whose section's news lies outside the entry's path.

    Features:
        US-KOR-03, F-13
    """
    section = entry.domain.removeprefix(GOVPL_SECTION_PREFIX)
    if section == entry.domain or not section or "/" in section.strip("/"):
        return None
    known = GOVPL_LISTING_URLS.get(entry.domain)
    return known or f"https://{entry.domain.rstrip('/')}{GOVPL_LISTING_PATH}"


def parse_govpl_listing(html: str, url: str) -> tuple[DiscoveredPage, ...]:
    """Read the article tiles of a gov.pl news listing.

    Args:
        html: The listing's raw, untrusted HTML.
        url: The listing's address; relative links resolve against it.

    Returns:
        Each linked article once, in listing order (newest first), with the
        tile's date when it has a valid one; at most ``MAX_PAGES_PER_ENTRY``.

    Features:
        US-KOR-03, F-13
    """
    parser = _TileParser()
    parser.feed(html)
    parser.close()
    pages: dict[str, DiscoveredPage] = {}
    for href, stamp in parser.tiles:
        link = urljoin(url, href)
        if link.startswith(("http://", "https://")) and link not in pages:
            pages[link] = DiscoveredPage(url=link, published_on=_date(stamp))
    return tuple(pages.values())[:MAX_PAGES_PER_ENTRY]


def _date(stamp: str) -> date | None:
    try:
        return datetime.strptime(stamp.strip(), GOVPL_DATE_FORMAT).date()  # ruff: ignore[call-datetime-strptime-without-zone]  # a calendar date, no time
    except ValueError:
        return None


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set((dict(attrs).get("class") or "").split())


class _TileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tiles: list[tuple[str, str]] = []
        self._date: list[str] | None = None
        self._last_date = ""
        self._in_title = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "span" and GOVPL_DATE_CLASS in _classes(attrs):
            self._date = []
        elif tag == "div" and GOVPL_TITLE_CLASS in _classes(attrs):
            self._in_title = True
        elif tag == "a" and self._in_title:
            href = (dict(attrs).get("href") or "").strip()
            if href:
                self.tiles.append((href, self._last_date))
            self._in_title = False
            self._last_date = ""

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._date is not None:
            self._last_date = "".join(self._date)
            self._date = None

    @override
    def handle_data(self, data: str) -> None:
        if self._date is not None:
            self._date.append(data)
