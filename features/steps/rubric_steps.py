"""Steps of the answer rubric scenarios (worker#252); they call only the public API."""

import asyncio
import math
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ClaimResult
from meritum_core.shared.llm import LlmResult, Prompt
from pydantic import BaseModel
from tests.llm_fakes import USAGE, NoTools

from meritum_worker.observability import (
    CaseRun,
    GoldenCase,
    judge_rubric,
    load_rubric,
    score_runs,
    with_judgements,
)
from meritum_worker.observability.constants import DEFAULT_RUBRIC_FILE

RUBRIC = load_rubric(Path(__file__).resolve().parents[2] / DEFAULT_RUBRIC_FILE)
DENIAL = "Nie twierdzi ani nie sugeruje, że zmiany albo zdarzenia nie było"


class _Judge(NoTools):
    """Fails the denial check when the answer denies; the first J vote fails."""

    def __init__(self) -> None:
        self.j_votes = 0

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        checks = prompt.instructions.split("\n")[1:]
        is_j = any("indeksu Google" in check for check in checks)
        self.j_votes += is_j
        denies = "zmiany nie było" in prompt.data[2]
        statuses = [
            "not_met"
            if (denies and DENIAL in check) or (is_j and self.j_votes == 1)
            else "met"
            for check in checks
        ]
        answer = {
            "checks": [{"number": n, "status": s} for n, s in enumerate(statuses, 1)]
        }
        return LlmResult[T](output=output.model_validate(answer), usage=USAGE)


def _case(case_id: str, scenario: str, verdict: str, behavior: str) -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "id": case_id,
            "scenario": scenario,
            "origin": "own",
            "channel": "web",
            "text": "Czy od wczoraj w Pcimiu bilety są tylko w aplikacji?",
            "main_claim": "W Pcimiu bilety są tylko w aplikacji.",
            "expected_status": "done",
            "expected_verdict": verdict,
            "expected_behavior": behavior,
        }
    )


def _run(case: GoldenCase, explanation: str) -> CaseRun:
    claim = ClaimResult.model_construct(
        claim=case.main_claim, verdict=case.expected_verdict, explanation=explanation
    )
    result = CheckResult.model_construct(
        check_id=case.id, status="done", claims=[claim], corpus_version="none"
    )
    return CaseRun.model_construct(None, case=case, result=result, seconds=1.0)


@given(
    "przypadek scenariusza D z odpowiedzią wzorcową i wynik sprawdzenia, który"
    " mówi, że zmiany nie było"
)
def d_case_that_denies(context: Context) -> None:
    case = _case(
        "D-own-bilety",
        "D",
        "insufficient_evidence",
        "Mówi, że nie udało się potwierdzić, i nazywa regulamin sprzedaży biletów.",
    )
    context.runs = [_run(case, "Nie potwierdzono, więc zmiany nie było.")]


@when("meritum-eval ocenia przebieg z flagą --judge")
def judge_the_run(context: Context) -> None:
    rubrics = asyncio.run(judge_rubric(context.runs, _Judge(), RUBRIC, votes=2))
    context.report = with_judgements(score_runs(context.runs), rubrics=rubrics)


@then("kryterium „nie twierdzi, że zdarzenia nie było” jest niespełnione")
def denial_check_fails(context: Context) -> None:
    rubric = context.report.outcomes[0].rubric
    assert any(DENIAL in failed for failed in rubric.failed), rubric.failed


@then(
    "przypadek nie przechodzi rubryki, a raport podaje to kryterium przy id przypadku"
)
def case_fails_rubric(context: Context) -> None:
    case = context.report.outcomes[0]
    assert case.id == "D-own-bilety"
    assert case.rubric.passed == 0


@given(
    "przebieg z przypadkami scenariuszy A i J ocenionymi przez sędziego dwoma głosami"
)
def a_and_j_cases(context: Context) -> None:
    a = _case("A-own-bilety", "A", "false", "Nie. Podaje źródło z linkiem.")
    j = _case("J-own-bilety", "J", "false", "Tak, Demagog to sprawdził.")
    context.runs = [_run(a, "To nieprawda."), _run(j, "Demagog ocenił to jako fałsz.")]


@when("powstaje raport")
def report_is_made(context: Context) -> None:
    judge_the_run(context)


@then("każdy scenariusz ma rubric_pass_rate i rubric_score obok accuracy")
def scenarios_have_rubric(context: Context) -> None:
    for scenario in context.report.scenarios:
        assert scenario.accuracy is not None
        assert scenario.rubric_pass_rate is not None, scenario.scenario
        assert scenario.rubric_score is not None, scenario.scenario


@then("przypadek, w którym głosy się różnią, liczy się jako pół zaliczenia")
def split_vote_is_half(context: Context) -> None:
    by_letter = {s.scenario: s for s in context.report.scenarios}
    assert by_letter["A"].rubric_pass_rate == 1
    assert math.isclose(by_letter["J"].rubric_pass_rate, 1 / 2)
