"""Vertex AI ranking API (``rankingConfigs:rank``) as a reranker.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-14, ADR-35
"""

import asyncio

from google.auth import default as adc_lookup
from google.auth.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from httpx2 import AsyncClient
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RERANK_TOP_K, RankedPassage
from meritum_core.shared.llm import ProviderUnavailableError
from pydantic import BaseModel

from meritum_worker.corpus.adapters._ranking import (
    check_limit,
    post_json,
    rank_by_scores,
)
from meritum_worker.corpus.constants import (
    RERANK_TIMEOUT_SECONDS,
    VERTEX_RANKING_HOST,
    VERTEX_RANKING_LOCATION,
    VERTEX_RANKING_MODEL,
    VERTEX_RANKING_SCOPES,
)
from meritum_worker.corpus.settings import RerankerSettings


class _Record(BaseModel):
    id: str
    score: float


class _Reply(BaseModel):
    records: list[_Record]


def _url(project: str, location: str) -> str:
    is_global = location == VERTEX_RANKING_LOCATION
    host = VERTEX_RANKING_HOST if is_global else f"{location}-{VERTEX_RANKING_HOST}"
    return (
        f"https://{host}/v1/projects/{project}/locations/{location}"
        "/rankingConfigs/default_ranking_config:rank"
    )


class VertexReranker:
    """RerankerPort on the Vertex AI ranking API (semantic ranker, ADR-35).

    Each passage goes as a record whose id is its index; only ids and scores
    come back. Scores are 0 to 1. A limit below 1 raises ``ValueError``; refused
    credentials, failed attempts or a reply naming a passage that was not sent
    raise ``ProviderUnavailableError``.

    Args:
        settings: Validated ``vertex`` settings (project set).
        credentials: Google credentials; Application Default Credentials when None.
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-14, ADR-35
    """

    def __init__(
        self,
        settings: RerankerSettings,
        *,
        credentials: Credentials | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        self._project = str(settings.project)
        self._model = settings.model or VERTEX_RANKING_MODEL
        self._retries = settings.retries
        self._credentials = credentials
        self._client = http_client or AsyncClient(timeout=RERANK_TIMEOUT_SECONDS)
        self._url = _url(self._project, settings.location)

    async def rerank(
        self, claim: str, passages: list[Passage], *, limit: int = RERANK_TOP_K
    ) -> list[RankedPassage]:
        """Rank ``passages`` against ``claim`` with the semantic ranker.

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
        token = await self._token()
        reply = await post_json(
            self._client,
            url=self._url,
            body={
                "model": self._model,
                "query": claim,
                "records": [
                    {"id": str(index), "content": p.text}
                    for index, p in enumerate(passages)
                ],
                "topN": limit,
                "ignoreRecordDetailsInResponse": True,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Goog-User-Project": self._project,
            },
            retries=self._retries,
            reply=_Reply,
        )
        return rank_by_scores(passages, ((r.id, r.score) for r in reply.records), limit)

    async def _token(self) -> str:
        try:
            if self._credentials is None:
                self._credentials, _ = await asyncio.to_thread(
                    adc_lookup, scopes=VERTEX_RANKING_SCOPES
                )
            credentials = self._credentials
            if not credentials.valid:
                await asyncio.to_thread(credentials.refresh, Request())
        except GoogleAuthError as exc:
            msg = "reranker credentials were refused"
            raise ProviderUnavailableError(msg) from exc
        return str(credentials.token)
