"""Case outcome by the main claim and macro-F1, counted by hand (US-OBS-04)."""

from collections.abc import Callable
from typing import get_args

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ClaimResult

from meritum_worker.observability import GoldenCase, case_outcome, macro_f1
from meritum_worker.observability.constants import OUTCOME_ORDER
from meritum_worker.observability.report import Outcome

type Make[T] = Callable[..., T]
type Case = Make[GoldenCase]
type Claim = Make[ClaimResult]
type Result = Make[CheckResult]


@pytest.mark.parametrize(
    ("expected", "predicted", "outcome"),
    [
        ("false", "false", "correct"),
        ("false", "confirmed", "wrong_decisive"),
        ("false", "insufficient_evidence", "wrong_abstention"),
        ("insufficient_evidence", "not_verifiable", "wrong_abstention"),
        ("insufficient_evidence", "misleading", "wrong_decisive"),
    ],
)
def test_outcome_of_a_verdict(  # ruff: ignore[too-many-arguments, too-many-positional-arguments]  # parametrize values plus fixtures
    expected: str,
    predicted: str,
    outcome: str,
    case: Case,
    claim: Claim,
    result: Result,
) -> None:
    golden = case(expected_verdict=expected)
    found = case_outcome(golden, result(claims=(claim(predicted),)))
    assert found == (predicted, outcome)


def test_state_instead_of_verdict_is_a_non_verdict(case: Case, result: Result) -> None:
    found = case_outcome(case(), result("technical_failure"))
    assert found == ("technical_failure", "non_verdict")


def test_expected_state_met_is_correct(case: Case, result: Result) -> None:
    golden = case(expected_status="out_of_scope", expected_verdict=None)
    assert case_outcome(golden, result("out_of_scope"))[1] == "correct"


def test_only_claims_matching_the_main_claim_count(
    case: Case, claim: Claim, result: Result
) -> None:
    other = claim("confirmed", text="Pcim ma nowego burmistrza.")
    main = claim("insufficient_evidence", text="w pcimiu jest NOWA strefa parkowania")
    assert case_outcome(case(), result(claims=(other, main)))[1] == "correct"


def test_several_main_claims_keep_the_worst_outcome(
    case: Case, claim: Claim, result: Result
) -> None:
    claims = (claim("insufficient_evidence"), claim("not_verifiable"), claim("false"))
    found = case_outcome(case(), result(claims=claims))
    assert found == ("false", "wrong_decisive")


def test_without_a_matching_claim_every_claim_counts(
    case: Case, claim: Claim, result: Result
) -> None:
    claims = (claim("not_verifiable", text="Zupełnie inne twierdzenie."),)
    assert case_outcome(case(), result(claims=claims))[1] == "wrong_abstention"


def test_macro_f1_counted_by_hand() -> None:
    pairs = [
        ("false", "false"),
        ("false", "technical_failure"),
        ("confirmed", "confirmed"),
        ("confirmed", "false"),
    ]
    # false: tp 1, fp 1, fn 1 -> 1/2; confirmed: tp 1, fn 1 -> 2/3; non_verdict: 0.
    assert macro_f1(pairs) == pytest.approx((1 / 2 + 2 / 3 + 0) / 3)


def test_wrong_states_fall_into_one_error_class() -> None:
    pairs = [
        ("out_of_scope", "technical_failure"),
        ("needs_clarification", "out_of_scope"),
    ]
    # out_of_scope, needs_clarification and non_verdict all score 0.
    assert macro_f1(pairs) == pytest.approx(0)


def test_met_expected_state_is_its_own_class() -> None:
    pairs = [("out_of_scope", "out_of_scope"), ("false", "technical_failure")]
    # Class F1 scores are 1 for out_of_scope, 0 for false and for non_verdict.
    assert macro_f1(pairs) == pytest.approx(1 / 3)


def test_macro_f1_without_cases_is_zero() -> None:
    assert macro_f1([]) == pytest.approx(0)


def test_outcome_order_names_every_outcome() -> None:
    assert set(OUTCOME_ORDER) == set(get_args(Outcome.__value__))
