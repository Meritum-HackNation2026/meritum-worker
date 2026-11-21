"""Shared parts of the reranker adapters: the limit, the POST and the ranking.

A failed POST or a reply naming a passage that was not sent raises
``ProviderUnavailableError``, the port's error; the caller keeps the search order.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-35
"""

import asyncio
from collections.abc import Iterable
from operator import itemgetter

from httpx2 import AsyncClient, RequestError, TransportError, codes
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RankedPassage
from meritum_core.shared.llm import ProviderUnavailableError
from pydantic import BaseModel, JsonValue, ValidationError

from meritum_worker.corpus.constants import RERANK_RETRY_BACKOFF_SECONDS


def check_limit(limit: int) -> None:
    """Reject a limit below 1, as the port requires.

    Args:
        limit: Most passages to return.

    Raises:
        ValueError: ``limit`` is below 1.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """
    if limit < 1:
        msg = f"limit must be at least 1, got {limit}"
        raise ValueError(msg)


def _is_transient(status: int) -> bool:
    return status == codes.TOO_MANY_REQUESTS or status >= codes.INTERNAL_SERVER_ERROR


async def post_json[T: BaseModel](  # ruff: ignore[too-many-arguments]  # one call site per adapter, all keyword
    client: AsyncClient,
    *,
    url: str,
    body: dict[str, JsonValue],
    headers: dict[str, str],
    retries: int,
    reply: type[T],
) -> T:
    """POST ``body`` and parse the first successful reply, retrying transient errors.

    Args:
        client: The HTTP client.
        url: Provider endpoint.
        body: JSON request body.
        headers: Auth headers.
        retries: Attempts, the first included.
        reply: Model of the provider's reply.

    Returns:
        The parsed reply.

    Raises:
        ProviderUnavailableError: Every attempt failed, the provider refused the
            request or the reply did not parse; the message holds no claim text.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """
    last = "no reply"
    for attempt in range(retries):
        if attempt:
            await asyncio.sleep(RERANK_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))
        try:
            response = await client.post(url, json=body, headers=headers)
        except TransportError as exc:
            last = f"{type(exc).__name__} on attempt {attempt + 1}"
            continue
        except RequestError as exc:  # undecodable body, redirects: not transient
            last = f"{type(exc).__name__} on attempt {attempt + 1}"
            break
        last = f"HTTP {response.status_code} on attempt {attempt + 1}"
        if response.is_success:
            try:
                return reply.model_validate_json(response.content)
            except ValidationError:
                last = "reply did not parse"
                break
        if not _is_transient(response.status_code):
            break
    msg = f"reranker unavailable ({last})"
    raise ProviderUnavailableError(msg)


def rank_by_scores(
    passages: list[Passage], scores: Iterable[tuple[str, float]], limit: int
) -> list[RankedPassage]:
    """Map the provider's scores back to passages, best first, cut to ``limit``.

    Args:
        passages: The passages sent; a score's id is the passage's index.
        scores: Pairs of the index as text and the provider's score.
        limit: Most passages to return.

    Returns:
        The ``limit`` best passages, each once, with non-increasing relevance.

    Raises:
        ProviderUnavailableError: A score names a passage that was not sent.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """
    by_id = {str(index): passage for index, passage in enumerate(passages)}
    best: dict[str, float] = {}
    for record_id, score in scores:
        if record_id not in by_id:
            msg = "reranker ranked a passage it was not sent"
            raise ProviderUnavailableError(msg)
        best[record_id] = max(score, best.get(record_id, score))
    order = sorted(best.items(), key=itemgetter(1), reverse=True)
    return [
        RankedPassage(passage=by_id[record_id], relevance=score)
        for record_id, score in order[:limit]
    ]
