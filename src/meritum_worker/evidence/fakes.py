"""In-process fakes of the evidence slice for tests and behave: recorded model answers.

Features:
    US-ZRD-01, US-ZRD-04, F-15, F-16
"""

from collections.abc import Mapping
from datetime import datetime

from meritum_core.checks.contracts import Source, SourceTier
from meritum_core.evidence import SourceDocument
from meritum_core.shared.llm import LlmResult, LlmToolResult, Prompt, Tool
from meritum_core.shared.llm.errors import ProviderUnavailableError
from pydantic import BaseModel

from meritum_worker.evidence.constants import FAKE_FETCHED_AT, FAKE_USAGE
from meritum_worker.evidence.models import StanceJudgement


class RecordedLlm:
    """Answers the stance call per source text and any other call by its model.

    Args:
        stances: the recorded stance answer for each source text.
        answers: the recorded answer for each other output model.

    Attributes:
        prompts: every prompt, in order.

    Features:
        US-ZRD-01, US-ZRD-04, F-15, F-16
    """

    def __init__(
        self, stances: Mapping[str, StanceJudgement], *answers: BaseModel
    ) -> None:
        self._stances = dict(stances)
        self._answers = {type(answer).__name__: answer for answer in answers}
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        """Return the recorded answer; the source text is the last data item.

        Args:
            prompt: the prompt, recorded.
            output: the model to answer with.

        Returns:
            The recorded answer.

        Raises:
            ProviderUnavailableError: nothing is recorded for the call.
        """
        self.prompts.append(prompt)
        recorded = (
            self._stances.get(prompt.data[-1])
            if output is StanceJudgement
            else self._answers.get(output.__name__)
        )
        if recorded is None:
            raise ProviderUnavailableError(output.__name__)
        return LlmResult[T](
            output=output.model_validate(recorded.model_dump()), usage=FAKE_USAGE
        )

    @staticmethod
    async def complete_with_tools[T: BaseModel](
        prompt: Prompt, output: type[T], tools: tuple[Tool, ...]
    ) -> LlmToolResult[T]:
        """Fail: no evidence step offers the model tools.

        Args:
            prompt: the prompt.
            output: the model to answer with.
            tools: the tools offered.

        Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(prompt, output, tools)


def document(  # ruff: ignore[too-many-arguments]  # a fake source names every field a test varies
    source_id: str,
    text: str,
    *,
    publisher_id: str = "gus",
    domain: str = "stat.gov.pl",
    tier: SourceTier = "primary",
    published_at: datetime | None = None,
) -> SourceDocument:
    """Build a corpus document with database metadata for a test.

    Args:
        source_id: the document id.
        text: the full source text.
        publisher_id: the catalogue publisher id.
        domain: the catalogue domain.
        tier: primary or secondary.
        published_at: the publication date.

    Returns:
        The document.

    Features:
        US-ZRD-01, F-16
    """
    source = Source(
        id=source_id,
        title=f"Dokument {source_id}",
        publisher=publisher_id.upper(),
        publisher_id=publisher_id,
        url=f"https://{domain}/{source_id}",
        domain=domain,
        kind="dane_publiczne" if tier == "primary" else "fact_check",
        tier=tier,
        published_at=published_at,
        fetched_at=FAKE_FETCHED_AT,
    )
    return SourceDocument(source=source, text=text)
