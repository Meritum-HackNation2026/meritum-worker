"""Ingesting one ``ingest: api`` entry: request, parse, store each record.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from datetime import datetime

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetcherPort,
    PageFetchError,
)
from meritum_core.shared.embeddings import EmbeddingsUnavailableError

from meritum_worker.corpus.catalog_api.acts import act_body, act_parts
from meritum_worker.corpus.catalog_api.constants import (
    ACT_TEXT_EMPTY,
    ACT_TEXT_UNAVAILABLE,
    API_NOT_SUPPORTED,
    INVALID_API_RESPONSE,
)
from meritum_worker.corpus.catalog_api.listings import (
    ApiListing,
    api_listings,
    parse_listing,
)
from meritum_worker.corpus.catalog_api.records import (
    ApiRecord,
    InvalidApiResponseError,
)
from meritum_worker.corpus.constants import EMBEDDINGS_UNAVAILABLE
from meritum_worker.corpus.documents import IngestReport
from meritum_worker.corpus.pages import failed_page, store_page
from meritum_worker.corpus.ports import IngestDeps


async def ingest_api_entry(
    entry: CatalogEntry, deps: IngestDeps, *, now: datetime
) -> IngestReport:
    """Store every record of one API entry; a failed request never stops the rest.

    A legal act is stored with its full text, cut into parts; an act listed
    twice (by ELI and by the search) is read once.

    Args:
        entry: An ingestible entry with ``ingest: api``.
        deps: The ports; ``api_fetcher`` makes the requests.
        now: When the run starts; the documents' ``fetched_at``.

    Returns:
        The entry's report; a failed request is one failure with its URL.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12, ADR-32
    """
    listings = api_listings(
        entry,
        now,
        legal_acts=deps.legal.acts,
        search_limit=deps.legal.search_limit,
    )
    if deps.api_fetcher is None or not listings:
        return failed_page(entry, f"https://{entry.domain}", API_NOT_SUPPORTED)
    report = IngestReport()
    seen: set[str] = set()
    for listing in listings:
        report += await _ingest_listing(
            entry, listing, deps, deps.api_fetcher, now, seen
        )
    return report


async def _ingest_listing(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]  # one listing with the run's state
    entry: CatalogEntry,
    listing: ApiListing,
    deps: IngestDeps,
    fetcher: PageFetcherPort,
    now: datetime,
    seen: set[str],
) -> IngestReport:
    try:
        answer = await _fetch(listing, fetcher)
        records = parse_listing(listing, answer.untrusted_text)
    except PageFetchError as error:
        return failed_page(entry, listing.url, error.reason.value)
    except InvalidApiResponseError:
        return failed_page(entry, listing.url, INVALID_API_RESPONSE)
    report = IngestReport()
    for record in records:
        if record.url in seen:
            continue
        seen.add(record.url)
        documents, report = await _with_full_text(entry, record, fetcher, report)
        for document in documents:
            report += await _store(entry, document, deps, now)
    return report


async def _with_full_text(
    entry: CatalogEntry,
    record: ApiRecord,
    fetcher: PageFetcherPort,
    report: IngestReport,
) -> tuple[list[ApiRecord], IngestReport]:
    # A failed download stores nothing: the act's earlier full text stays.
    if not record.wants_text:
        return [record], report
    if record.text_url is None:
        return [record], report + failed_page(entry, record.url, ACT_TEXT_UNAVAILABLE)
    try:
        page = await fetcher.fetch(record.text_url, purpose=FetchPurpose.SOURCE)
    except PageFetchError as error:
        return [], report + failed_page(entry, record.text_url, error.reason.value)
    body = act_body(page.untrusted_text)
    if not body:
        return [record], report + failed_page(entry, record.text_url, ACT_TEXT_EMPTY)
    return act_parts(record, body), report


async def _store(
    entry: CatalogEntry, record: ApiRecord, deps: IngestDeps, now: datetime
) -> IngestReport:
    try:
        return await store_page(record.page(), entry, deps, now=now)
    except EmbeddingsUnavailableError:
        return failed_page(entry, record.url, EMBEDDINGS_UNAVAILABLE)


async def _fetch(listing: ApiListing, fetcher: PageFetcherPort) -> FetchedPage:
    for _ in range(listing.attempts - 1):
        try:
            return await fetcher.fetch(listing.url, purpose=FetchPurpose.SOURCE)
        except PageFetchError as error:
            if error.reason != FetchFailureReason.NOT_FOUND:
                raise
    return await fetcher.fetch(listing.url, purpose=FetchPurpose.SOURCE)
