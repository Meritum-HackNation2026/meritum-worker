"""bge-reranker in Cloudflare Workers AI as a reranker, called over REST.

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
    RERANK_TIMEOUT_SECONDS,
    WORKERS_AI_RERANK_ENDPOINT,
    WORKERS_AI_RERANK_MODEL,
)
from meritum_worker.corpus.settings import RerankerSettings


class _Score(BaseModel):
    id: int
    score: float


class _Result(BaseModel):
    response: list[_Score]


class _Reply(BaseModel):
    result: _Result


class WorkersAiReranker:
    """RerankerPort on a bge cross-encoder in Cloudflare Workers AI (ADR-35).

    Scores are raw logits (higher is more relevant), comparable only within one
    reranking, as ``RankedPassage.relevance`` allows. A limit below 1 raises
    ``ValueError``; failed attempts or a reply naming a passage that was not
    sent raise ``ProviderUnavailableError``.

    Args:
        settings: Validated ``workers_ai`` settings (account and token set).
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """

    def __init__(
        self, settings: RerankerSettings, *, http_client: AsyncClient | None = None
    ) -> None:
        model = settings.model or WORKERS_AI_RERANK_MODEL
        self._url = f"{WORKERS_AI_RERANK_ENDPOINT}/{settings.account_id}/ai/run/{model}"
        token = settings.api_token
        secret = "" if token is None else token.get_secret_value()
        self._headers = {"Authorization": f"Bearer {secret}"}
        self._retries = settings.retries
        self._client = http_client or AsyncClient(timeout=RERANK_TIMEOUT_SECONDS)

    async def rerank(
        self, claim: str, passages: list[Passage], *, limit: int = RERANK_TOP_K
    ) -> list[RankedPassage]:
        """Rank ``passages`` against ``claim`` with the bge reranker.

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
            url=self._url,
            body={
                "query": claim,
                "contexts": [{"text": p.text} for p in passages],
                "top_k": limit,
            },
            headers=self._headers,
            retries=self._retries,
            reply=_Reply,
        )
        scores = ((str(s.id), s.score) for s in reply.result.response)
        return rank_by_scores(passages, scores, limit)
