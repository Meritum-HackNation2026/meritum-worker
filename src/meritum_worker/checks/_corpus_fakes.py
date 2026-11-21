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


class FakeCorpusSearch:
    """CorpusSearchPort that finds the same passages for every query.

    Args:
        passages: what every search returns, best first.

    Attributes:
        queries: every query with its claim date, in order.
        most_at_once: the most searches that were running at the same time.

    Features:
        US-SPR-02, US-SPR-04, F-09, F-12
    """

    def __init__(self, passages: Sequence[Passage] = ()) -> None:
        self.queries: list[tuple[str, date]] = []
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
        self._running += 1
        self.most_at_once = max(self.most_at_once, self._running)
        await asyncio.sleep(0)
        self._running -= 1
        return self._passages[:limit]


class CorpusPorts(TypedDict):
    """The CheckDeps ports of corpus research, for ``CheckDeps(**corpus_ports())``.

    Attributes:
        corpus: the fake search.
        reranker: core's null gate, which keeps the search order.
        corpus_version: the pinned snapshot.

    Features:
        US-SPR-04, F-12
    """

    corpus: CorpusSearchPort
    reranker: RerankerPort
    corpus_version: str


def corpus_ports(
    passages: Sequence[Passage] = (), *, version: str = NO_CORPUS_VERSION
) -> CorpusPorts:
    """A fake corpus search, the null reranker and a pinned snapshot.

    Args:
        passages: what every search finds.
        version: the snapshot; NO_CORPUS_VERSION (default) skips search_corpus.

    Returns:
        The ports.

    Features:
        US-SPR-04, F-12
    """
    return CorpusPorts(
        corpus=FakeCorpusSearch(passages),
        reranker=NullReranker(),
        corpus_version=version,
    )
