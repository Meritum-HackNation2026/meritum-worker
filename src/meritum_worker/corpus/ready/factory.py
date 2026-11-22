"""Builds the gold build's ports from the worker's corpus settings.

Features:
    US-KOR-02, F-12
"""

from meritum_core.corpus import CorpusProvider, CorpusSettings, build_legal_act_meta
from meritum_core.corpus.catalog import load_catalog
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.corpus.ready.adapters import PostgresReadyStore
from meritum_worker.corpus.ready.build import ReadyDeps
from meritum_worker.corpus.ready.fakes import MemoryReadyStore
from meritum_worker.corpus.ready.ports import ReadyStorePort


def build_ready_deps(settings: CorpusSettings, embeddings: EmbeddingsPort) -> ReadyDeps:
    """Build the store, act metadata, embeddings and catalogue kinds of the build.

    Args:
        settings: ``CorpusSettings()``: the database with both corpus schemas.
        embeddings: The model bronze passages are indexed with.

    Returns:
        The PostgreSQL store for postgres, an empty in-memory one otherwise.

    Raises:
        ValueError: postgres without a database URL.

    Features:
        US-KOR-02, F-12
    """
    store: ReadyStorePort
    match settings.provider:
        case CorpusProvider.POSTGRES:
            if settings.database_url is None:
                msg = "MERITUM_CORPUS_DATABASE_URL is required for postgres"
                raise ValueError(msg)
            store = PostgresReadyStore(settings.database_url.get_secret_value())
        case CorpusProvider.MEMORY:
            store = MemoryReadyStore()
    kinds = {entry.domain: str(entry.kind) for entry in load_catalog()}
    return ReadyDeps(
        store=store,
        legal_meta=build_legal_act_meta(settings),
        embeddings=embeddings,
        catalog_kinds=kinds,
    )
