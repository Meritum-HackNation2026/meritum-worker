"""Google Fact Check Tools API (``claims:search``): ClaimReview ratings by phrase.

The API matches phrases literally; recall is worker#84's job, the query stays
the plain claim.

Features:
    US-KOR-01, US-BEZ-03, F-14, F-18, ADR-24, ADR-34
"""

from httpx2 import AsyncClient, HTTPError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from meritum_worker.corpus.errors import FactCheckUnavailableError
from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_NO_KEY,
    FACT_CHECK_TIMEOUT_SECONDS,
    FACT_CHECK_URL,
)
from meritum_worker.corpus.models import FactCheckAnswer, FactCheckHit


class GoogleFactCheck:
    """FactCheckPort over ``factchecktools.googleapis.com``.

    Args:
        api_key: The API key, sent in the ``X-Goog-Api-Key`` header, never in the
            URL; empty fails every search as unavailable.
        http_client: The HTTP client, owned by the caller; None: one with the timeout.

    Features:
        US-KOR-01, F-14, ADR-24, ADR-34
    """

    def __init__(self, api_key: str, http_client: AsyncClient | None = None) -> None:
        self._key = api_key
        self._http = http_client or AsyncClient(timeout=FACT_CHECK_TIMEOUT_SECONDS)

    async def search(self, query: str, *, language: str) -> FactCheckAnswer:
        """Return the reviews of the claims the API matches to ``query``.

        Args:
            query: The masked claim.
            language: ISO 639-1 code of the claim's language.

        Returns:
            The reviews with the response's cache header; none for an empty answer.

        Raises:
            FactCheckUnavailableError: No key, HTTP failure, quota or key refused,
                or an unreadable answer.
        """
        if not self._key:
            raise FactCheckUnavailableError(FACT_CHECK_NO_KEY)
        try:
            response = await self._http.get(
                FACT_CHECK_URL,
                params={"query": query, "languageCode": language},
                headers={"X-Goog-Api-Key": self._key},
            )
            response.raise_for_status()
            found = _Claims.model_validate_json(response.content)
        except (HTTPError, ValidationError, ValueError) as error:
            # The reason is the error's type: its text may hold the URL or key.
            raise FactCheckUnavailableError(type(error).__name__) from error
        hits = [
            FactCheckHit(
                claim_reviewed=claim.text,
                site=review.publisher.site,
                publisher=review.publisher.name,
                rating=review.rating,
                title=review.title,
                url=review.url,
                reviewed_at=review.reviewed_at,
            )
            for claim in found.claims
            for review in claim.reviews
        ]
        return FactCheckAnswer(
            hits=hits, cache_control=response.headers.get("cache-control")
        )


class _Publisher(BaseModel):
    name: str = ""
    site: str = ""


class _Review(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    publisher: _Publisher = _Publisher()
    url: str
    title: str = ""
    rating: str = Field(alias="textualRating")
    reviewed_at: str | None = Field(default=None, alias="reviewDate")


class _Claim(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str = ""
    reviews: list[_Review] = Field(default=[], alias="claimReview")


class _Claims(BaseModel):
    claims: list[_Claim] = []
