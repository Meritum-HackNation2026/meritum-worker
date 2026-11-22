"""In-process fakes of corpus research for tests and behave: no database, no network.

Features:
    US-SPR-02, US-SPR-04, F-09, F-12
"""

import asyncio
from collections.abc import Sequence
from datetime import date
from typing import TypedDict

from meritum_core.corpus import CorpusSearchPort, NullReranker, Passage, RerankerPort

from meritum_worker.checks.constants import NO_CORPUS_VERSION
from meritum_worker.corpus import CorpusDocumentsPort, DocumentMeta


class FakeCorpusSearch:
    """CorpusSearchPort that finds the same passages for every query.

    Args:
        passages: what every search returns, best first.

    Attributes:
        queries: every query with its claim date, in order.
        limits: the ``limit`` of every query, in order.
        most_at_once: the most searches that were running at the same time.

    Features:
        US-SPR-02, US-SPR-04, F-09, F-12
    """

    def __init__(self, passages: Sequence[Passage] = ()) -> None:
        self.queries: list[tuple[str, date]] = []
        self.limits: list[int] = []
        self.most_at_once = 0
        self._passages = list(passages)
        self._running = 0

    async def search(
        self, query: str, *, claim_date: date, corpus_version: str, limit: int = 20
    ) -> list[Passage]:
        """Note the query, yield once so parallel searches overlap, return passages.

        Args:
            query: the masked claim.
            claim_date: the date the claim is about.
            corpus_version: the pinned snapshot; any is accepted.
            limit: most passages returned.

        Returns:
            The first ``limit`` passages given at construction.
        """
        del corpus_version
        self.queries.append((query, claim_date))
        self.limits.append(limit)
        self._running += 1
        self.most_at_once = max(self.most_at_once, self._running)
        await asyncio.sleep(0)
        self._running -= 1
        return self._passages[:limit]


class FakeCorpusDocuments:
    """CorpusDocumentsPort over the metadata given at construction.

    Args:
        documents: the documents the corpus holds.

    Features:
        US-KOR-02, US-ZRD-01, F-12, F-16
    """

    def __init__(self, documents: Sequence[DocumentMeta] = ()) -> None:
        self._documents = {d.source_id: d for d in documents}

    async def document(self, source_id: str) -> DocumentMeta | None:
        """Return the document given at construction, if any.

        Args:
            source_id: the document.

        Returns:
            Its metadata, or None.
        """
        await asyncio.sleep(0)
        return self._documents.get(source_id)


class CorpusPorts(TypedDict):
    """The CheckDeps ports of corpus research, for ``CheckDeps(**corpus_ports())``.

    Attributes:
        corpus: the fake search.
        reranker: core's null gate, which keeps the search order.
        corpus_version: the pinned snapshot.
        corpus_documents: the fake documents the passages come from.

    Features:
        US-SPR-02, US-SPR-04, F-09, F-12
    """

    corpus: CorpusSearchPort
    reranker: RerankerPort
    corpus_version: str
    corpus_documents: CorpusDocumentsPort


def corpus_ports(
    passages: Sequence[Passage] = (),
    *,
    version: str = NO_CORPUS_VERSION,
    documents: Sequence[DocumentMeta] = (),
) -> CorpusPorts:
    """A fake corpus search, the null reranker and a pinned snapshot.

    Args:
        passages: what every search finds.
        version: the snapshot; NO_CORPUS_VERSION (default) skips search_corpus.
        documents: the metadata of the documents the passages come from.

    Returns:
        The ports.

    Features:
        US-SPR-02, US-SPR-04, F-09, F-12
    """
    return CorpusPorts(
        corpus=FakeCorpusSearch(passages),
        reranker=NullReranker(),
        corpus_version=version,
        corpus_documents=FakeCorpusDocuments(documents),
    )
