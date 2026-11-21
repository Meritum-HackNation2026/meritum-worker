"""Builds the ports of the `check` workflow; nothing else instantiates adapters.

Features:
    US-SPR-01, US-OBS-01, F-22, ADR-03
"""

from meritum_core.checks.transcription import TranscriptionSettings, build_transcriber
from meritum_core.corpus.fetching import build_page_fetcher
from meritum_core.observability import build_app_repositories
from meritum_core.security.pii import PiiGateSettings, build_pii_gate
from meritum_core.shared.blobs import BlobProvider, BlobSettings, build_blob_store
from meritum_core.shared.database import DatabaseSettings
from meritum_core.shared.llm import LlmSettings, build_llm

from meritum_worker.checks.adapters import DbosCheckRuntime
from meritum_worker.checks.models import CheckDeps
from meritum_worker.checks.ports import CheckRuntime


def build_check_deps(
    settings: LlmSettings,
    database: DatabaseSettings,
    blobs: BlobSettings | None = None,
) -> CheckDeps:
    """Build the model, the repositories, the fetcher, masking and transcription.

    Args:
        settings: LLM settings, usually ``LlmSettings()`` from ``MERITUM_LLM_*``.
        database: app database settings, usually ``DatabaseSettings()`` from
            ``MERITUM_DATABASE_*``: in-memory fakes by default, PostgreSQL on dev
            and prd.
        blobs: blob store settings, usually ``BlobSettings()``; the in-memory
            store when None (no ``MERITUM_BLOB_PROVIDER``). Transcription reads
            ``MERITUM_TRANSCRIPTION_*``.

    Returns:
        The ports.

    Features:
        US-SPR-01, US-SPR-07, US-SPR-11, US-OBS-01, F-06, F-08, F-22
    """
    app = build_app_repositories(database)
    store = build_blob_store(blobs or BlobSettings(provider=BlobProvider.MEMORY))
    return CheckDeps(
        llm=build_llm(settings),
        records=app.records,
        pages=build_page_fetcher(),
        pii=build_pii_gate(PiiGateSettings()),
        blobs=store,
        transcriber=build_transcriber(TranscriptionSettings(), store),
        notifications=app.notifications,
    )


def build_check_runtime() -> CheckRuntime:
    """Build the DBOS runtime; call it inside the `check` workflow.

    Returns:
        The runtime.

    Features:
        US-SPR-01, F-22, ADR-03
    """
    return DbosCheckRuntime()
