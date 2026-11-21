"""Builds the EUvsDisinfo client and the local copy.

Features:
    US-KOR-08, F-11, ADR-32
"""

from collections.abc import Mapping

from httpx2 import AsyncClient

from meritum_worker.corpus.adapters import McpEuvsDisinfo, MemoryEuvsCopy
from meritum_worker.corpus.constants import (
    EUVSDISINFO_MCP_URL,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_ENV,
)
from meritum_worker.corpus.errors import MissingTokenError
from meritum_worker.corpus.ports import EuvsCopyPort, EuvsDisinfoPort


def build_euvsdisinfo_client(
    env: Mapping[str, str], *, http_client: AsyncClient | None = None
) -> EuvsDisinfoPort:
    """Build the MCP client with the token from the environment.

    Args:
        env: The worker's environment, usually ``os.environ``.
        http_client: HTTP client to use (a fake server in tests); a new one
            with ``REQUEST_TIMEOUT_SECONDS`` when None.

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
    client = http_client or AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    return McpEuvsDisinfo(EUVSDISINFO_MCP_URL, token, client)


def build_euvsdisinfo_copy() -> EuvsCopyPort:
    """Build the local copy of EUvsDisinfo.

    Returns:
        The in-memory copy.

    Features:
        US-KOR-08, F-11
    """
    # shortcut: in-memory only, lost on restart; add a PostgreSQL copy once the
    # corpus schema has its tables (follow-up issue).
    return MemoryEuvsCopy()
