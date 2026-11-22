"""corpus_ready build: bronze ``corpus.documents`` become silver text and gold chunks.

Silver cleaning is deterministic; gold chunks keep a pointer to the bronze
``source_id`` and character offsets, so every citation can be checked against
the raw text. Runs only as its own DBOS workflow with ``MERITUM_CORPUS_READY``
on (core ``CorpusReadySettings``); core's ``build_corpus_search`` reads gold.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

from meritum_worker.corpus.ready.build import (
    ReadyDeps,
    build_enabled,
    build_ready_layer,
)
from meritum_worker.corpus.ready.constants import (
    BUILD_SCHEDULE,
    BUILD_STEP,
    BUILD_WORKFLOW,
)
from meritum_worker.corpus.ready.factory import build_ready_deps
from meritum_worker.corpus.ready.gold import gold_chunks, number_tags
from meritum_worker.corpus.ready.models import BronzeDocument, BuildReport, Span
from meritum_worker.corpus.ready.silver import clean, paragraphs, silver_text

__all__ = [
    "BUILD_SCHEDULE",
    "BUILD_STEP",
    "BUILD_WORKFLOW",
    "BronzeDocument",
    "BuildReport",
    "ReadyDeps",
    "Span",
    "build_enabled",
    "build_ready_deps",
    "build_ready_layer",
    "clean",
    "gold_chunks",
    "number_tags",
    "paragraphs",
    "silver_text",
]
