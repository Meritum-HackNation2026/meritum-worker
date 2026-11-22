"""Builds the ports of the `check` workflow; nothing else instantiates adapters.

Features:
    US-SPR-01, US-OBS-01, F-22, ADR-03
"""

import os

from meritum_core.checks.transcription import TranscriptionSettings, build_transcriber
from meritum_core.corpus import CorpusSettings, build_corpus_search
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import build_page_fetcher
from meritum_core.corpus.web_search import WebSearchSettings, build_web_search
from meritum_core.observability import build_app_repositories
from meritum_core.security.pii import PiiGateSettings, build_pii_gate
from meritum_core.shared.blobs import BlobProvider, BlobSettings, build_blob_store
from meritum_core.shared.database import DatabaseSettings
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings
from meritum_core.shared.llm import LlmSettings, build_llm

from meritum_worker.checks.adapters import DbosCheckRuntime
from meritum_worker.checks.models import CheckDeps
from meritum_worker.checks.ports import CheckRuntime
from meritum_worker.checks.settings import ResearchSettings
from meritum_worker.corpus import build_reranker
from meritum_worker.moderation import build_moderation_deps
from meritum_worker.security import InjectionGateSettings, build_detector


def build_check_deps(
    settings: LlmSettings,
    database: DatabaseSettings,
    blobs: BlobSettings | None = None,
) -> CheckDeps:
    """Build the model, repositories, fetcher, masking, transcription and web search.

    Web search reads ``MERITUM_WEB_SEARCH_*`` (stub by default); the injection
    detector reads ``MERITUM_INJECTION_GATE_*``.

    Args:
        settings: LLM settings, usually ``LlmSettings()`` from ``MERITUM_LLM_*``.
        database: app database settings, usually ``DatabaseSettings()`` from
            ``MERITUM_DATABASE_*``: in-memory fakes by default, PostgreSQL on dev
            and prd.
        blobs: blob store settings, usually ``BlobSettings()``; the in-memory
            store when None (no ``MERITUM_BLOB_PROVIDER``). Transcription reads
            ``MERITUM_TRANSCRIPTION_*``; corpus search ``MERITUM_CORPUS_*`` and
            ``MERITUM_EMBEDDINGS_*``, the reranker ``MERITUM_RERANKER``, the
            snapshot ``MERITUM_CORPUS_VERSION``.

    Returns:
        The ports.

    Features:
        US-SPR-01, US-SPR-04, US-SPR-07, US-SPR-11, US-OBS-01, US-KOR-04, F-06,
        F-08, F-12, F-13, F-22
    """
    app = build_app_repositories(database)
    store = build_blob_store(blobs or BlobSettings(provider=BlobProvider.MEMORY))
    llm = build_llm(settings)
    embeddings = build_embeddings(EmbeddingsSettings())
    catalog = load_catalog()
    return CheckDeps(
        llm=llm,
        records=app.records,
        pages=build_page_fetcher(),
        pii=build_pii_gate(PiiGateSettings()),
        blobs=store,
        transcriber=build_transcriber(TranscriptionSettings(), store),
        notifications=app.notifications,
        web_search=build_web_search(WebSearchSettings(), catalog),
        injection=build_detector(llm, InjectionGateSettings()),
        catalog=catalog,
        corpus=build_corpus_search(CorpusSettings(), embeddings),
        reranker=build_reranker(),
        corpus_version=ResearchSettings().corpus_version,
        moderation=build_moderation_deps(app, embeddings, os.environ),
    )


def build_check_runtime() -> CheckRuntime:
    """Build the DBOS runtime; call it inside the `check` workflow.

    Returns:
        The runtime.

    Features:
        US-SPR-01, F-22, ADR-03
    """
    return DbosCheckRuntime()
