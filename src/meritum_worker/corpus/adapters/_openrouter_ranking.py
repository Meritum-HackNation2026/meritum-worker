"""Cohere Rerank through OpenRouter as a reranker, ZDR endpoints only.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-35
"""

from httpx2 import AsyncClient
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RERANK_TOP_K, RankedPassage
from pydantic import BaseModel

from meritum_worker.corpus.adapters._ranking import (
    check_limit,
    post_json,
    rank_by_scores,
)
from meritum_worker.corpus.constants import (
    OPENROUTER_PRIVACY,
    OPENROUTER_RERANK_MODEL,
    OPENROUTER_RERANK_URL,
    RERANK_TIMEOUT_SECONDS,
)
from meritum_worker.corpus.settings import RerankerSettings


class _Result(BaseModel):
    index: int
    relevance_score: float


class _Reply(BaseModel):
    results: list[_Result]


class OpenRouterReranker:
    """RerankerPort on OpenRouter's rerank endpoint (ADR-35).

    Every call asks for ZDR endpoints and no data collection; a model with no
    such endpoint makes OpenRouter refuse the call, which surfaces as
    ``ProviderUnavailableError`` like any other failure, as do failed attempts
    and a reply naming a passage that was not sent. Scores are in [0, 1]. A
    limit below 1 raises ``ValueError``.

    Args:
        settings: Validated ``openrouter`` settings (API key set).
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """

    def __init__(
        self, settings: RerankerSettings, *, http_client: AsyncClient | None = None
    ) -> None:
        self._model = settings.model or OPENROUTER_RERANK_MODEL
        token = settings.token
        secret = "" if token is None else token.get_secret_value()
        self._headers = {"Authorization": f"Bearer {secret}"}
        self._retries = settings.retries
        self._client = http_client or AsyncClient(timeout=RERANK_TIMEOUT_SECONDS)

    async def rerank(
        self, claim: str, passages: list[Passage], *, limit: int = RERANK_TOP_K
    ) -> list[RankedPassage]:
        """Rank ``passages`` against ``claim`` with the OpenRouter model.

        Args:
            claim: The claim, already masked (data, never instructions).
            passages: Passages from the search, best first.
            limit: Most passages to return.

        Returns:
            The ``limit`` most relevant passages; empty, with no call, for none.
        """
        check_limit(limit)
        if not passages:
            return []
        reply = await post_json(
            self._client,
            url=OPENROUTER_RERANK_URL,
            body={
                "model": self._model,
                "query": claim,
                "documents": [p.text for p in passages],
                "top_n": limit,
                "provider": dict(OPENROUTER_PRIVACY),
            },
            headers=self._headers,
            retries=self._retries,
            reply=_Reply,
        )
        scores = ((str(r.index), r.relevance_score) for r in reply.results)
        return rank_by_scores(passages, scores, limit)
