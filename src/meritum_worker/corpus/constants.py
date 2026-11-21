"""Settings of the EUvsDisinfo sync (not secrets) and of corpus migrations.

Features:
    US-KOR-08, US-KOR-02, F-11, F-12
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

MAX_PAGES: Final = 1000
"""Most pages per tool in one sync (100 000 items, about five times the database
in 2026); a server that ignores ``offset`` fails the sync instead of looping."""

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

CASE_KEY_PREFIX: Final = "case:"
"""Prefix of a case's key in the local copy, before the EUvsDisinfo id."""

ARTICLE_KEY_PREFIX: Final = "article:"
"""Prefix of an article's key in the local copy, before the EUvsDisinfo id."""

SOURCE_LANGUAGE: Final = "en"
"""Language of EUvsDisinfo fact texts as cited sources."""

CATALOG_LICENSE: Final = "unknown; short quotes with the source named"
"""No licence found for the database, so it is quoted briefly with its source."""

CATALOG_QUALIFIED_BECAUSE: Final = "EEAS registry of pro-Kremlin disinformation cases"
"""Why EUvsDisinfo is in the source catalogue."""

MIGRATIONS_PACKAGE: Final = "meritum_core.corpus"
"""Package of meritum-core whose ``migrations/`` holds the corpus schema's SQL files."""

MIGRATIONS_DIRECTORY: Final = "migrations"
"""Directory of ``MIGRATIONS_PACKAGE`` with the SQL files, applied in name order."""

MIGRATION_SUFFIX: Final = ".sql"
"""Suffix of a migration file; other files in the directory are ignored."""

MIGRATIONS_LOCK: Final = 32_0001
"""Advisory lock key (issue number + 0001, like core's 38_0001 for the app schema):
two deploys migrating corpus at once run one after another."""
