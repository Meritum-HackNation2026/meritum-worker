"""What the `check` workflow carries between its steps.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, F-07, F-22
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from meritum_core.checks import CheckRecordRepository, CheckResult, InjectionEvent
from meritum_core.checks.constants import MIN_TEXT_CHARS
from meritum_core.checks.contracts import (
    CatalogEntry,
    ClaimDateSource,
    FailureCode,
    ModelUsage,
)
from meritum_core.checks.transcription import TranscriptionPort
from meritum_core.corpus import CorpusSearchPort, RankedPassage, RerankerPort
from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.corpus.web_search import WebSearchPort
from meritum_core.evidence.models import SourceDocument
from meritum_core.jobs.contracts import CheckInput
from meritum_core.notifications import NotificationRepository
from meritum_core.security.injection import InjectionDetectorPort
from meritum_core.security.pii import PiiGatePort
from meritum_core.shared.blobs import BlobStore
from meritum_core.shared.llm import LlmPort
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.checks.constants import (
    NO_CORPUS_VERSION,
    TECHNICAL_FAILURE_CODE,
    TECHNICAL_FAILURE_MESSAGE,
)
from meritum_worker.evidence import (
    AssessedCitation,
    VerifiedCitation,
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
        pages: the SSRF-safe page fetcher, from the core fetching factory.
        pii: the personal-data masking gate for pages, transcripts and web queries.
        blobs: the store holding uploaded recordings (ADR-31).
        transcriber: transcription over the same store (ADR-30).
        notifications: the inbox the end of a long check is announced in.
        web_search: live web search, limited to catalogue domains.
        injection: the detector pages found by web search are scanned with.
        catalog: the loaded source catalogue.
        corpus: hybrid search of the corpus snapshots, called in process (ADR-32).
        reranker: the gate passages pass before stance assessment (ADR-35).
        corpus_version: the snapshot checks search; NO_CORPUS_VERSION skips it.

    Features:
        US-SPR-01, US-SPR-02, US-SPR-04, US-SPR-07, US-SPR-11, US-OBS-01, US-OBS-07,
        US-POW-01, US-KOR-04, F-06, F-08, F-09, F-12, F-13, F-22
    """

    llm: LlmPort
    records: CheckRecordRepository
    pages: PageFetcherPort
    pii: PiiGatePort
    blobs: BlobStore
    transcriber: TranscriptionPort
    notifications: NotificationRepository
    web_search: WebSearchPort
    injection: InjectionDetectorPort
    catalog: tuple[CatalogEntry, ...]
    corpus: CorpusSearchPort
    reranker: RerankerPort
    corpus_version: str


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
        skipped_steps: step codes that had nothing to do for this input.
        claims: the dated claims to answer, at most MAX_CLAIMS_PER_CHECK.
        evidence: source documents found for the claims, each past quarantine.
        passages: reranked corpus passages per fact, keyed by the claim text.
        assessed: citations the stance calls proposed, per fact.
        citations: citations past the verbatim check, per fact.
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
    skipped_steps: list[str] = []
    claims: list[ExtractedClaim] = []
    evidence: list[SourceDocument] = []
    passages: dict[str, list[RankedPassage]] = {}
    assessed: list[AssessedCitation] = []
    citations: list[VerifiedCitation] = []
    limitations: list[str] = []
    result: CheckResult | None = None

    @property
    def has_text(self) -> bool:
        """Whether the citizen pasted text, by the contract's MIN_TEXT_CHARS rule."""
        return len((self.job.request.text or "").strip()) >= MIN_TEXT_CHARS

    @property
    def question(self) -> str:
        """The masked question: text, else page, transcript, link or audio id."""
        request = self.job.request
        if self.has_text:
            return request.text or ""
        link = str(request.url or "")
        return self.page_text or self.transcript or link or request.audio_id or ""

    def with_message(self, status: NotAVerdict, message: str) -> CheckResult:
        """Build a non-verdict result with a diagnostic message.

        Args:
            status: needs_clarification, out_of_scope or technical_failure.
            message: diagnostic text for internal use.

        Returns:
            The result.
        """
        failed = status == "technical_failure"
        return CheckResult(
            check_id=self.check_id,
            status=status,
            message=message,
            failure_code=TECHNICAL_FAILURE_CODE if failed else None,
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
