"""Reranking in the research step: a provider failure falls back to the search order."""

import asyncio
from datetime import UTC, date, datetime

from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RankedPassage
from meritum_core.corpus.rerank.fakes import FakeReranker
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.corpus import rerank_passages

CLAIM = "Sejm przyjął ustawę o ochronie zwierząt."


def _passages(count: int) -> list[Passage]:
    return [
        Passage(
            passage_id=f"p{i}",
            source_id=f"src-{i}",
            text=f"Fragment {i}.",
            published_on=date(2026, 11, 1),
            fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
            score=1 - i / 100,
        )
        for i in range(count)
    ]


class _BrokenReranker:
    async def rerank(  # ruff: ignore[no-self-use]  # same signature as the port
        self, claim: str, passages: list[Passage], *, limit: int = 5
    ) -> list[RankedPassage]:
        msg = f"reranker down for {len(passages)} passages, limit {limit}, {claim}"
        raise ProviderUnavailableError(msg)


def test_ranked_passages_come_back_without_errors() -> None:
    reranker = FakeReranker({"p7": 0.9, "p3": 0.8})
    result = asyncio.run(rerank_passages(reranker, CLAIM, _passages(20)))
    assert [r.passage.passage_id for r in result.passages][:2] == ["p7", "p3"]
    assert len(result.passages) == 5
    assert result.retrieval_errors == []


def test_provider_failure_keeps_the_search_order_and_records_the_error() -> None:
    result = asyncio.run(rerank_passages(_BrokenReranker(), CLAIM, _passages(20)))
    assert [r.passage.passage_id for r in result.passages] == [
        f"p{i}" for i in range(5)
    ]
    assert result.retrieval_errors == ["search_corpus: reranker_unavailable"]
