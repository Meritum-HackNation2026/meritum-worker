"""What the evidence steps carry: stance answers, citations per fact, the judgement.

Features:
    US-ZRD-01, US-ZRD-04, US-ZRD-08, US-ZRD-09, US-ZRD-10, F-11, F-15, F-16
"""

from datetime import date, datetime
from typing import Annotated, Literal

from meritum_core.checks.contracts import (
    Citation,
    ClaimReviewContext,
    ClaimReviewPremise,
    EvidenceStrength,
    Stance,
    TechniqueCode,
    Verdict,
)
from meritum_core.evidence import CitationDraft
from meritum_core.shared.embeddings import Vector
from pydantic import BaseModel, ConfigDict, Field


class StanceJudgement(BaseModel):
    """What the model answers for one claim-source pair.

    Attributes:
        relevant: whether the source is about the claim at all.
        fragment: the quoted fragment (untrusted until the verbatim check).
        stance: whether the fragment supports, refutes or gives context.
        missing: the part of the claim (a qualifier, number or date) the fragment
            does not confirm; empty when it confirms all of it.

    Features:
        US-ZRD-01, US-ZRD-04, F-15, F-16
    """

    relevant: bool
    fragment: str = ""
    stance: Stance = "context"
    missing: str = ""


class AssessedCitation(BaseModel):
    """A citation the stance call proposed for one fact.

    Attributes:
        fact: the index of the fact among the check's facts.
        draft: the proposed citation, before the verbatim check.

    Features:
        US-ZRD-01, F-15, F-16
    """

    model_config = ConfigDict(frozen=True)

    fact: Annotated[int, Field(ge=0)]
    draft: CitationDraft


class VerifiedCitation(BaseModel):
    """A citation that passed the verbatim check, with metadata from the database.

    Attributes:
        fact: the index of the fact among the check's facts.
        citation: the verified citation with its validity set.

    Features:
        US-ZRD-01, US-ZRD-10, F-15, F-16
    """

    model_config = ConfigDict(frozen=True)

    fact: Annotated[int, Field(ge=0)]
    citation: Citation


class Judgement(BaseModel):
    """The verdict and strength the core rules derive from one fact's citations.

    Attributes:
        verdict: the verdict.
        strength: the strength of a settling verdict, else None.
        citations: the citations the result may show for this verdict.
        technique: ``outdated`` when newer evidence replaced the support.
        archival: whether the agreeing evidence is past its age threshold.
        claim_review_premises: fact-checkers' ratings behind the verdict.
        claim_reviews: fact-checkers' ratings shown as context.

    Features:
        US-ZRD-04, US-ZRD-10, F-15
    """

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    strength: EvidenceStrength | None
    citations: list[Citation]
    technique: TechniqueCode | None
    archival: bool
    claim_review_premises: list[ClaimReviewPremise] = []
    claim_reviews: list[ClaimReviewContext] = []


class ClaimExplanation(BaseModel):
    """What the model writes for one fact in write_answer: text only, no verdict.

    Attributes:
        explanation: the AI interpretation of the citations, in Polish.
        unresolved: what could not be established and which source would settle it.

    Features:
        US-ZRD-02, US-SPR-04, F-15
    """

    explanation: str
    unresolved: str | None = None


class ReviewMatch(BaseModel):
    """What the model answers when it compares a rated claim with ours.

    Attributes:
        same_claim: whether both claims have the same topic, numbers and date.

    Features:
        US-KOR-01, F-14, ADR-34
    """

    same_claim: bool


class IncidentCandidate(BaseModel):
    """A known incident the claim is compared with, from any incident database.

    Attributes:
        database: organiser, euvsdisinfo or fact_check.
        incident_id: the incident's key in that database.
        title: the incident title.
        date: the incident date.
        url: the incident description page, never the disinformation itself.
        domains: domains the incident lists as spreading it (moderators only).
        description_vector: multilingual embedding of the description.
        title_vector: multilingual embedding of the title; None until embedded.

    Features:
        US-ZRD-08, US-ZRD-09, F-11
    """

    model_config = ConfigDict(frozen=True)

    database: Literal["organiser", "euvsdisinfo", "fact_check"]
    incident_id: str
    title: str
    date: datetime
    url: str
    domains: tuple[str, ...] = ()
    description_vector: Vector
    title_vector: Vector | None = None


class IncidentProbe(BaseModel):
    """What one claim brings to the incident comparison.

    Attributes:
        vector: multilingual embedding of the masked claim.
        on: the date of the checked material: the page's, else the claim's.
        domain: the checked link's host without ``www.``; None without a link.

    Features:
        US-ZRD-08, US-ZRD-09, F-11
    """

    model_config = ConfigDict(frozen=True)

    vector: Vector
    on: date
    domain: str | None = None
