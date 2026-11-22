"""Wiring of the archive ports: fetcher, blob store and the copies' registry.

Features:
    US-KOR-07, F-38
"""

from meritum_core.corpus.fetching import build_page_fetcher
from meritum_core.shared.blobs import BlobProvider, BlobSettings, build_blob_store
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings

from meritum_worker.corpus.archive_ports import ArchiveDeps, ArchiveRegistry

from ._memory_archive import MemoryArchiveRegistry
from ._postgres_archive import PostgresArchiveRegistry


def build_archive_deps(
    database: DatabaseSettings, blobs: BlobSettings | None = None
) -> ArchiveDeps:
    """Build core's SSRF-safe fetcher, the blob store and the copies' registry.

    Args:
        database: ``DatabaseSettings()``; PostgreSQL on dev and prd, in memory
            otherwise.
        blobs: ``BlobSettings()``; the in-memory store when None.

    Returns:
        The ports of the archiving workflow.

    Features:
        US-KOR-07, F-38
    """
    registry: ArchiveRegistry = MemoryArchiveRegistry()
    if database.provider is DatabaseProvider.POSTGRES and database.url is not None:
        registry = PostgresArchiveRegistry(database.url.get_secret_value())
    return ArchiveDeps(
        pages=build_page_fetcher(),
        blobs=build_blob_store(blobs or BlobSettings(provider=BlobProvider.MEMORY)),
        registry=registry,
    )
