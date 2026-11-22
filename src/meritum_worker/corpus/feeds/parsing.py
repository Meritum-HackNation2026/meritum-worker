"""Parsing RSS 2.0, Atom and sitemaps into the pages they list, safely.

The XML is untrusted: defusedxml refuses entity expansion and external
references, and the listing is cut to ``MAX_PAGES_PER_ENTRY``.

Features:
    US-KOR-03, F-13
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from xml.etree.ElementTree import Element  # nosec B405  # ruff: ignore[suspicious-xml-etree-import]  # type only; defusedxml parses

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from meritum_core.checks.contracts import SourceVia

from meritum_worker.corpus.documents import DiscoveredPage
from meritum_worker.corpus.errors import FeedUnreadableError
from meritum_worker.corpus.feeds.constants import (
    ATOM_NS,
    MAX_CHILD_SITEMAPS,
    MAX_PAGES_PER_ENTRY,
    SITEMAP_NS,
)
from meritum_worker.corpus.feeds.nato import parse_nato_news


@dataclass(frozen=True)
class FeedListing:
    """What one feed or sitemap lists.

    Attributes:
        pages: Pages, newest first, at most ``MAX_PAGES_PER_ENTRY``.
        sitemaps: Child sitemaps of a sitemap index, newest first, at most
            ``MAX_CHILD_SITEMAPS``.

    Features:
        US-KOR-03, F-13
    """

    pages: tuple[DiscoveredPage, ...] = ()
    sitemaps: tuple[str, ...] = field(default=())


def parse_feed(xml: str) -> FeedListing:
    """Read an RSS 2.0 channel, an Atom feed, a sitemap or a sitemap index.

    JSON is NATO's news listing (``parse_nato_news``).

    Args:
        xml: The raw, untrusted XML or JSON.

    Returns:
        The listed pages or child sitemaps with their publication dates.

    Raises:
        FeedUnreadableError: Not well-formed XML, unsafe XML or an unknown kind.

    Features:
        US-KOR-03, F-13
    """
    if xml.lstrip().startswith(("{", "[")):
        return FeedListing(pages=parse_nato_news(xml))
    try:
        root = fromstring(xml.strip())
    except (ParseError, DefusedXmlException) as error:
        raise FeedUnreadableError from error
    match _local(root.tag):
        case "rss" | "RDF":
            items = [_rss_item(i) for i in root.iter("item")]
        case "feed":
            items = [_atom_entry(e) for e in root.iter(f"{ATOM_NS}entry")]
        case "urlset":
            items = [_located(u) for u in root.iter(f"{SITEMAP_NS}url")]
        case "sitemapindex":
            maps = _newest([_located(s) for s in root.iter(f"{SITEMAP_NS}sitemap")])
            return FeedListing(sitemaps=tuple(p.url for p in maps[:MAX_CHILD_SITEMAPS]))
        case _:
            raise FeedUnreadableError
    return FeedListing(pages=tuple(_newest(items)[:MAX_PAGES_PER_ENTRY]))


def _local(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _newest(pages: list[DiscoveredPage | None]) -> list[DiscoveredPage]:
    listed = [p for p in pages if p is not None]
    return sorted(listed, key=lambda p: p.published_on or date.min, reverse=True)


def _text(element: Element, tag: str) -> str:
    found = element.find(tag)
    return (found.text or "").strip() if found is not None else ""


def _page(
    url: str, published_on: date | None, via: SourceVia = "corpus"
) -> DiscoveredPage | None:
    if not url.startswith(("http://", "https://")):
        return None
    return DiscoveredPage(url=url, published_on=published_on, via=via)


def _rss_item(item: Element) -> DiscoveredPage | None:
    return _page(_text(item, "link"), _rfc822_date(_text(item, "pubDate")), "rss")


def _atom_entry(entry: Element) -> DiscoveredPage | None:
    links = entry.findall(f"{ATOM_NS}link")
    alternate = [link for link in links if link.get("rel", "alternate") == "alternate"]
    url = alternate[0].get("href", "").strip() if alternate else ""
    stamp = _text(entry, f"{ATOM_NS}published") or _text(entry, f"{ATOM_NS}updated")
    return _page(url, _iso_date(stamp), "rss")


def _located(element: Element) -> DiscoveredPage | None:
    loc = _text(element, f"{SITEMAP_NS}loc")
    return _page(loc, _iso_date(_text(element, f"{SITEMAP_NS}lastmod")))


def _rfc822_date(value: str) -> date | None:
    try:
        return parsedate_to_datetime(value).date() if value else None
    except TypeError, ValueError:
        return None


def _iso_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date() if value else None
    except ValueError:
        return None
