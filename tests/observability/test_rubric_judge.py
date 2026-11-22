"""Answer rubric: a judge model scores the answer text per scenario (worker#252)."""

import asyncio
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import Citation, ClaimResult, Source
from meritum_core.shared.llm import LlmResult, Prompt, ProviderUnavailableError
from pydantic import BaseModel, HttpUrl
from tests.llm_fakes import USAGE, NoTools

from meritum_worker.observability import (
    CaseRun,
    EvalReport,
    GoldenCase,
    judge_rubric,
    load_rubric,
    score_runs,
    with_judgements,
)
from meritum_worker.observability.constants import DEFAULT_RUBRIC_FILE

type Make[T] = Callable[..., T]

ROOT = Path(__file__).resolve().parents[2]
RUBRIC = load_rubric(ROOT / DEFAULT_RUBRIC_FILE)


class _Judge(NoTools):
    """Answers each call with the next list of statuses, one per check."""

    def __init__(self, *votes: tuple[str, ...] | Exception) -> None:
        self._votes: Iterator[tuple[str, ...] | Exception] = iter(votes)
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.prompts.append(prompt)
        vote = next(self._votes)
        if isinstance(vote, Exception):
            raise vote
        checks = [
            {"number": n, "status": s, "reason": f"powód {n}"}
            for n, s in zip(count(1), vote, strict=False)
        ]
        answer = output.model_validate({"checks": checks})
        return LlmResult[T](output=answer, usage=USAGE)


def _d_checks(*statuses: str) -> tuple[str, ...]:
    # D has two common checks and three of its own.
    assert len(statuses) == len(RUBRIC.checks("D"))
    return statuses


MET = _d_checks("met", "met", "met", "met", "met")
DENIES = _d_checks("met", "met", "met", "met", "not_met")


def _judged(runs: list[CaseRun], judge: _Judge, votes: int = 2) -> EvalReport:
    rubrics = asyncio.run(judge_rubric(runs, judge, RUBRIC, votes=votes))
    return with_judgements(score_runs(runs), rubrics=rubrics)


def test_every_scenario_has_its_rubric() -> None:
    for scenario in "ABCDEFGHIJ":
        own = RUBRIC.checks(scenario)  # type: ignore[arg-type]
        assert own[: len(RUBRIC.common)] == RUBRIC.common
        assert len(own) > len(RUBRIC.common), scenario


def test_case_fails_the_rubric_when_one_check_is_not_met(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    report = _judged([run(case(), result())], _Judge(DENIES, DENIES))
    scored = report.outcomes[0].rubric
    assert scored is not None
    assert scored.passed == 0
    assert scored.score == pytest.approx(0.8)
    assert scored.failed == (f"{RUBRIC.checks('D')[-1]} (powód 5)",)
    assert report.scenarios[0].rubric_pass_rate == 0
    assert report.rubric_pass_rate == 0


def test_split_votes_count_as_half_a_pass(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    report = _judged([run(case(), result())], _Judge(MET, DENIES))
    assert report.scenarios[0].rubric_pass_rate == pytest.approx(0.5)
    assert report.rubric_score == pytest.approx(0.9)


def test_checks_that_do_not_apply_are_left_out_and_missing_ones_fail(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    na = _d_checks("met", "met", "not_applicable", "met", "met")
    report = _judged([run(case(), result())], _Judge(na, ("met",)))
    scored = report.outcomes[0].rubric
    assert scored is not None
    assert scored.score == pytest.approx((1 + 0.2) / 2)
    assert scored.passed == pytest.approx(0.5)


def test_a_failed_judge_call_drops_the_vote_not_the_run(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    down = ProviderUnavailableError("judge down")
    report = _judged([run(case(), result())], _Judge(down, MET))
    scored = report.outcomes[0].rubric
    assert scored is not None
    assert scored.passed == 1
    assert len(scored.votes) == 1


def test_the_judge_reads_the_rubric_model_answer_and_the_visible_answer(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    source = Source.model_construct(
        url=HttpUrl("https://demagog.org.pl/wypowiedzi/pcim/"),
        title="Bilety w Pcimiu",
        publisher="Demagog",
        published_at=datetime(2026, 11, 2, tzinfo=UTC),
    )
    cited = Citation.model_construct(
        source=source, fragment="Bilety są w kioskach.", stance="refutes"
    )
    claim = ClaimResult.model_construct(
        claim="W Pcimiu bilety są tylko w aplikacji.",
        verdict="insufficient_evidence",
        explanation="Nie znaleziono komunikatu przewoźnika.",
        citations=[cited],
    )
    judge = _Judge(MET)
    _judged([run(case(), result(claims=(claim,)))], judge, votes=1)
    prompt = judge.prompts[0]
    assert RUBRIC.checks("D")[-1] in prompt.instructions
    question, model_answer, answer = prompt.data
    assert question == case().text
    assert model_answer == case().expected_behavior
    shown = json.loads(answer)
    quoted = shown["claims"][0]["citations"][0]
    assert quoted["source"]["title"] == "Bilety w Pcimiu"
    assert quoted["source"]["published_at"].startswith("2026-11-02")
    assert "check_id" not in shown


def test_a_repeat_is_judged_next_to_the_first_answer(
    case: Make[GoldenCase], result: Make[CheckResult], run: Make[CaseRun]
) -> None:
    first = case(id="H-own-a", scenario="H")
    again = case(
        id="H-own-b",
        scenario="H",
        channel="discord",
        variant="other_channel",
        related_case="H-own-a",
    )
    h_met = ("met",) * len(RUBRIC.checks("H"))
    judge = _Judge(h_met, h_met)
    runs = [run(first, result()), run(again, result(check_id="check-2"))]
    _judged(runs, judge, votes=1)
    assert len(judge.prompts[0].data) == 3
    assert len(judge.prompts[1].data) == 4


def test_reports_from_before_the_rubric_still_load() -> None:
    old = ROOT / "evals" / "reports" / "fact-checks-2026-11-22-7.json"
    report = EvalReport.model_validate_json(old.read_text(encoding="utf-8"))
    assert report.rubric_pass_rate is None
    assert report.outcomes[0].rubric is None
