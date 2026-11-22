"""A matched fact-checker's rating drives the verdict (worker#280)."""

from datetime import UTC, datetime

import pytest
from meritum_core.checks.contracts import ClaimReviewPremise, Stance, Verdict
from tests.evidence.samples import CLAIM_DATE, FETCHED_AT, cite

from meritum_worker.checks.answers import answer_prompt
from meritum_worker.checks.models import ExtractedClaim
from meritum_worker.evidence import judge


def _rating(rating: str, stance: Stance) -> ClaimReviewPremise:
    return ClaimReviewPremise(
        publisher="Stowarzyszenie Demagog",
        publisher_id="demagog",
        signatory_of=["ifcn"],
        rating=rating,
        title="Darmowa komunikacja. Jaką kwotę musiałby dołożyć Wrocław?",
        reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
        url="https://demagog.org.pl/wypowiedzi/darmowa-komunikacja/",
        fetched_at=FETCHED_AT,
        stance=stance,
    )


@pytest.mark.parametrize(
    ("rating", "stance", "verdict"),
    [
        ("Fałsz", "refutes", "false"),
        ("Prawda", "supports", "confirmed"),
        ("Częściowa prawda", "context", "misleading"),
        ("Manipulacja", "context", "misleading"),
    ],
)
def test_matched_rating_alone_gives_its_verdict_with_the_rating_as_premise(
    rating: str, stance: Stance, verdict: Verdict
) -> None:
    premise = _rating(rating, stance)
    result = judge([], catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    assert result.verdict == verdict
    assert result.strength is not None
    assert result.strength.premises.signatory_reviews == 1
    assert result.claim_review_premises == [premise]


def test_partial_rating_names_the_misleading_technique() -> None:
    premise = _rating("Częściowa prawda", "context")
    result = judge([], catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    assert result.technique == "out_of_context"


def test_partial_rating_next_to_one_sided_sources_stays_misleading() -> None:
    premise = _rating("Częściowa prawda", "context")
    citations = [cite("supports", "um-wroclaw", "primary")]
    result = judge(citations, catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    assert result.verdict == "misleading"


def test_false_rating_against_an_official_source_is_conflicting() -> None:
    premise = _rating("Fałsz", "refutes")
    citations = [cite("supports", "kprm", "primary", domain="gov.pl")]
    result = judge(citations, catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    assert result.verdict == "insufficient_evidence"
    assert result.strength is None
    assert result.citations == citations
    assert result.claim_review_premises == [premise]


def test_partial_rating_with_sources_on_both_sides_is_conflicting() -> None:
    premise = _rating("Częściowa prawda", "context")
    citations = [
        cite("supports", "kprm", "primary", domain="gov.pl"),
        cite("refutes", "gus", "primary", domain="stat.gov.pl", page="b"),
    ]
    result = judge(citations, catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    assert result.verdict == "insufficient_evidence"


def test_answer_prompt_gives_the_rating_with_its_publisher_and_link() -> None:
    premise = _rating("Częściowa prawda", "context")
    judged = judge([], catalog={}, claim_date=CLAIM_DATE, reviews=[premise])
    fact = ExtractedClaim(
        claim="Wrocław wydaje na komunikację około 700 mln zł",
        kind="fact",
        explanation="Kwotę można sprawdzić w budżecie miasta.",
    )
    prompt = answer_prompt("pytanie", [fact], [judged])
    described = prompt.data[1]
    assert "Stowarzyszenie Demagog" in described
    assert "ocena Częściowa prawda" in described
    assert str(premise.url) in described
    assert "fact-checker's rating" in prompt.instructions
