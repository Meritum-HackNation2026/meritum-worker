"""Which open cases and earlier checks already hold a claim (per claim, US-MOD-02).

Features:
    US-MOD-02, F-24
"""

from collections.abc import Sequence

from meritum_core.checks.contracts import ModeratorCase
from meritum_core.shared.embeddings import EmbeddingsPort, EmbeddingsUnavailableError

from meritum_worker.moderation.constants import SIMILARITY_THRESHOLD
from meritum_worker.moderation.models import PastClaim
from meritum_worker.moderation.similarity import cosine, facts_agree


async def similar_flags(
    claim: str, texts: Sequence[str], embeddings: EmbeddingsPort
) -> list[bool]:
    """Say for each text whether it is the same claim as ``claim``.

    The same words always match; otherwise the embeddings must be at least
    SIMILARITY_THRESHOLD close and the numbers, months and names must agree.
    When the embeddings are unavailable only the same words match.

    Args:
        claim: the new claim.
        texts: the claims to compare it with.
        embeddings: the embeddings port.

    Returns:
        One flag per text, in order.

    Features:
        US-MOD-02, F-24
    """
    same = [claim.casefold() == t.casefold() for t in texts]
    if not texts or all(same):
        return same
    try:
        vectors = await embeddings.embed_documents([claim, *texts])
    except EmbeddingsUnavailableError:
        return same
    return [
        s
        or (
            cosine(vectors[0], vector) >= SIMILARITY_THRESHOLD
            and facts_agree(claim, text)
        )
        for s, text, vector in zip(same, texts, vectors[1:], strict=True)
    ]


async def similar_case(
    claim: str, cases: Sequence[ModeratorCase], embeddings: EmbeddingsPort
) -> tuple[ModeratorCase, int] | None:
    """Find the first case (latest first) that groups a claim like ``claim``.

    Args:
        claim: the new claim.
        cases: open cases, latest first.
        embeddings: the embeddings port.

    Returns:
        The case and the index of its matching claim, or None.

    Features:
        US-MOD-02, F-24
    """
    located = [(case, i) for case in cases for i in range(len(case.claims))]
    flags = await similar_flags(
        claim, [case.claims[i].claim for case, i in located], embeddings
    )
    return next(
        (place for place, flag in zip(located, flags, strict=True) if flag), None
    )


async def similar_past(
    claim: str, past: Sequence[PastClaim], embeddings: EmbeddingsPort
) -> list[PastClaim]:
    """Pick the earlier unanswered claims that are the same as ``claim``.

    Args:
        claim: the new claim.
        past: earlier unanswered claims of other checks.
        embeddings: the embeddings port.

    Returns:
        The matching ones.

    Features:
        US-MOD-02, F-24
    """
    flags = await similar_flags(claim, [p.claim for p in past], embeddings)
    return [p for p, flag in zip(past, flags, strict=True) if flag]
