"""Builds the corpus adapters (EUvsDisinfo, catalogue documents) and runs the sync.

Features:
    US-KOR-08, F-11, ADR-32
"""

from collections.abc import Mapping
from datetime import datetime

from google.auth.credentials import Credentials
from httpx2 import AsyncClient
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.corpus.fetching import build_page_fetcher
from meritum_core.corpus.rerank import NullReranker, RerankerPort
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.corpus.adapters import (
    EntryPageDiscovery,
    McpEuvsDisinfo,
    MemoryCorpusWriter,
    MemoryEuvsCopy,
    OpenRouterReranker,
    PostgresCorpusWriter,
    PostgresEuvsCopy,
    VertexReranker,
    WorkersAiReranker,
)
from meritum_worker.corpus.constants import (
    EUVSDISINFO_MCP_URL,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_ENV,
)
from meritum_worker.corpus.errors import MissingTokenError
from meritum_worker.corpus.models import SyncReport
from meritum_worker.corpus.ports import (
    CorpusWriterPort,
    DocumentDiscoveryPort,
    EuvsCopyPort,
    EuvsDisinfoPort,
    IngestDeps,
)
from meritum_worker.corpus.settings import RerankerProvider, RerankerSettings
from meritum_worker.corpus.sync import missing_env, sync_euvsdisinfo


def build_euvsdisinfo_client(
    env: Mapping[str, str], http_client: AsyncClient
) -> EuvsDisinfoPort:
    """Build the MCP client with the token from the environment.

    Args:
        env: The worker's environment, usually ``os.environ``.
        http_client: HTTP client to use (a fake server in tests); the caller
            closes it.

    Returns:
        The client of the EUvsDisinfo MCP server.

    Raises:
        MissingTokenError: ``EUVSDISINFO_MCP_API_KEY`` is unset.

    Features:
        US-KOR-08, F-11, ADR-32
    """
    token = env.get(TOKEN_ENV, "")
    if not token:
        raise MissingTokenError(TOKEN_ENV)
    return McpEuvsDisinfo(EUVSDISINFO_MCP_URL, token, http_client)


def build_euvsdisinfo_copy(settings: CorpusSettings | None = None) -> EuvsCopyPort:
    """Build the local copy of EUvsDisinfo named by the corpus settings.

    Args:
        settings: Usually ``CorpusSettings()`` from ``MERITUM_CORPUS_*``; postgres
            keeps the copy in the shared ``corpus`` schema. None (tests) or
            memory: an in-process copy, lost on restart.

    Returns:
        The PostgreSQL or the in-memory copy.

    Raises:
        ValueError: postgres without a database URL (settings built unvalidated).

    Features:
        US-KOR-08, F-11, ADR-26
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by _postgres_url
    url = _postgres_url(settings)
    return MemoryEuvsCopy() if url is None else PostgresEuvsCopy(url)


def build_corpus_writer(settings: CorpusSettings | None = None) -> CorpusWriterPort:
    """Build the writer of catalogue documents and snapshots.

    Args:
        settings: Usually ``CorpusSettings()`` from ``MERITUM_CORPUS_*``; postgres
            writes the shared ``corpus`` schema. None (tests) or memory: in process.

    Returns:
        The PostgreSQL or the in-memory writer.

    Raises:
        ValueError: postgres without a database URL (settings built unvalidated).

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """  # ruff: ignore[docstring-extraneous-exception]  # raised by _postgres_url
    url = _postgres_url(settings)
    return MemoryCorpusWriter() if url is None else PostgresCorpusWriter(url)


def build_document_discovery() -> DocumentDiscoveryPort:
    """Build the discovery of catalogue pages: each entry's own page for now.

    Returns:
        The entry-page discovery.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    return EntryPageDiscovery()


def build_ingest_deps(
    settings: CorpusSettings, embeddings: EmbeddingsPort
) -> IngestDeps:
    """Build the ports of the catalogue ingestion from the worker's settings.

    Args:
        settings: ``CorpusSettings()``: where documents and snapshots go.
        embeddings: The model the corpus is searched with.

    Returns:
        Entry-page discovery, core's SSRF-safe fetcher, the embeddings, the writer.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    return IngestDeps(
        discovery=build_document_discovery(),
        fetcher=build_page_fetcher(),
        embeddings=embeddings,
        store=build_corpus_writer(settings),
    )


def _postgres_url(settings: CorpusSettings | None) -> str | None:
    if settings is None or settings.provider is CorpusProvider.MEMORY:
        return None
    if settings.database_url is None:
        msg = "MERITUM_CORPUS_DATABASE_URL is required for postgres"
        raise ValueError(msg)
    return settings.database_url.get_secret_value()


async def run_euvsdisinfo_sync(
    env: Mapping[str, str],
    store: EuvsCopyPort,
    embeddings: EmbeddingsPort,
    *,
    now: datetime,
    http_client: AsyncClient | None = None,
) -> SyncReport:
    """The body of the ``euvsdisinfo_sync`` workflow: check the token, then sync.

    Args:
        env: The worker's environment, usually ``os.environ``.
        store: The local copy.
        embeddings: Multilingual embeddings.
        now: When the sync runs.
        http_client: HTTP client (a fake server in tests); a new one, closed
            after the run, when None.

    Returns:
        The sync report; only ``missing_env`` when the token is unset, with
        no call to the server.

    Features:
        US-KOR-08, US-WDR-08, F-11, ADR-26
    """
    missing = missing_env(env)
    if missing:
        return SyncReport(missing_env=missing)
    async with http_client or AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as http:
        client = build_euvsdisinfo_client(env, http)
        return await sync_euvsdisinfo(client, store, embeddings, now=now)


def build_reranker(
    settings: RerankerSettings | None = None,
    *,
    credentials: Credentials | None = None,
    http_client: AsyncClient | None = None,
) -> RerankerPort:
    """Build the reranker ``MERITUM_RERANKER`` names.

    Args:
        settings: Reranker settings; read from the environment when None.
        credentials: Google credentials for Vertex AI; Application Default
            Credentials when None. Ignored by the other rerankers.
        http_client: HTTP client (shared pool, or recorded replies in tests); a
            new one when None. Ignored by the null gate.

    Returns:
        The Vertex AI, Workers AI or OpenRouter reranker, or core's null gate when no
        provider is set.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """
    settings = RerankerSettings() if settings is None else settings
    match settings.provider:
        case RerankerProvider.VERTEX:
            return VertexReranker(
                settings, credentials=credentials, http_client=http_client
            )
        case RerankerProvider.WORKERS_AI:
            return WorkersAiReranker(settings, http_client=http_client)
        case RerankerProvider.OPENROUTER:
            return OpenRouterReranker(settings, http_client=http_client)
        case RerankerProvider.NONE:
            return NullReranker()
