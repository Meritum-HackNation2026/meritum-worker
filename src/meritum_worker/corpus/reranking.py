"""Reranking in the research step: a provider failure keeps the search order.

The reranker is a cheap gate, not a source of evidence (ADR-35), so its failure
is not a failure of the check: the passages stay in search order and the error
goes to ``retrieval_errors``.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-35
"""

import logging

from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RERANK_TOP_K, RankedPassage, RerankerPort
from meritum_core.shared.llm import ProviderUnavailableError
from pydantic import BaseModel, ConfigDict

from meritum_worker.corpus.constants import RERANK_FAILED_ERROR

_log = logging.getLogger(__name__)


class Reranking(BaseModel):
    """What the research step gets from the reranker for one claim.

    Attributes:
        passages: The passages to assess, most relevant first.
        retrieval_errors: Errors for ``CheckRecord.retrieval_errors``; empty
            when the reranker answered.

    Features:
        US-KOR-02, US-SPR-04, F-12
    """

    model_config = ConfigDict(frozen=True)

    passages: list[RankedPassage]
    retrieval_errors: list[str] = []


async def rerank_passages(
    reranker: RerankerPort,
    claim: str,
    passages: list[Passage],
    *,
    limit: int = RERANK_TOP_K,
) -> Reranking:
    """Rerank ``passages``; on a provider failure keep the search order.

    Args:
        reranker: The configured reranker (``build_reranker``).
        claim: The claim, already masked.
        passages: Passages from the search, best first.
        limit: Most passages to keep.

    Returns:
        The reranked passages, or the first ``limit`` in search order (relevance
        1, 1/2, 1/3, ...) with ``RERANK_FAILED_ERROR`` when the provider failed.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """
    try:
        return Reranking(passages=await reranker.rerank(claim, passages, limit=limit))
    except ProviderUnavailableError as error:
        _log.warning("reranker failed (%s); search order kept", error)
    kept = [
        RankedPassage(passage=p, relevance=1 / rank)
        for rank, p in enumerate(passages[:limit], start=1)
    ]
    return Reranking(passages=kept, retrieval_errors=[RERANK_FAILED_ERROR])
