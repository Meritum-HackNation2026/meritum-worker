"""Settings of the EUvsDisinfo sync (not secrets), corpus migrations and live search.

Features:
    US-KOR-08, US-KOR-02, US-KOR-04, US-SPR-04, F-11, F-12, F-13
"""

from datetime import timedelta
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
them), served with zero data retention by Amazon Bedrock; OpenRouter picks
the region."""

OPENROUTER_PRIVACY: Final = {"zdr": True, "data_collection": "deny"}
"""Provider preferences of every OpenRouter rerank call, as core's LLM adapter
sends them (meritum-core#97): only ZDR endpoints; with none for the model
OpenRouter refuses to route, so no text leaves for a provider that keeps it."""

URL_SEGMENT: Final = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
"""Pattern of a project, location or account id: one URL path segment, so a
setting cannot redirect the request that carries the token."""

MODEL_ID: Final = r"^@?[A-Za-z0-9][A-Za-z0-9_@/-]*$"
"""Pattern of a model id (``semantic-ranker-default-005``,
``@cf/baai/bge-reranker-base``); no ``.``, ``?`` or ``#`` reach the URL."""

OPENROUTER_MODEL_ID: Final = r"^[a-z0-9-]+/[A-Za-z0-9._:-]+$"
"""Pattern of an OpenRouter model id (``cohere/rerank-v3.5``); it only goes in
the JSON body, so a ``.`` is allowed."""

WEB_SEARCH_TIMEOUT: Final = timedelta(seconds=10)
"""One deadline for live search in a check: the searches, the page fetches and
their scans (US-SPR-04, US-SPR-06, F-13, F-18). Searches past it make the check a
technical_failure; a page not scanned by then is dropped and the check goes on."""

WEB_SEARCH_MARGIN: Final = timedelta(seconds=1)
"""Time the search_web step gets past WEB_SEARCH_TIMEOUT, so pages cut at the
deadline drop out before the step's own backstop timeout ends the check."""

WEB_QUERIES_PER_CHECK: Final = 5
"""Most web searches one check sends: one per checked fact (US-KOR-04, F-13)."""

MAX_PARALLEL_CLAIMS: Final = 3
"""Most claims one research agent researches at once, corpus and web alike
(US-SPR-02, F-09, ADR-20)."""

WEB_RESULTS_PER_QUERY: Final = 3
"""Catalogue addresses asked per search; each is fetched and scanned in quarantine."""

WEB_PAGE_MAX_CHARS: Final = 4000
"""Longest page text kept as evidence and scanned: the limit of a pasted text."""

WEB_SOURCE_ID_PREFIX: Final = "web-"
"""Prefix of the id of a page found by live search, followed by its URL's hash."""

WEB_SOURCE_ID_HASH_CHARS: Final = 32
"""Hex characters of the URL's SHA-256 kept in a live search source id."""

WEB_TITLE_MAX_CHARS: Final = 200
"""Longest Source.title; a live search page is titled with its URL, cut to this."""

INJECTION_EXCERPT_MAX_CHARS: Final = 300
"""Longest InjectionEvent.excerpt the contract accepts."""
CHUNK_MAX_CHARS: Final = 1200
"""Longest passage of a catalogue document: short enough to quote with a link
and to embed in one call (US-KOR-05, F-12)."""

PARAGRAPH_SEPARATOR: Final = "\n\n"
"""Joins the paragraphs grouped into one passage."""

INGESTED_METHODS: Final = frozenset({"static", "rss", "sitemap"})
"""Catalogue ``ingest`` values fetched as web pages; ``mcp`` is the EUvsDisinfo
sync, ``live`` and ``web_search`` are queried per check (ADR-32), and ``api``
answers JSON the page fetcher refuses, so it waits for per-API adapters."""

EVIDENCE_ROLE: Final = "evidence"
"""Catalogue ``role`` of entries ingested as evidence; ``source_status`` lists
only feed a neutral warning."""

TDM_RESERVED_ENTRY: Final = "reserved"
"""Catalogue ``tdm_reservation`` of an owner who opted out of text and data mining."""

PLAN_STEP: Final = "plan due entries"
"""DBOS step that picks the due catalogue entries once per run, so a retried
entry step still fetches all of its pages."""

INGEST_STEP_PREFIX: Final = "ingest "
"""Prefix of an entry's DBOS step name, before its catalogue domain."""

SNAPSHOT_STEP: Final = "take snapshot"
"""DBOS step of the snapshot workflow."""

DEFAULT_REFRESH_MINUTES: Final = 1440
"""Refresh interval of a catalogue entry that names none: once a day."""

INGEST_WORKFLOW: Final = "corpus_ingest"
"""DBOS name of the scheduled catalogue ingestion workflow."""

INGEST_SCHEDULE: Final = "*/15 * * * *"
"""Cron of the ingestion: the shortest ``refresh_minutes`` the catalogue allows
is 15; each run fetches only the entries that are due."""

SNAPSHOT_WORKFLOW: Final = "corpus_snapshot"
"""DBOS name of the scheduled snapshot workflow."""

SNAPSHOT_SCHEDULE: Final = "0 * * * *"
"""Cron of the snapshots: a new ``corpus_version`` every hour, on the hour (ADR-19)."""

SNAPSHOT_VERSION_FORMAT: Final = "%Y-%m-%dT%H:%MZ"
"""strftime format of a ``corpus_version`` from its scheduled UTC time."""

INGEST_ENV: Final = "MERITUM_CORPUS_INGEST"
"""Environment variable that turns on ingestion and snapshots; set only where the
role may write the shared ``corpus`` schema (prd, infra#13)."""

INGEST_ENABLED: Final = "enabled"
"""The ``MERITUM_CORPUS_INGEST`` value that turns them on."""

SOURCE_ID_PREFIX: Final = "doc-"
"""Prefix of a catalogue document's ``source_id``, before a hash of its URL."""

SOURCE_ID_HASH_CHARS: Final = 24
"""Hex characters of the URL's sha256 kept in a ``source_id`` (96 bits)."""

PASSAGE_CHECKSUM_CHARS: Final = 12
"""Hex characters of the text checksum in a passage id."""

TDM_RESERVED: Final = "tdm_reserved"
"""Failure reason of a page whose meta tags reserve text and data mining."""

EMPTY_TEXT: Final = "empty_text"
"""Failure reason of a page with no main text."""

EMBEDDINGS_UNAVAILABLE: Final = "embeddings_unavailable"
"""Failure reason of a page whose passages could not be embedded."""

EMBED_BATCH: Final = 100
"""Passages embedded per call."""

CORPUS_WRITE_LOCK: Final = 17_0001
"""Advisory lock key (issue number + 0001): document writes take it shared, a
snapshot exclusive, so ``taken_at`` follows every write it covers (ADR-19)."""
