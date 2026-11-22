"""Major media as catalogue entries, for the last-resort search of a check.

Features:
    US-KOR-04, F-13, ADR-07
"""

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.checks.news.constants import (
    NEWS_LICENSE,
    NEWS_MEDIA,
    NEWS_QUALIFIED_BECAUSE,
)


def news_catalog() -> tuple[CatalogEntry, ...]:
    """Build the catalogue entries of the major media.

    Each outlet is a secondary ``media`` source queried live and never
    ingested; the fetcher still asks robots.txt and Content-Signal per page.

    Returns:
        One entry per outlet of ``NEWS_MEDIA``.

    Features:
        US-KOR-04, F-13, ADR-07
    """
    return tuple(
        CatalogEntry(
            domain=domain,
            publisher=publisher,
            publisher_id=publisher_id,
            kind="media",
            tier="secondary",
            role="evidence",
            license=NEWS_LICENSE,
            ingest="live",
            validity="expires",
            qualified_because=NEWS_QUALIFIED_BECAUSE,
        )
        for domain, publisher, publisher_id in NEWS_MEDIA
    )
