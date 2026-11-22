"""Catalogue ingestion runs and snapshots, on ports only.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-32
"""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.shared.embeddings import EmbeddingsUnavailableError

from meritum_worker.corpus.catalog_api import ingest_api_entry
from meritum_worker.corpus.catalog_api.constants import API_METHOD
from meritum_worker.corpus.constants import (
    DEFAULT_REFRESH_MINUTES,
    EMBEDDINGS_UNAVAILABLE,
    EVIDENCE_ROLE,
    INGEST_ENABLED,
    INGEST_ENV,
    INGESTED_METHODS,
    SNAPSHOT_VERSION_FORMAT,
    TDM_RESERVED_ENTRY,
)
from meritum_worker.corpus.documents import CorpusSnapshot, IngestReport
from meritum_worker.corpus.pages import failed_page, store_page
from meritum_worker.corpus.ports import CorpusWriterPort, IngestDeps


def ingestion_enabled(env: Mapping[str, str]) -> bool:
    """Whether this worker may ingest and take snapshots.

    Args:
        env: The worker's environment, usually ``os.environ``.

    Returns:
        True only with ``MERITUM_CORPUS_INGEST=enabled``, set where the role may
        write the shared ``corpus`` schema (prd, infra#13).

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    return env.get(INGEST_ENV, "") == INGEST_ENABLED


def ingestible(entries: Iterable[CatalogEntry]) -> list[CatalogEntry]:
    """Keep the entries the catalogue ingestion fetches.

    Args:
        entries: The catalogue, e.g. ``load_catalog()``.

    Returns:
        Evidence entries fetched as static pages, RSS, sitemaps or public APIs
        that are neither excluded nor reserved for text and data mining.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    return [e for e in entries if _is_ingestible(e)]


def _is_ingestible(entry: CatalogEntry) -> bool:
    is_evidence = entry.role == EVIDENCE_ROLE and entry.ingest in INGESTED_METHODS
    may_mine = not entry.excluded and entry.tdm_reservation != TDM_RESERVED_ENTRY
    return is_evidence and may_mine


def is_due(entry: CatalogEntry, last_attempt: datetime | None, now: datetime) -> bool:
    """Whether an entry's ``refresh_minutes`` passed since it was last tried.

    Args:
        entry: A catalogue entry.
        last_attempt: When the ingestion last tried its domain, None if never.
        now: When the run starts.

    Returns:
        True when the entry should be fetched now.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """
    minutes = entry.refresh_minutes or DEFAULT_REFRESH_MINUTES
    return last_attempt is None or now - last_attempt >= timedelta(minutes=minutes)


async def due_entries(
    entries: Iterable[CatalogEntry], store: CorpusWriterPort, *, now: datetime
) -> list[CatalogEntry]:
    """Pick the ingestible entries that are due, before any of them is fetched.

    Args:
        entries: The catalogue.
        store: The corpus writer, which keeps the last attempt per domain.
        now: When the run starts.

    Returns:
        The due entries, in catalogue order.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    return [
        e
        for e in ingestible(entries)
        if is_due(e, await store.last_attempt(e.domain), now)
    ]


async def ingest_catalog(
    entries: Iterable[CatalogEntry], deps: IngestDeps, *, now: datetime
) -> IngestReport:
    """Ingest every due entry; one failed page never stops the run.

    Args:
        entries: The catalogue.
        deps: The ports.
        now: When the run starts; the documents' ``fetched_at``.

    Returns:
        The summed report of every entry.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    report = IngestReport()
    for entry in await due_entries(entries, deps.store, now=now):
        report += await ingest_pages(entry, deps, now=now)
    return report


async def ingest_pages(
    entry: CatalogEntry, deps: IngestDeps, *, now: datetime
) -> IngestReport:
    """Fetch, chunk, embed and store every page of one entry.

    The attempt is noted first, so a domain whose pages all fail waits its
    ``refresh_minutes`` too. A page that fails (robots.txt, Content-Signal,
    HTTP error, TDM meta tags, embeddings down) goes to the report and the
    next page follows. An ``ingest: api`` entry stores one document per API
    record instead (``catalog_api``).

    Args:
        entry: An ingestible catalogue entry.
        deps: The ports.
        now: When the run starts.

    Returns:
        The entry's report.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    await deps.store.record_attempt(entry.domain, now)
    if entry.ingest == API_METHOD:
        return await ingest_api_entry(entry, deps, now=now)
    report = IngestReport()
    for url in await deps.discovery.urls(entry):
        try:
            page = await deps.fetcher.fetch(url, purpose=FetchPurpose.SOURCE)
            report += await store_page(page, entry, deps, now=now, url=url)
        except PageFetchError as error:
            report += failed_page(entry, url, error.reason.value)
        except EmbeddingsUnavailableError:
            report += failed_page(entry, url, EMBEDDINGS_UNAVAILABLE)
    return report


async def take_snapshot(
    store: CorpusWriterPort, *, scheduled: datetime
) -> CorpusSnapshot:
    """Take the ``corpus_version`` named after its scheduled UTC time (ADR-19).

    Pages stored since the previous snapshot, live-search pages included,
    join this one (ADR-21).

    Args:
        store: The corpus writer.
        scheduled: The scheduled UTC time of the snapshot workflow.

    Returns:
        The snapshot; the same one when the workflow is retried.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-21
    """
    return await store.take_snapshot(scheduled.strftime(SNAPSHOT_VERSION_FORMAT))
