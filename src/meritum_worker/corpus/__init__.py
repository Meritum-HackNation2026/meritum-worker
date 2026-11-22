"""Corpus slice of the worker: the local EUvsDisinfo copy, its sync and live search.

Public API: the sync, live search, their ports, models, errors and factories.

Features:
    US-KOR-08, US-KOR-04, F-11, F-13, ADR-26, ADR-32
"""

from meritum_worker.corpus.constants import (
    MAX_PARALLEL_CLAIMS,
    SYNC_WORKFLOW,
    TOKEN_ENV,
    WEB_SEARCH_MARGIN,
    WEB_SEARCH_TIMEOUT,
)
from meritum_worker.corpus.errors import EuvsDisinfoUnavailableError, MissingTokenError
from meritum_worker.corpus.factory import (
    build_euvsdisinfo_client,
    build_euvsdisinfo_copy,
    build_reranker,
    run_euvsdisinfo_sync,
)
from meritum_worker.corpus.fakes import FakeWebSearch
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
from meritum_worker.corpus.ports import EuvsCopyPort, EuvsDisinfoPort
from meritum_worker.corpus.reranking import Reranking, rerank_passages
from meritum_worker.corpus.settings import RerankerProvider, RerankerSettings
from meritum_worker.corpus.sync import catalog_entry, missing_env, sync_euvsdisinfo

__all__ = [
    "MAX_PARALLEL_CLAIMS",
    "SYNC_WORKFLOW",
    "TOKEN_ENV",
    "WEB_SEARCH_MARGIN",
    "WEB_SEARCH_TIMEOUT",
    "Entry",
    "EuvsArticle",
    "EuvsCase",
    "EuvsCopyPort",
    "EuvsDisinfoPort",
    "EuvsDisinfoUnavailableError",
    "FakeWebSearch",
    "LiveSearchPorts",
    "LiveSearchResult",
    "MissingTokenError",
    "RerankerProvider",
    "RerankerSettings",
    "Reranking",
    "StoredEntry",
    "SyncReport",
    "build_euvsdisinfo_client",
    "build_euvsdisinfo_copy",
    "build_reranker",
    "catalog_entry",
    "missing_env",
    "rerank_passages",
    "run_euvsdisinfo_sync",
    "search_live",
    "sync_euvsdisinfo",
]
