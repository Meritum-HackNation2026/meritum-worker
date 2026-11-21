"""Security slice: the injection classifier gate, retention and erasure on request.

Public API: gate settings and factories, the retention and ``delete_subject``
workflow bodies, their ports and the in-memory workflow store.

Features:
    US-BEZ-01, US-BEZ-05, US-POW-04, F-19, F-20, ADR-12, ADR-13, ADR-35
"""

from meritum_worker.security.constants import (
    BLOB_PROVIDER_ENV,
    ERASURE_SETTLE,
    RETENTION_CRON,
    RETENTION_SCHEDULE_NAME,
    RETENTION_WORKFLOW,
)
from meritum_worker.security.erasure import erase_subject
from meritum_worker.security.factory import (
    build_detector,
    build_injection_gate,
    build_retention_deps,
)
from meritum_worker.security.fakes import CleanInjectionDetector, InMemoryWorkflowStore
from meritum_worker.security.models import (
    RetentionDeps,
    RetentionReport,
    StoredWorkflow,
)
from meritum_worker.security.ports import BlobCleaner, RemovedCaseChecks, WorkflowStore
from meritum_worker.security.retention import run_retention
from meritum_worker.security.selection import about_checks, audio_id, names_subject
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)

__all__ = [
    "BLOB_PROVIDER_ENV",
    "ERASURE_SETTLE",
    "RETENTION_CRON",
    "RETENTION_SCHEDULE_NAME",
    "RETENTION_WORKFLOW",
    "BlobCleaner",
    "CleanInjectionDetector",
    "InMemoryWorkflowStore",
    "InjectionGateProvider",
    "InjectionGateSettings",
    "RemovedCaseChecks",
    "RetentionDeps",
    "RetentionReport",
    "StoredWorkflow",
    "WorkflowStore",
    "about_checks",
    "audio_id",
    "build_detector",
    "build_injection_gate",
    "build_retention_deps",
    "erase_subject",
    "names_subject",
    "run_retention",
]
