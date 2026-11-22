"""Ingesting one ``ingest: api`` entry: request, parse, store each record.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from datetime import datetime

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchPurpose, PageFetcherPort, PageFetchError
from meritum_core.shared.embeddings import EmbeddingsUnavailableError

from meritum_worker.corpus.catalog_api.constants import (
    API_NOT_SUPPORTED,
    INVALID_API_RESPONSE,
)
from meritum_worker.corpus.catalog_api.listings import (
    ApiListing,
    api_listings,
    parse_listing,
)
from meritum_worker.corpus.catalog_api.records import InvalidApiResponseError
from meritum_worker.corpus.constants import EMBEDDINGS_UNAVAILABLE
from meritum_worker.corpus.documents import IngestReport
from meritum_worker.corpus.pages import failed_page, store_page
from meritum_worker.corpus.ports import IngestDeps


async def ingest_api_entry(
    entry: CatalogEntry, deps: IngestDeps, *, now: datetime
) -> IngestReport:
    """Store every record of one API entry; a failed request never stops the rest.

    Args:
        entry: An ingestible entry with ``ingest: api``.
        deps: The ports; ``api_fetcher`` makes the requests.
        now: When the run starts; the documents' ``fetched_at``.

    Returns:
        The entry's report; a failed request is one failure with its URL.

    Features:
        US-KOR-02, F-10, F-12, ADR-32
    """
    listings = api_listings(entry, now)
    if deps.api_fetcher is None or not listings:
        return failed_page(entry, f"https://{entry.domain}", API_NOT_SUPPORTED)
    report = IngestReport()
    for listing in listings:
        report += await _ingest_listing(entry, listing, deps, deps.api_fetcher, now)
    return report


async def _ingest_listing(
    entry: CatalogEntry,
    listing: ApiListing,
    deps: IngestDeps,
    fetcher: PageFetcherPort,
    now: datetime,
) -> IngestReport:
    try:
        answer = await fetcher.fetch(listing.url, purpose=FetchPurpose.SOURCE)
        records = parse_listing(listing, answer.untrusted_text)
    except PageFetchError as error:
        return failed_page(entry, listing.url, error.reason.value)
    except InvalidApiResponseError:
        return failed_page(entry, listing.url, INVALID_API_RESPONSE)
    report = IngestReport()
    for record in records:
        try:
            report += await store_page(record.page(), entry, deps, now=now)
        except EmbeddingsUnavailableError:
            report += failed_page(entry, record.url, EMBEDDINGS_UNAVAILABLE)
    return report
