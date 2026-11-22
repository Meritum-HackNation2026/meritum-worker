"""The gold build: bronze documents that changed become silver text and gold chunks.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from meritum_core.corpus import LegalActMeta, LegalActMetaPort
from meritum_core.corpus.ready import CorpusReadySettings
from meritum_core.shared.embeddings import EmbeddingsPort, Vector

from meritum_worker.corpus.ingest import ingestion_enabled
from meritum_worker.corpus.ready.constants import EMBED_BATCH
from meritum_worker.corpus.ready.gold import gold_chunks
from meritum_worker.corpus.ready.models import BronzeDocument, BuildReport
from meritum_worker.corpus.ready.ports import ReadyStorePort
from meritum_worker.corpus.ready.silver import clean, silver_text


@dataclass(frozen=True)
class ReadyDeps:
    """What the gold build needs.

    Attributes:
        store: Bronze reads, silver and gold writes.
        legal_meta: Core's act metadata (core#167); empty until the worker writes it.
        embeddings: The model bronze passages are indexed with.
        catalog_kinds: Catalogue ``kind`` per domain (``akt_prawny``, ``fact_check``…).

    Features:
        US-KOR-02, F-12
    """

    store: ReadyStorePort
    legal_meta: LegalActMetaPort
    embeddings: EmbeddingsPort
    catalog_kinds: Mapping[str, str] = field(default_factory=dict)


async def build_ready_layer(deps: ReadyDeps, *, build_id: str) -> BuildReport:
    """Rebuild silver and gold for new or changed documents, forget removed ones.

    Unchanged documents (same checksum in silver) cost nothing, so a retried or
    hourly run only does the new work.

    Args:
        deps: Store, act metadata, embeddings and catalogue kinds.
        build_id: The run's id (its DBOS workflow id).

    Returns:
        Counts of documents rebuilt, chunks written and documents removed.

    Features:
        US-KOR-02, US-ZRD-05, F-12
    """
    await deps.store.prepare()
    live = await deps.store.live_versions()
    built = await deps.store.built_versions()
    gone = sorted(set(built) - set(live))
    await deps.store.remove(gone)
    todo = sorted(sid for sid, checksum in live.items() if built.get(sid) != checksum)
    chunks = 0
    for start in range(0, len(todo), EMBED_BATCH):
        docs = await deps.store.documents(todo[start : start + EMBED_BATCH])
        metas = await deps.legal_meta.read([d.source_id for d in docs])
        for doc in docs:
            chunks += await _rebuild(deps, doc, metas.get(doc.source_id), build_id)
    report = BuildReport(
        build_id=build_id, documents=len(todo), chunks=chunks, removed=len(gone)
    )
    await deps.store.record(report)
    return report


async def _rebuild(
    deps: ReadyDeps, doc: BronzeDocument, meta: LegalActMeta | None, build_id: str
) -> int:
    found = gold_chunks(doc, deps.catalog_kinds.get(doc.domain), meta)
    texts = [f"{c.header}\n{c.text}" for c in found]
    vectors: list[Vector] = []
    for start in range(0, len(texts), EMBED_BATCH):
        vectors += await deps.embeddings.embed_documents(
            texts[start : start + EMBED_BATCH]
        )
    silver = silver_text(doc.full_text, clean(doc.full_text))
    await deps.store.replace(
        doc, silver, list(zip(found, vectors, strict=True)), build_id
    )
    return len(found)


def build_enabled() -> bool:
    """Whether this worker schedules the gold build.

    Needs ``MERITUM_CORPUS_READY`` on (core ``CorpusReadySettings``) and corpus
    ingestion enabled: only the worker that may write the shared corpus (prd)
    owns ``corpus_ready`` too (infra db.sh).

    Returns:
        True only when both are on.

    Features:
        US-KOR-02, F-12
    """
    return ingestion_enabled(os.environ) and CorpusReadySettings().enabled
