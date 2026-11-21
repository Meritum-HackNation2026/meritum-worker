"""What the `check` workflow carries between its steps.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, F-07, F-22
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from meritum_core.checks import CheckRecordRepository, CheckResult, InjectionEvent
from meritum_core.checks.contracts import (
    ClaimDateSource,
    ClaimResult,
    ModelUsage,
)
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.llm import LlmPort, LlmUsage
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.checks.constants import (
    NO_CORPUS_VERSION,
    TECHNICAL_FAILURE_CODE,
    TECHNICAL_FAILURE_MESSAGE,
)


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


type NotAVerdict = Literal["needs_clarification", "out_of_scope", "technical_failure"]
"""Check statuses that carry a message instead of claims."""


@dataclass(frozen=True, slots=True)
class CheckDeps:
    """Ports the steps call; built once by `checks.factory`.

    Attributes:
        llm: the language model, from the core LLM factory.
        records: where the CheckRecord is saved.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """

    llm: LlmPort
    records: CheckRecordRepository


class CheckState(BaseModel):
    """The check so far; every step takes it and returns the next one.

    It crosses each DBOS step as JSON, so it holds only contract models.

    Attributes:
        check_id: the check's id (the DBOS workflow id).
        job: the workflow input, personal data already masked.
        corpus_version: the corpus snapshot searched.
        models: every model call so far.
        web_search_calls: how many web searches ran.
        retrieval_errors: retrieval failures met on the way.
        injection_events: instructions found and neutralised.
        claims: the dated claims to answer, at most MAX_CLAIMS_PER_CHECK.
        limitations: what the check already knows it will not cover.
        result: the answer, once write_answer ran.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    job: CheckInput
    corpus_version: str = NO_CORPUS_VERSION
    models: list[ModelUsage] = []
    web_search_calls: int = 0
    retrieval_errors: list[str] = []
    injection_events: list[InjectionEvent] = []
    claims: list[ExtractedClaim] = []
    limitations: list[str] = []
    result: CheckResult | None = None

    @property
    def question(self) -> str:
        """The masked question: the text, else the link, else the audio id."""
        request = self.job.request
        return request.text or str(request.url or "") or request.audio_id or ""

    def with_message(self, status: NotAVerdict, message: str) -> CheckResult:
        """Build a result that is not a verdict: no claims, a message instead.

        Args:
            status: needs_clarification, out_of_scope or technical_failure.
            message: the copy key channels show.

        Returns:
            The result.
        """
        return CheckResult(
            check_id=self.check_id,
            status=status,
            message=message,
            failure_code=TECHNICAL_FAILURE_CODE if status == "technical_failure" else None,
            corpus_version=self.corpus_version,
        )

    def technical_failure(self) -> CheckResult:
        """Build the technical-failure result: no claims, a message instead.

        Returns:
            The result channels show as „Problem techniczny”.
        """
        return self.with_message("technical_failure", TECHNICAL_FAILURE_MESSAGE)

    def final_result(self) -> CheckResult:
        """The answer, or a technical failure when no step produced one.

        Returns:
            The result the workflow returns and records.
        """
        return self.result or self.technical_failure()


class AnswerDraft(BaseModel):
    """What the model answers in write_answer, before the CheckResult rules apply.

    Attributes:
        claims: one result per claim.
        limitations: what the check could not cover.

    Features:
        US-SPR-01, F-22
    """

    claims: list[ClaimResult]
    limitations: list[str]


def model_usage(usage: LlmUsage) -> ModelUsage:
    """Turn one LLM call's usage into the ModelUsage the CheckRecord keeps.

    Cost stays 0 until the cost step prices the call (worker#26).

    Args:
        usage: provider, model, region and tokens of the call.

    Returns:
        The usage entry.

    Features:
        US-OBS-01, F-22
    """
    return ModelUsage(
        provider=usage.provider,
        model=usage.model,
        region=usage.region,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=0.0,
    )
