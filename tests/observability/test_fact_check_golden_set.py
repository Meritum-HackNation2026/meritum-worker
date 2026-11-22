"""The fact-checking golden set validates and covers every kind (worker#170)."""

from pathlib import Path

import pytest

from meritum_worker.observability import GoldenSet, load_eval_cases

FACT_CHECKS = (
    Path(__file__).resolve().parents[2] / "evals" / "golden" / "fact-checks.json"
)
CATEGORIES = {
    "true",
    "false",
    "partial",
    "misleading",
    "numbers",
    "public_figure",
    "opinion",
    "fact_checked",
    "out_of_scope",
}
MIN_CASES = 60


@pytest.fixture(scope="module")
def golden() -> GoldenSet:
    return load_eval_cases(FACT_CHECKS)


def test_has_enough_cases_of_every_category(golden: GoldenSet) -> None:
    assert len(golden.root) >= MIN_CASES
    assert {case.category for case in golden.root} == CATEGORIES


def test_rated_cases_cite_the_fact_checker(golden: GoldenSet) -> None:
    rated = [case for case in golden.root if case.category == "fact_checked"]
    assert all(case.sources or case.acceptable_verdicts for case in rated), (
        "a rated claim names its rating or accepts an abstention"
    )


def test_alternatives_never_repeat_the_expected_verdict(golden: GoldenSet) -> None:
    for case in golden.root:
        assert case.expected_verdict not in case.acceptable_verdicts, case.id
