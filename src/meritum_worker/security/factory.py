"""Builds the classifier gate, the detector around it and the retention ports.

Features:
    US-BEZ-01, US-BEZ-05, F-19, F-20, ADR-12, ADR-13, ADR-35
"""

from google.auth.credentials import Credentials
from httpx2 import AsyncClient
from meritum_core.corpus import CorpusSettings
from meritum_core.jobs.contracts import CHECK
from meritum_core.observability import build_app_repositories
from meritum_core.security.injection import (
    InjectionDetectorPort,
    InjectionGatePort,
    NullInjectionGate,
    build_injection_detector,
)
from meritum_core.shared.blobs import BlobProvider, BlobSettings, build_blob_store
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.llm import LlmPort

from meritum_worker.corpus import (
    ArchiveDeps,
    CorpusRetentionPort,
    build_corpus_retention,
)
from meritum_worker.corpus.adapters import build_archive_deps
from meritum_worker.security.adapters import (
    DbosWorkflowStore,
    ModelArmorGate,
    NullBlobCleaner,
    NullRemovedCaseChecks,
    PostgresRemovedCaseChecks,
    StoreBlobCleaner,
    WorkersAiGate,
)
from meritum_worker.security.models import RetentionDeps
from meritum_worker.security.ports import BlobCleaner, RemovedCaseChecks, WorkflowStore
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)


def build_injection_gate(
    settings: InjectionGateSettings,
    *,
    credentials: Credentials | None = None,
    http_client: AsyncClient | None = None,
) -> InjectionGatePort:
    """Build the gate the settings name.

    Args:
        settings: Usually ``InjectionGateSettings()`` from the environment.
        credentials: Google credentials for Model Armor; Application Default
            Credentials when None. Ignored by the other gates.
        http_client: HTTP client (shared pool, or recorded replies in tests); a
            new one when None. Ignored by the null gate.

    Returns:
        Model Armor, Workers AI, or the null gate when no provider is set.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """
    match settings.provider:
        case InjectionGateProvider.MODEL_ARMOR:
            return ModelArmorGate(
                settings, credentials=credentials, http_client=http_client
            )
        case InjectionGateProvider.WORKERS_AI:
            return WorkersAiGate(settings, http_client=http_client)
        case InjectionGateProvider.NONE:
            return NullInjectionGate()


def build_detector(
    llm: LlmPort,
    settings: InjectionGateSettings,
    *,
    credentials: Credentials | None = None,
    http_client: AsyncClient | None = None,
) -> InjectionDetectorPort:
    """Build core's layered detector with the configured gate (ADR-12, ADR-35).

    Args:
        llm: The model of the isolated classifier layer.
        settings: Gate settings, usually ``InjectionGateSettings()``.
        credentials: Passed to ``build_injection_gate``.
        http_client: Passed to ``build_injection_gate``.

    Returns:
        Patterns, the configured gate and the isolated LLM classifier.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-23, ADR-35
    """
    gate = build_injection_gate(
        settings, credentials=credentials, http_client=http_client
    )
    return build_injection_detector(llm=llm, gate=gate)


def build_retention_deps(  # ruff: ignore[too-many-arguments]  # keyword-only test seams beside the two settings
    database: DatabaseSettings,
    blobs: BlobSettings | None,
    *,
    workflows: WorkflowStore | None = None,
    corpus: CorpusSettings | None = None,
    corpus_store: CorpusRetentionPort | None = None,
    archives: ArchiveDeps | None = None,
    check_workflows: tuple[str, ...] = (CHECK.name,),
) -> RetentionDeps:
    """Build the ports of the retention and ``delete_subject`` workflows.

    Args:
        database: app database settings, usually ``DatabaseSettings()``.
        blobs: blob store settings, usually ``BlobSettings()``; None when the
            worker has no ``MERITUM_BLOB_PROVIDER`` and so no files to delete.
        workflows: the DBOS workflow data; DBOS itself when None.
        corpus: corpus settings, usually ``CorpusSettings()`` when the worker
            ingests the catalogue; None: an empty in-memory corpus.
        corpus_store: the corpus retention itself (tests); wins over ``corpus``.
        archives: the page archive ports (tests); built from ``database`` and
            ``blobs`` when None.
        check_workflows: the names of workflows whose input is a ``CheckInput``.

    Returns:
        The ports.

    Features:
        US-BEZ-05, US-POW-04, US-KOR-05, F-10, F-20, ADR-13
    """
    return RetentionDeps(
        app=build_app_repositories(database),
        workflows=DbosWorkflowStore() if workflows is None else workflows,
        blobs=_blob_cleaner(blobs),
        removed_checks=_removed_checks(database),
        corpus=build_corpus_retention(corpus) if corpus_store is None else corpus_store,
        archives=build_archive_deps(database, blobs) if archives is None else archives,
        check_workflows=check_workflows,
    )


def _blob_cleaner(settings: BlobSettings | None) -> BlobCleaner:
    if settings is None:
        return NullBlobCleaner()
    is_volume = settings.provider is BlobProvider.FILESYSTEM
    directory = settings.directory if is_volume else None
    return StoreBlobCleaner(build_blob_store(settings), directory)


def _removed_checks(settings: DatabaseSettings) -> RemovedCaseChecks:
    if settings.provider is DatabaseProvider.POSTGRES and settings.url is not None:
        return PostgresRemovedCaseChecks(settings.url.get_secret_value())
    return NullRemovedCaseChecks()
