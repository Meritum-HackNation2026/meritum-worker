"""Feed URLs of catalogue entries and canonical page URLs.

Features:
    US-KOR-03, F-13
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.feeds.constants import (
    DEFAULT_FEED_PATHS,
    FEED_URLS,
    TRACKING_PARAM_PREFIX,
)


def feed_url(entry: CatalogEntry) -> str:
    """Return the RSS feed or sitemap of an entry with ``ingest`` rss or sitemap.

    Args:
        entry: The catalogue entry.

    Returns:
        The URL from ``FEED_URLS``, else ``https://<domain>`` with the default path.

    Features:
        US-KOR-03, F-13
    """
    known = FEED_URLS.get(entry.domain)
    if known is not None:
        return known
    path = DEFAULT_FEED_PATHS.get(entry.ingest, "")
    return f"https://{entry.domain.rstrip('/')}{path}"


def canonical_url(url: str) -> str:
    """Normalise a page URL so one page is stored once.

    Args:
        url: An absolute URL from a feed.

    Returns:
        The URL with a lower-case scheme and host, without the fragment and
        without ``utm_*`` parameters.

    Features:
        US-KOR-03, F-13
    """
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PARAM_PREFIX)
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )
