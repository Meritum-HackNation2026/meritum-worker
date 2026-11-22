"""Fact-checkers' ratings as premises: does the rated claim match ours (ADR-34).

Features:
    US-KOR-01, F-14, ADR-24, ADR-34
"""

from collections.abc import Sequence
from datetime import date

from meritum_core.checks.contracts import ClaimReviewContext, ClaimReviewPremise
from meritum_core.shared.llm import LlmPort, LlmUsage, Prompt

from meritum_worker.evidence.constants import REVIEW_MATCH_INSTRUCTIONS
from meritum_worker.evidence.models import ReviewMatch


async def review_matches(
    llm: LlmPort, claim: str, claim_date: date, claim_reviewed: str
) -> tuple[bool, LlmUsage]:
    """Ask the model whether the claim a fact-checker rated is ours.

    Args:
        llm: the language model.
        claim: our claim as extracted.
        claim_date: the date our claim refers to.
        claim_reviewed: the rated claim, as the API returned it (untrusted).

    Returns:
        Whether topic, numbers and date agree, and the call's usage.

    A model failure propagates.

    Features:
        US-KOR-01, F-14, ADR-34
    """
    prompt = Prompt(
        instructions=REVIEW_MATCH_INSTRUCTIONS,
        data=(claim, claim_date.isoformat(), claim_reviewed),
    )
    answer = await llm.complete(prompt, ReviewMatch)
    return answer.output.same_claim, answer.usage


def split_reviews(
    ratings: Sequence[tuple[bool, ClaimReviewPremise | ClaimReviewContext]],
) -> tuple[list[ClaimReviewPremise], list[ClaimReviewContext]]:
    """Keep one rating per URL and publisher, preferring a matching premise.

    Args:
        ratings: each rating after the rating rule, with whether the model found
            the rated claim to be ours.

    Returns:
        The premises and the context ratings.

    Features:
        US-KOR-01, F-14, ADR-34
    """
    premises: dict[tuple[str, str], ClaimReviewPremise] = {}
    context: dict[tuple[str, str], ClaimReviewContext] = {}
    for same, rating in ratings:
        key = (str(rating.url), rating.publisher)
        if same and isinstance(rating, ClaimReviewPremise):
            premises.setdefault(key, rating)
        else:
            context.setdefault(
                key,
                rating if isinstance(rating, ClaimReviewContext) else _context(rating),
            )
    return list(premises.values()), [
        rating for key, rating in context.items() if key not in premises
    ]


def _context(premise: ClaimReviewPremise) -> ClaimReviewContext:
    return ClaimReviewContext(
        publisher=premise.publisher,
        rating=premise.rating,
        url=premise.url,
        reviewed_at=premise.reviewed_at,
    )
