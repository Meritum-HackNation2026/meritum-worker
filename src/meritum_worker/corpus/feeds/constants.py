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
    "www.nato.int": "https://www.nato.int/sitemap.xml",
    "pkw.gov.pl": "https://pkw.gov.pl/sitemaps/sitemap_1.xml",
}
"""Feed or sitemap of a catalogue domain, from the catalogue section of core's README;
the catalogue contract has no field for it."""

DEFAULT_FEED_PATHS: Final = {"rss": "/feed/", "sitemap": "/sitemap.xml"}
"""Path of the feed of a domain missing from ``FEED_URLS``, per ``ingest`` method."""

FEED_METHODS: Final = frozenset(DEFAULT_FEED_PATHS)
"""Catalogue ``ingest`` values discovered through a feed or sitemap."""

MAX_PAGES_PER_ENTRY: Final = 50
"""Most pages one entry yields per run, newest first."""

MAX_CHILD_SITEMAPS: Final = 5
"""Most child sitemaps of a sitemap index read per run, newest first."""

FEED_MEDIA_TYPES: Final = frozenset(
    {"application/rss+xml", "application/atom+xml", "application/xml", "text/xml"}
)
"""Media types of feeds and sitemaps, handed to core's fetcher as plain text."""

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
