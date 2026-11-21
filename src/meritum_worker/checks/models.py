"""What the `check` workflow carries between its steps.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from dataclasses import dataclass

from meritum_core.checks import CheckRecordRepository, CheckResult
from meritum_core.checks.contracts import ClaimResult, ModelUsage
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.llm import LlmPort
from pydantic import BaseModel, ConfigDict

from meritum_worker.checks.constants import (
    NO_CORPUS_VERSION,
    TECHNICAL_FAILURE_MESSAGE,
)


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
        result: the answer, once write_answer ran.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str
    job: CheckInput
    corpus_version: str = NO_CORPUS_VERSION
    models: list[ModelUsage] = []
    result: CheckResult | None = None

    @property
    def question(self) -> str:
        """The masked question: the text, else the link, else the audio id."""
        request = self.job.request
        return request.text or str(request.url or "") or request.audio_id or ""

    def technical_failure(self) -> CheckResult:
        """Build the technical-failure result: no claims, a message instead.

        Returns:
            The result channels show as „Problem techniczny”.
        """
        return CheckResult(
            check_id=self.check_id,
            status="technical_failure",
            message=TECHNICAL_FAILURE_MESSAGE,
            corpus_version=self.corpus_version,
        )

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
