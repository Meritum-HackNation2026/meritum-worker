"""What the worker evidence rules return per fact.

Features:
    US-ZRD-04, US-ZRD-05, US-ZRD-10, F-15, ADR-05, ADR-25
"""

from typing import Annotated

from meritum_core.checks.contracts import (
    Citation,
    EvidenceStrength,
    TechniqueCode,
    Verdict,
)
from pydantic import BaseModel, ConfigDict, Field


class VerifiedCitation(BaseModel):
    """A citation past the verbatim check, tied to one fact.

    Attributes:
        fact: the index of the fact among the check's facts.
        citation: the verified citation with validity set at the claim date.

    Features:
        US-ZRD-01, US-ZRD-10, F-15
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

    Features:
        US-ZRD-04, US-ZRD-10, F-15, ADR-05
    """

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    strength: EvidenceStrength | None
    citations: list[Citation]
    technique: TechniqueCode | None
    archival: bool
