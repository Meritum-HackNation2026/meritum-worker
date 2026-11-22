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
        claim_en: the claim in English, for English-language sources; None when
            the claim is already English.
        search_queries: up to 3 web search queries the model wrote for the claim:
            key entities, numbers and dates, in Polish and English; empty when
            the model gave none.
        fact_check_phrases: up to 4 short Polish key phrases of a fact for the
            fact-checkers' index, which matches phrases literally: the names of
            people, institutions and places and the numbers (worker#84); empty
            when the model gave none.
        kind: fact (gets checked), opinion or prediction (not verifiable).
        explanation: why the claim is that kind, in Polish.
        claim_date: the date the claim refers to; None until the step dates it.
        claim_date_source: where the claim date was taken from.

    Features:
        US-SPR-03, US-SPR-06, US-ZRD-05, US-KOR-06, F-07, F-35
    """

    model_config = ConfigDict(frozen=True)

    claim: Annotated[str, Field(min_length=5, max_length=500)]
    claim_en: Annotated[str, Field(min_length=5, max_length=500)] | None = None
    search_queries: Annotated[
        list[Annotated[str, Field(min_length=3, max_length=200)]],
        Field(max_length=3),
    ] = []  # pydantic copies the default per instance
    # No length cap on the list: a fifth phrase must not fail the extraction;
    # the search takes FACT_CHECK_PHRASES_PER_FACT.
    fact_check_phrases: list[Annotated[str, Field(min_length=3, max_length=200)]] = []
    kind: Literal["fact", "opinion", "prediction"]
    explanation: Annotated[str, Field(min_length=10, max_length=800)]
    claim_date: date | None = None
    claim_date_source: ClaimDateSource | None = None

    @property
    def queries(self) -> list[str]:
        """The claim as a search query in each language, Polish first."""
        return list(dict.fromkeys([self.claim, self.claim_en or self.claim]))

    @property
    def web_queries(self) -> list[str]:
        """What the web search gets: the model's keyword queries, else the claim."""
        return list(dict.fromkeys(self.search_queries)) or self.queries

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
