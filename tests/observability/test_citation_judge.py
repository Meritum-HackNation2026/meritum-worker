"""Citation precision: a judge model checks each fragment's stance (worker#170)."""

import asyncio
from collections.abc import Callable

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

type Make[T] = Callable[..., T]

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
        answer = output.model_validate({"correct": "4806" in prompt.data[-1]})
        return LlmResult[T](output=answer, usage=USAGE)


def _cited(*fragments: str) -> ClaimResult:
    source = Source.model_construct(url=HttpUrl("https://www.gov.pl/web/rodzina"))
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
    claim, stance, fragment = judge.prompts[0].data
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
