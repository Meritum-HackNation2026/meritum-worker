"""Corpus slice of the worker: the local EUvsDisinfo copy and its sync.

Public API: the sync, its ports, models, errors and factories.

Features:
    US-KOR-08, F-11, ADR-26, ADR-32
"""

from meritum_worker.corpus.constants import SYNC_WORKFLOW, TOKEN_ENV
from meritum_worker.corpus.errors import EuvsDisinfoUnavailableError, MissingTokenError
from meritum_worker.corpus.factory import (
    build_euvsdisinfo_client,
    build_euvsdisinfo_copy,
    build_reranker,
    run_euvsdisinfo_sync,
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
    "SYNC_WORKFLOW",
    "TOKEN_ENV",
    "Entry",
    "EuvsArticle",
    "EuvsCase",
    "EuvsCopyPort",
    "EuvsDisinfoPort",
    "EuvsDisinfoUnavailableError",
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
    "sync_euvsdisinfo",
]
