"""What the `check` workflow carries between its steps.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, F-07, F-22
"""

from datetime import date
from typing import Literal

from meritum_core.checks import CheckResult, InjectionEvent
from meritum_core.checks.constants import MIN_TEXT_CHARS
from meritum_core.checks.contracts import (
    FailureCode,
    LimitationCode,
    ModelUsage,
    OutOfScopeCode,
)
from meritum_core.checks.ocr import ImageInfo
from meritum_core.corpus import RankedPassage
from meritum_core.evidence.models import SourceDocument
from meritum_core.jobs.contracts import CheckInput
from pydantic import BaseModel, ConfigDict

from meritum_worker.checks.constants import (
    NO_CORPUS_VERSION,
    TECHNICAL_FAILURE_CODE,
    TECHNICAL_FAILURE_MESSAGE,
)
from meritum_worker.checks.models.claims import ExtractedClaim
from meritum_worker.corpus import ClaimReviewFinding
from meritum_worker.evidence import AssessedCitation, VerifiedCitation

type NotAVerdict = Literal["needs_clarification", "out_of_scope", "technical_failure"]
"""Check statuses that carry a message instead of claims."""


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
        page_text: the masked main text of the linked page, once fetch_url read it.
        published_at: the linked page's publication date from its metadata, if any.
        transcript: the masked automatic transcript, once transcribe_audio ran.
        audio_seconds: the recording's length, once transcribe_audio read it.
        image_text: the masked OCR text, once read_image ran.
        image_date: the first date written in the image's text.
        image_info: the image file's format and size; context only, never read
            by the verdict.
        image_notes: limitations of an image check, each with its code.
        skipped_steps: step codes that had nothing to do for this input.
        claims: the dated claims to answer, at most MAX_CLAIMS_PER_CHECK.
        evidence: source documents found for the claims, each past quarantine.
        passages: reranked corpus passages per fact, keyed by the claim text.
        assessed: citations the stance calls proposed, per fact.
        citations: citations past the verbatim check, per fact.
        fact_checks: fact-checkers' ratings found for the facts.
        same_claim_reviews: positions in fact_checks of ratings of our claim.
        failed_steps: step codes that failed without ending the check.
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
    page_text: str | None = None
    published_at: date | None = None
    transcript: str | None = None
    audio_seconds: float | None = None
    image_text: str | None = None
    image_date: date | None = None
    image_info: ImageInfo | None = None
    image_notes: list[tuple[LimitationCode, str]] = []
    skipped_steps: list[str] = []
    claims: list[ExtractedClaim] = []
    evidence: list[SourceDocument] = []
    passages: dict[str, list[RankedPassage]] = {}
    assessed: list[AssessedCitation] = []
    citations: list[VerifiedCitation] = []
    fact_checks: list[ClaimReviewFinding] = []
    same_claim_reviews: list[int] = []
    failed_steps: list[str] = []
    limitations: list[str] = []
    result: CheckResult | None = None

    @property
    def has_text(self) -> bool:
        """Whether the citizen pasted text, by the contract's MIN_TEXT_CHARS rule."""
        return len((self.job.request.text or "").strip()) >= MIN_TEXT_CHARS

    @property
    def question(self) -> str:
        """The masked question: text, else page, transcript, OCR text, link or id."""
        request = self.job.request
        if self.has_text:
            return request.text or ""
        link = str(request.url or "")
        spoken = self.page_text or self.transcript or self.image_text
        return spoken or link or request.audio_id or ""

    def with_message(
        self,
        status: NotAVerdict,
        message: str,
        *,
        out_of_scope_code: OutOfScopeCode | None = None,
        limitation: tuple[LimitationCode, str] | None = None,
    ) -> CheckResult:
        """Build a non-verdict result with a diagnostic message.

        Args:
            status: needs_clarification, out_of_scope or technical_failure.
            message: diagnostic text for internal use.
            out_of_scope_code: what is not handled, for out_of_scope.
            limitation: the code and text explaining why, if any.

        Returns:
            The result.
        """
        failed = status == "technical_failure"
        return CheckResult(
            check_id=self.check_id,
            status=status,
            message=message,
            failure_code=TECHNICAL_FAILURE_CODE if failed else None,
            out_of_scope_code=out_of_scope_code,
            limitations=[limitation[1]] if limitation else [],
            limitation_codes=[limitation[0]] if limitation else [],
            corpus_version=self.corpus_version,
        )

    def technical_failure(
        self,
        code: FailureCode = TECHNICAL_FAILURE_CODE,
        message: str = TECHNICAL_FAILURE_MESSAGE,
    ) -> CheckResult:
        """Build the technical-failure result: no claims, a message instead.

        Args:
            code: why the check failed; the model provider by default.
            message: diagnostic text, never shown to citizens.

        Returns:
            The coded failure with diagnostic text.
        """
        return CheckResult(
            check_id=self.check_id,
            status="technical_failure",
            message=message,
            failure_code=code,
            corpus_version=self.corpus_version,
        )

    def final_result(self) -> CheckResult:
        """The answer, or a technical failure when no step produced one.

        Returns:
            The result, with the transcript of an audio input.
        """
        result = self.result or self.technical_failure()
        return result.model_copy(update={"transcript": self.transcript})
