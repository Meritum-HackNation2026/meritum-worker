"""Builds the EUvsDisinfo client and the local copy, and runs the sync with them.

Features:
    US-KOR-08, F-11, ADR-32
"""

from collections.abc import Mapping
from datetime import datetime

from httpx2 import AsyncClient
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.corpus.adapters import (
    McpEuvsDisinfo,
    MemoryEuvsCopy,
    PostgresEuvsCopy,
)
from meritum_worker.corpus.constants import (
    EUVSDISINFO_MCP_URL,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_ENV,
)
from meritum_worker.corpus.errors import MissingTokenError
from meritum_worker.corpus.models import SyncReport
from meritum_worker.corpus.ports import EuvsCopyPort, EuvsDisinfoPort
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
    """
    if settings is None:
        return MemoryEuvsCopy()
    match settings.provider:
        case CorpusProvider.POSTGRES:
            if settings.database_url is None:
                msg = "MERITUM_CORPUS_DATABASE_URL is required for postgres"
                raise ValueError(msg)
            return PostgresEuvsCopy(settings.database_url.get_secret_value())
        case CorpusProvider.MEMORY:
            return MemoryEuvsCopy()


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
