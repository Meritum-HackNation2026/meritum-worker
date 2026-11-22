"""Constants of RSS, Atom and sitemap discovery.

Features:
    US-KOR-03, F-13
"""

from typing import Final

FEED_URLS: Final = {
    "policja.pl": "https://policja.pl/dokumenty/rss/1-rss-1.rss",
    "cert.pl": "https://cert.pl/feed/",
    "kgsok.pl": "https://kgsok.pl/wp-sitemap.xml",
    "fakenews.pl": "https://fakenews.pl/feed/",
    "pravda.org.pl": "https://pravda.org.pl/rss/",
    "edmo.eu": "https://edmo.eu/sitemap_index.xml",
    "checkfirst.network": "https://checkfirst.network/feed/",
    "ec.europa.eu/commission/presscorner": (
        "https://ec.europa.eu/commission/presscorner/api/rss?language=pl"
    ),
    "www.nato.int": (
        "https://www.nato.int/content/nato/en/news-and-events/articles/news"
        "/jcr:content/root/container/general_search.search.json"
        "?searchType=wcm&sortBy=dateDesc&pageSize=50&page=1"
    ),
    "pkw.gov.pl": "https://pkw.gov.pl/sitemaps/sitemap_1.xml",
}
"""Feed or sitemap of a catalogue domain, from the catalogue section of core's README;
the catalogue contract has no field for it. NATO's ``sitemap.xml`` is 10 MB, past
core's 5 MB limit, and its smaller child sitemap lists only French pages, so NATO
is read from the JSON its English news page (``/en/news-and-events/articles/news``)
loads its list from; robots.txt allows it (checked 2026-11-22, worker#220)."""

FEED_HOST_FIXES: Final = {"pkw.gov.pl": {"baza57-loc.pl": "https://pkw.gov.pl"}}
"""Hosts a publisher's own sitemap names by mistake, per catalogue domain: PKW's
sitemap (from its robots.txt) lists every page on its internal host baza57-loc.pl,
and the same paths answer on pkw.gov.pl (checked 2026-11-22, worker#220)."""

WWW_PREFIX: Final = "www."
"""Host prefix ignored when a listed page is matched to its catalogue domain."""

DEFAULT_FEED_PATHS: Final = {"rss": "/feed/", "sitemap": "/sitemap.xml"}
"""Path of the feed of a domain missing from ``FEED_URLS``, per ``ingest`` method."""

FEED_METHODS: Final = frozenset(DEFAULT_FEED_PATHS)
"""Catalogue ``ingest`` values discovered through a feed or sitemap."""

MAX_PAGES_PER_ENTRY: Final = 50
"""Most pages one entry yields per run, newest first."""

MAX_CHILD_SITEMAPS: Final = 5
"""Most child sitemaps of a sitemap index read per run, newest first."""

FEED_MEDIA_TYPES: Final = frozenset(
    {
        "application/rss+xml",
        "application/atom+xml",
        "application/xml",
        "text/xml",
        "application/json",
    }
)
"""Media types of feeds, sitemaps and NATO's JSON news listing, handed to core's
fetcher as plain text."""

NATO_ORIGIN: Final = "https://www.nato.int"
"""What the relative links of NATO's news listing are resolved against."""

NATO_DATE_FORMAT: Final = "%d %B %Y"
"""Date of an article in NATO's news listing (``19 November 2026``)."""

LISTING_MEDIA_TYPES: Final = FEED_MEDIA_TYPES | {"text/html"}
"""Media types the discovery fetcher hands over as plain text: feeds, sitemaps and
the HTML news listings of gov.pl sections, whose links are read from the markup."""

GOVPL_SECTION_PREFIX: Final = "www.gov.pl/web/"
"""Domain prefix of a gov.pl section entry (``www.gov.pl/web/mswia``)."""

GOVPL_LISTING_PATH: Final = "/aktualnosci"
"""Path of a gov.pl section's news listing, relative to the section: static HTML
with its 10 newest articles. gov.pl has no RSS, no sitemap and no Content-Signal;
its robots.txt allows everything (checked 2026-11-22, worker#232)."""

GOVPL_LISTING_URLS: Final = {
    "www.gov.pl/web/obrona-narodowa": (
        "https://www.gov.pl/web/obrona-narodowa/aktualnosci5"
    ),
}
"""News listings of gov.pl sections outside ``GOVPL_LISTING_PATH``: MON's
``/aktualnosci`` lists the premier's articles, its own news is ``/aktualnosci5``."""

GOVPL_DATE_FORMAT: Final = "%d.%m.%Y"
"""Date of an article tile on a gov.pl listing (``16.11.2026``)."""

GOVPL_DATE_CLASS: Final = "date"
"""Class of the ``span`` holding an article tile's date on a gov.pl listing."""

GOVPL_TITLE_CLASS: Final = "title"
"""Class of the ``div`` holding an article tile's link on a gov.pl listing."""

FEED_AS_MEDIA_TYPE: Final = "text/plain"
"""What a feed's media type becomes, so core's fetcher returns the raw XML."""

TRACKING_PARAM_PREFIX: Final = "utm_"
"""Query parameters with this prefix are dropped from a canonical URL."""

FEED_UNREADABLE: Final = "feed_unreadable"
"""Failure reason of a feed or sitemap that is not well-formed XML of a known kind."""

ATOM_NS: Final = "{http://www.w3.org/2005/Atom}"
"""XML namespace of Atom elements."""

SITEMAP_NS: Final = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
"""XML namespace of sitemap elements."""
