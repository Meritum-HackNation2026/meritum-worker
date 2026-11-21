"""Settings of the EUvsDisinfo sync that are not secrets.

Features:
    US-KOR-08, F-11
"""

from typing import Final

EUVSDISINFO_MCP_URL: Final = "https://euvsdisinfo-mcp-server.vercel.app/mcp"
"""Streamable HTTP endpoint of the EUvsDisinfo MCP server (Vercel, USA; ADR-14)."""

TOKEN_ENV: Final = "EUVSDISINFO_MCP_API_KEY"  # ruff: ignore[hardcoded-password-string]  # a variable name
"""Environment variable with the token EUvsDisinfo issues on request (worker#9)."""

MCP_ACCEPT: Final = "application/json, text/event-stream"
"""Accept header streamable HTTP requires: the server answers JSON or SSE."""

SSE_DATA_PREFIX: Final = "data:"
"""Prefix of the SSE line that carries the JSON-RPC answer."""

PAGE_SIZE: Final = 100
"""Items per ``cases`` / ``articles`` call; the server's maximum."""

REQUEST_TIMEOUT_SECONDS: Final = 60.0
"""Timeout of one MCP call; a page of 100 cases is a few hundred kilobytes."""

PUBLISHER_ID: Final = "eeas-euvsdisinfo"
"""Catalogue publisher id of EUvsDisinfo (EEAS East StratCom Task Force)."""

PUBLISHER_NAME: Final = "EUvsDisinfo (EEAS)"
"""Publisher name shown with a cited fact text."""

SOURCE_DOMAIN: Final = "euvsdisinfo.eu"
"""Catalogue domain of the EUvsDisinfo database."""

SYNC_WORKFLOW: Final = "euvsdisinfo_sync"
"""DBOS name of the sync workflow; started by hand, not by the backend."""

SOURCE_TITLE_MIN: Final = 3
"""Shortest ``Source.title`` the core contract accepts; shorter case titles get a
fallback naming the case."""

SOURCE_TITLE_MAX: Final = 200
"""Longest ``Source.title`` the core contract accepts; longer titles are cut."""
