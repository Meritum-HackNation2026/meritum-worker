"""Citation precision: a judge model checks each fragment's stance (worker#170)."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import Citation, ClaimResult, Source
from meritum_core.shared.llm import LlmResult, Prompt
from pydantic import BaseModel, HttpUrl
from tests.llm_fakes import USAGE, NoTools

from meritum_worker.observability import (
    CaseRun,
    GoldenCase,
    judge_citations,
    score_runs,
)
from meritum_worker.observability.constants import (
    CITATION_JUDGE_INSTRUCTIONS,
    JUDGE_UNKNOWN_DATE,
)

type Make[T] = Callable[..., T]

PUBLISHED = datetime(2025, 9, 15, tzinfo=UTC)
RIGHT = "Minimalne wynagrodzenie wynosi 4806 zł."
WRONG = "Komunikat o zmianie godzin otwarcia urzędu."


class _Judge(NoTools):
    """Says a fragment is right when it holds the expected figure."""

    def __init__(self) -> None:
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.prompts.append(prompt)
        answer = output.model_validate({"correct": "4806" in prompt.data[2]})
        return LlmResult[T](output=answer, usage=USAGE)


def _cited(*fragments: str, published: datetime | None = PUBLISHED) -> ClaimResult:
    source = Source.model_construct(
        url=HttpUrl("https://www.gov.pl/web/rodzina"),
        title="Minimalne wynagrodzenie za pracę w 2026 r.",
        published_at=published,
    )
    citations = [
        Citation.model_construct(source=source, fragment=f, stance="supports")
        for f in fragments
    ]
    return ClaimResult.model_construct(
        claim="Płaca minimalna wynosi 4806 zł.",
        verdict="confirmed",
        citations=citations,
    )


def test_precision_is_the_share_of_fragments_the_judge_confirms(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    judge = _Judge()
    runs = [
        run(case(), result(claims=(_cited(RIGHT, WRONG),))),
        run(case(id="D-own-b"), result(claims=(_cited(RIGHT),))),
    ]
    assert asyncio.run(judge_citations(runs, judge)) == pytest.approx(0.6667)
    claim, stance, fragment = judge.prompts[0].data[:3]
    assert claim == "Płaca minimalna wynosi 4806 zł."
    assert stance == "potwierdza"
    assert fragment == RIGHT


def test_precision_without_citations_is_none(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    runs = [run(case(), result("out_of_scope"))]
    assert asyncio.run(judge_citations(runs, _Judge())) is None


def test_a_run_without_the_judge_has_no_precision(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    report = score_runs([run(case(), result("out_of_scope"))])
    assert report.citation_precision is None


def test_the_judge_sees_the_source_a_reader_sees_under_the_citation(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    judge = _Judge()
    asyncio.run(judge_citations([run(case(), result(claims=(_cited(RIGHT),)))], judge))
    assert judge.prompts[0].data[3:] == (
        "Minimalne wynagrodzenie za pracę w 2026 r.",
        "2025-09-15",
        "https://www.gov.pl/web/rodzina",
    )


def test_a_source_without_a_date_is_told_to_the_judge_as_unknown(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    judge = _Judge()
    cited = _cited(RIGHT, published=None)
    asyncio.run(judge_citations([run(case(), result(claims=(cited,)))], judge))
    assert judge.prompts[0].data[4] == JUDGE_UNKNOWN_DATE


def test_the_judge_knows_the_rules_the_stance_call_follows() -> None:
    assert "kwotą brutto" in CITATION_JUDGE_INSTRUCTIONS
    assert "z tytułu i daty źródła" in CITATION_JUDGE_INSTRUCTIONS
    assert "z innego roku" in CITATION_JUDGE_INSTRUCTIONS
