"""Which Fact Check Tools searches a check sends, and how close a rated claim is.

Features:
    US-KOR-01, US-ZRD-03, F-14, F-15, ADR-34
"""

import math
from collections.abc import Sequence

from meritum_core.shared.embeddings import Vector

from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_PHRASES_PER_FACT,
    FACT_CHECK_QUERIES_PER_CHECK,
)


def plan_queries(
    facts: Sequence[str], phrases: Sequence[Sequence[str]]
) -> list[tuple[int, str]]:
    """List the searches: every full claim first, then the phrases round by round.

    Args:
        facts: The checked facts.
        phrases: Each fact's key phrases, in the order of ``facts``.

    Returns:
        The fact's index and the query, without repeats, at most
        FACT_CHECK_QUERIES_PER_CHECK.

    Features:
        US-KOR-01, F-14, ADR-34
    """
    extra = [
        (fact, own[rank])
        for rank in range(FACT_CHECK_PHRASES_PER_FACT)
        for fact, own in enumerate(phrases[: len(facts)])
        if rank < len(own)
    ]
    unique = dict.fromkeys(
        (fact, query.strip()) for fact, query in [*enumerate(facts), *extra]
    )
    return [q for q in unique if q[1]][:FACT_CHECK_QUERIES_PER_CHECK]


def cosine(first: Vector, second: Vector) -> float:
    """Cosine similarity of two vectors; 0 when one is all zeros.

    Args:
        first: One vector.
        second: The other vector.

    Returns:
        The similarity, from -1 to 1.

    Features:
        US-ZRD-03, F-15, ADR-34
    """
    norms = math.hypot(*first) * math.hypot(*second)
    dot = math.fsum(a * b for a, b in zip(first, second, strict=True))
    return dot / norms if norms else 0.0
