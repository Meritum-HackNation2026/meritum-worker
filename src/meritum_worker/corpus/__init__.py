"""Corpus slice: catalogue ingestion, snapshots, live search, EUvsDisinfo copy.

Public API: the ingestion, sync and live search, their ports, models, errors and
factories.

Features:
    US-KOR-08, US-KOR-02, US-KOR-04, US-KOR-05, US-ZRD-08, F-10, F-11, F-12, F-13,
    ADR-19, ADR-26, ADR-32
"""

from meritum_worker.corpus.chunking import chunk_text
from meritum_worker.corpus.constants import (
    INGEST_SCHEDULE,
    INGEST_STEP_PREFIX,
    INGEST_WORKFLOW,
    MAX_PAGE_TEXT_CHARS,
    MAX_PARALLEL_CLAIMS,
    PLAN_STEP,
    SNAPSHOT_SCHEDULE,
    SNAPSHOT_STEP,
    SNAPSHOT_WORKFLOW,
    SYNC_WORKFLOW,
    TOKEN_ENV,
    WEB_SEARCH_MARGIN,
    WEB_SEARCH_TIMEOUT,
)
from meritum_worker.corpus.documents import (
    CorpusSnapshot,
    Document,
    DocumentMeta,
    DocumentPassage,
    IngestFailure,
    IngestReport,
    ManifestEntry,
)
from meritum_worker.corpus.errors import EuvsDisinfoUnavailableError, MissingTokenError
from meritum_worker.corpus.factory import (
    build_corpus_writer,
    build_document_discovery,
    build_euvsdisinfo_client,
    build_euvsdisinfo_copy,
    build_ingest_deps,
    build_organiser_file,
    build_reranker,
    run_euvsdisinfo_sync,
)
from meritum_worker.corpus.fakes import FakeWebSearch
from meritum_worker.corpus.ingest import (
    due_entries,
    ingest_catalog,
    ingest_pages,
    ingestible,
    ingestion_enabled,
    is_due,
    take_snapshot,
)
from meritum_worker.corpus.language import detect_language
from meritum_worker.corpus.live_search import (
    LiveSearchPorts,
    LiveSearchResult,
    search_live,
)
from meritum_worker.corpus.models import (
    Entry,
    EuvsArticle,
    EuvsCase,
    StoredEntry,
    SyncReport,
)
from meritum_worker.corpus.organiser import (
    IMPORT_WORKFLOW,
    ImportReport,
    import_organiser_file,
)
from meritum_worker.corpus.pages import store_page
from meritum_worker.corpus.ports import (
    CorpusWriterPort,
    DocumentDiscoveryPort,
    EuvsCopyPort,
    EuvsDisinfoPort,
    IngestDeps,
)
from meritum_worker.corpus.reranking import Reranking, rerank_passages
from meritum_worker.corpus.settings import RerankerProvider, RerankerSettings
from meritum_worker.corpus.sync import catalog_entry, missing_env, sync_euvsdisinfo

__all__ = [
    "IMPORT_WORKFLOW",
    "INGEST_SCHEDULE",
    "INGEST_STEP_PREFIX",
    "INGEST_WORKFLOW",
    "MAX_PAGE_TEXT_CHARS",
    "MAX_PARALLEL_CLAIMS",
    "PLAN_STEP",
    "SNAPSHOT_SCHEDULE",
    "SNAPSHOT_STEP",
    "SNAPSHOT_WORKFLOW",
    "SYNC_WORKFLOW",
    "TOKEN_ENV",
    "WEB_SEARCH_MARGIN",
    "WEB_SEARCH_TIMEOUT",
    "CorpusSnapshot",
    "CorpusWriterPort",
    "Document",
    "DocumentDiscoveryPort",
    "DocumentMeta",
    "DocumentPassage",
    "Entry",
    "EuvsArticle",
    "EuvsCase",
    "EuvsCopyPort",
    "EuvsDisinfoPort",
    "EuvsDisinfoUnavailableError",
    "FakeWebSearch",
    "ImportReport",
    "IngestDeps",
    "IngestFailure",
    "IngestReport",
    "LiveSearchPorts",
    "LiveSearchResult",
    "ManifestEntry",
    "MissingTokenError",
    "RerankerProvider",
    "RerankerSettings",
    "Reranking",
    "StoredEntry",
    "SyncReport",
    "build_corpus_writer",
    "build_document_discovery",
    "build_euvsdisinfo_client",
    "build_euvsdisinfo_copy",
    "build_ingest_deps",
    "build_organiser_file",
    "build_reranker",
    "catalog_entry",
    "chunk_text",
    "detect_language",
    "due_entries",
    "import_organiser_file",
    "ingest_catalog",
    "ingest_pages",
    "ingestible",
    "ingestion_enabled",
    "is_due",
    "missing_env",
    "rerank_passages",
    "run_euvsdisinfo_sync",
    "search_live",
    "store_page",
    "sync_euvsdisinfo",
    "take_snapshot",
]
