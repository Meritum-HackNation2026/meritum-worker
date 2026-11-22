"""CorpusSearchPort and RerankerPort that record answers or replay them.

A replayed run reads the passages the recording saw, so it needs neither the
corpus database nor the embeddings and reranker providers.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-19, ADR-28
"""

import asyncio
import hashlib
from datetime import date

from meritum_core.corpus import (
    CorpusSearchPort,
    CorpusUnavailableError,
    Passage,
    RankedPassage,
    UnknownCorpusVersionError,
)
from meritum_core.corpus.constants import DEFAULT_LIMIT
from meritum_core.corpus.rerank import RerankerPort
from meritum_core.corpus.rerank.constants import RERANK_TOP_K
from meritum_core.shared.embeddings import EmbeddingsUnavailableError
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, CorpusTake, RerankTake

type _SearchError = (
    UnknownCorpusVersionError | CorpusUnavailableError | EmbeddingsUnavailableError
)


def _failure(name: str) -> type[_SearchError]:
    known = (UnknownCorpusVersionError, EmbeddingsUnavailableError)
    return next((e for e in known if e.__name__ == name), CorpusUnavailableError)


def _key(*parts: object) -> str:
    return hashlib.sha256(repr(parts).encode()).hexdigest()


class CassetteCorpus:
    """Records each corpus search, or replays them when ``corpus`` is None.

    Args:
        cassette: Where searches are recorded or read from.
        corpus: The hybrid search to record; None replays without the database.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-19, ADR-28
    """

    def __init__(self, cassette: Cassette, corpus: CorpusSearchPort | None) -> None:
        self._tape = Tape(cassette.corpus)
        self._corpus = corpus

    async def search(
        self,
        query: str,
        *,
        claim_date: date,
        corpus_version: str,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Passage]:
        """Search the snapshot (recording it) or answer from the cassette.

        Args:
            query: The masked claim.
            claim_date: The date the claim is about.
            corpus_version: The pinned snapshot.
            limit: Most passages to return.

        Returns:
            Passages, best first.

        Raises:
            UnknownCorpusVersionError: No such snapshot, now or when recorded.
            CorpusUnavailableError: The store failed, now or when recorded.
            EmbeddingsUnavailableError: The query was not embedded.
            CassetteMissError: Replay found no recorded search for this query.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = _key(query, claim_date.isoformat(), corpus_version, limit)
        if self._corpus is None:
            take = self._tape.next(key)
            if take.failure is not None:
                raise _failure(take.failure)(key)
            return list(take.passages)
        try:
            passages = await self._corpus.search(
                query, claim_date=claim_date, corpus_version=corpus_version, limit=limit
            )
        except asyncio.CancelledError:
            self._tape.record_timeout(key)
            raise
        except (
            UnknownCorpusVersionError,
            CorpusUnavailableError,
            EmbeddingsUnavailableError,
        ) as error:
            self._tape.record(key, CorpusTake(failure=type(error).__name__))
            raise
        self._tape.record(key, CorpusTake(passages=tuple(passages)))
        return passages


class CassetteReranker:
    """Records each reranking, or replays them when ``reranker`` is None.

    The cassette keeps passage ids and relevance only; replay ranks the
    passages it is given, which are the recorded search's.

    Args:
        cassette: Where rankings are recorded or read from.
        reranker: The reranker to record; None replays without its provider.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-35, ADR-28
    """

    def __init__(self, cassette: Cassette, reranker: RerankerPort | None) -> None:
        self._tape = Tape(cassette.rerank)
        self._reranker = reranker

    async def rerank(
        self, claim: str, passages: list[Passage], *, limit: int = RERANK_TOP_K
    ) -> list[RankedPassage]:
        """Rerank (recording it) or answer from the cassette.

        Args:
            claim: The masked claim.
            passages: Passages from the search, best first.
            limit: Most passages to return.

        Returns:
            Passages from ``passages`` with their relevance, best first.

        Raises:
            ProviderUnavailableError: The provider failed, now or when recorded.
            CassetteMissError: Replay found no recorded ranking for this call.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = _key(claim, tuple(p.passage_id for p in passages), limit)
        if self._reranker is None:
            take = self._tape.next(key)
            if take.ranked is None:
                raise ProviderUnavailableError(key)
            by_id = {p.passage_id: p for p in passages}
            return [
                RankedPassage(passage=by_id[i], relevance=r) for i, r in take.ranked
            ]
        try:
            ranked = await self._reranker.rerank(claim, passages, limit=limit)
        except asyncio.CancelledError:
            self._tape.record_timeout(key)
            raise
        except ProviderUnavailableError:
            self._tape.record(key, RerankTake())
            raise
        pairs = tuple((r.passage.passage_id, r.relevance) for r in ranked)
        self._tape.record(key, RerankTake(ranked=pairs))
        return ranked
