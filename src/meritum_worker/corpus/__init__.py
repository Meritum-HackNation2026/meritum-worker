"""Corpus slice of the worker: the local EUvsDisinfo copy and its sync.

Public API: the sync, its ports, models, errors and factories.

Features:
    US-KOR-08, F-11, ADR-26, ADR-32
"""

from meritum_worker.corpus.errors import EuvsDisinfoUnavailableError, MissingTokenError
from meritum_worker.corpus.factory import (
    build_euvsdisinfo_client,
    build_euvsdisinfo_copy,
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
from meritum_worker.corpus.sync import catalog_entry, missing_env, sync_euvsdisinfo

__all__ = [
    "Entry",
    "EuvsArticle",
    "EuvsCase",
    "EuvsCopyPort",
    "EuvsDisinfoPort",
    "EuvsDisinfoUnavailableError",
    "MissingTokenError",
    "StoredEntry",
    "SyncReport",
    "build_euvsdisinfo_client",
    "build_euvsdisinfo_copy",
    "catalog_entry",
    "missing_env",
    "run_euvsdisinfo_sync",
    "sync_euvsdisinfo",
]
