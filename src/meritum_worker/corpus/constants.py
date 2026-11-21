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

RERANKER_ENV: Final = "MERITUM_RERANKER"
"""Environment variable naming the reranker: ``none``, ``vertex``, ``workers_ai``
or ``openrouter``."""

RERANKER_ENV_PREFIX: Final = "MERITUM_RERANKER_"
"""Prefix of the reranker's other variables (``MERITUM_RERANKER_PROJECT``)."""

RERANK_RETRIES: Final = 2
"""HTTP attempts per reranking, the first included; then the search order stays."""

RERANK_RETRY_BACKOFF_SECONDS: Final = 0.5
"""Pause before the second attempt, doubled before each further one."""

RERANK_TIMEOUT_SECONDS: Final = 10.0
"""Timeout of one reranking call; 20 passages are a few kilobytes."""

RERANK_FAILED_ERROR: Final = "search_corpus: reranker_unavailable"
"""What retrieval_errors records when the reranker failed; the search order stays.
Reranking runs under the ``search_corpus`` step code, hence the prefix."""

VERTEX_RANKING_HOST: Final = "discoveryengine.googleapis.com"
"""Host of the Vertex AI ranking API; a location other than ``global`` prefixes it."""

VERTEX_RANKING_LOCATION: Final = "global"
"""Default location of the ranking config; the only one the ranking guide shows."""

VERTEX_RANKING_MODEL: Final = "semantic-ranker-default-005"
"""Default ranking model, pinned rather than ``@latest``: 25 languages, 1024 tokens
per record."""

VERTEX_RANKING_SCOPES: Final = ("https://www.googleapis.com/auth/cloud-platform",)
"""OAuth scope of the ranking API's access token."""

WORKERS_AI_RERANK_ENDPOINT: Final = "https://api.cloudflare.com/client/v4/accounts"
"""Cloudflare API base; the run URL is ``{base}/{account}/ai/run/{model}``."""

WORKERS_AI_RERANK_MODEL: Final = "@cf/baai/bge-reranker-base"
"""Default Workers AI reranker: a bge cross-encoder, 512 tokens per context."""

OPENROUTER_RERANK_URL: Final = "https://openrouter.ai/api/v1/rerank"
"""OpenRouter rerank endpoint; the model goes in the body, not the URL."""

OPENROUTER_RERANK_MODEL: Final = "cohere/rerank-v3.5"
"""Default OpenRouter reranker: multilingual Cohere (100+ languages, Polish among
them), served with zero data retention by Amazon Bedrock; OpenRouter picks the region."""

OPENROUTER_PRIVACY: Final = {"zdr": True, "data_collection": "deny"}
"""Provider preferences of every OpenRouter rerank call, as core's LLM adapter
sends them (meritum-core#97): only ZDR endpoints; with none for the model OpenRouter refuses to
route, so no text leaves for a provider that keeps it."""

URL_SEGMENT: Final = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
"""Pattern of a project, location or account id: one URL path segment, so a
setting cannot redirect the request that carries the token."""

MODEL_ID: Final = r"^@?[A-Za-z0-9][A-Za-z0-9_@/-]*$"
"""Pattern of a model id (``semantic-ranker-default-005``,
``@cf/baai/bge-reranker-base``); no ``.``, ``?`` or ``#`` reach the URL."""

OPENROUTER_MODEL_ID: Final = r"^[a-z0-9-]+/[A-Za-z0-9._:-]+$"
"""Pattern of an OpenRouter model id (``cohere/rerank-v3.5``); it only goes in
the JSON body, so a ``.`` is allowed."""
