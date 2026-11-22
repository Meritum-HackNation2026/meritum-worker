"""Feed URLs of catalogue entries and canonical page URLs.

Features:
    US-KOR-03, F-13
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.feeds.constants import (
    DEFAULT_FEED_PATHS,
    FEED_HOST_FIXES,
    FEED_URLS,
    TRACKING_PARAM_PREFIX,
    WWW_PREFIX,
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


def on_entry_site(entry: CatalogEntry, url: str) -> str | None:
    """Keep a page a feed lists only when it belongs to the entry.

    A feed or sitemap may name pages of other sites; they would be stored under
    this entry's publisher, so they are dropped. A host the publisher's own
    sitemap names by mistake (``FEED_HOST_FIXES``) is replaced first.

    Args:
        entry: The catalogue entry whose feed listed the page.
        url: The listed page.

    Returns:
        The URL, its host fixed, when its host is the entry's (``www.`` aside)
        and its path lies under the entry's path; otherwise None.

    Features:
        US-KOR-03, F-13
    """
    parts = urlsplit(url.strip())
    fixed = FEED_HOST_FIXES.get(entry.domain, {}).get(parts.netloc.lower())
    if fixed is not None:
        base = urlsplit(fixed)
        parts = parts._replace(scheme=base.scheme, netloc=base.netloc)
    host, _, path = entry.domain.partition("/")
    prefix = f"/{path.strip('/')}" if path else ""
    in_path = parts.path == prefix or parts.path.startswith(f"{prefix}/")
    same_host = _bare(parts.netloc) == _bare(host)
    return urlunsplit(parts) if same_host and in_path else None


def _bare(host: str) -> str:
    return host.lower().removeprefix(WWW_PREFIX)
