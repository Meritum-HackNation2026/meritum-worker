"""The claims the model finds in a check's input.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, F-07, F-22
"""

from datetime import date
from typing import Annotated, Literal

from meritum_core.checks.contracts import ClaimDateSource
from pydantic import BaseModel, ConfigDict, Field


class ExtractedClaim(BaseModel):
    """One claim the model found in the input, before any evidence is searched.

    Attributes:
        claim: the claim as written in the input.
        kind: fact (gets checked), opinion or prediction (not verifiable).
        explanation: why the claim is that kind, in Polish.
        claim_date: the date the claim refers to; None until the step dates it.
        claim_date_source: where the claim date was taken from.

    Features:
        US-SPR-03, US-SPR-06, US-ZRD-05, F-07
    """

    model_config = ConfigDict(frozen=True)

    claim: Annotated[str, Field(min_length=5, max_length=500)]
    kind: Literal["fact", "opinion", "prediction"]
    explanation: Annotated[str, Field(min_length=10, max_length=800)]
    claim_date: date | None = None
    claim_date_source: ClaimDateSource | None = None

    @property
    def is_fact(self) -> bool:
        """Whether the claim gets checked; opinions and predictions do not."""
        return self.kind == "fact"


class ClaimExtraction(BaseModel):
    """What the model answers in extract_claims.

    Attributes:
        out_of_scope: the request is not about information (e.g. „napisz wiersz”).
        claims: every claim in the input, in order; empty when there is none.

    Features:
        US-SPR-03, US-SPR-06, US-ZRD-05, F-07
    """

    out_of_scope: bool
    claims: list[ExtractedClaim]
