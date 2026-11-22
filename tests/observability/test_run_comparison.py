"""Two stored runs side by side: metric differences and cases that changed."""

from datetime import UTC, datetime, timedelta

import pytest
from meritum_core.checks.contracts import (
    EvalCaseResult,
    EvalMetrics,
    EvalRun,
    EvalScenarioScore,
    Verdict,
)

from meritum_worker.observability import compare_runs

T0 = datetime(2026, 11, 22, 12, tzinfo=UTC)


def _metrics(**changes: object) -> EvalMetrics:
    raw: dict[str, object] = {
        "cases": 2,
        "macro_f1": 0.5,
        "citation_coverage": 1.0,
        "citation_correctness": None,
        "abstention": 0.5,
        "robustness": None,
        "median_seconds": 3.0,
        "p95_seconds": 5.0,
        "max_seconds": 6.0,
        "input_tokens_per_check": 100.0,
        "output_tokens_per_check": 50.0,
        "cost_per_check_usd": 0.01,
        "cost_100_checks_usd": 1.0,
        "channel_consistency": None,
        "information_loop": None,
    }
    return EvalMetrics.model_validate(raw | changes)


def _case(case_id: str, predicted: Verdict, scenario: str = "A") -> EvalCaseResult:
    return EvalCaseResult(
        case_id=case_id,
        scenario=scenario,
        expected="false",
        predicted=predicted,
        outcome="correct" if predicted == "false" else "wrong_decisive",
        received_at=T0,
        answered_at=T0 + timedelta(seconds=1),
    )


def _run(run_id: str, metrics: EvalMetrics, *cases: EvalCaseResult) -> EvalRun:
    return EvalRun(
        id=run_id,
        case_set="golden",
        status="done",
        corpus_version="v1",
        started_at=T0,
        finished_at=T0 + timedelta(minutes=1),
        metrics=metrics,
        scenarios=(EvalScenarioScore(scenario="A", cases=2, correct=1, accuracy=0.5),),
        cases=cases,
    )


def test_metric_differences_are_after_minus_before() -> None:
    before = _run("a", _metrics(), _case("A-1", "false"))
    after = _run(
        "b", _metrics(macro_f1=0.75, median_seconds=2.0), _case("A-1", "false")
    )
    comparison = compare_runs(before, after)
    deltas = {d.metric: d.change for d in comparison.metrics}
    assert deltas["macro_f1"] == pytest.approx(0.25)
    assert deltas["median_seconds"] == pytest.approx(-1.0)
    assert deltas["cases"] == 0


def test_a_metric_missing_in_one_run_has_no_difference() -> None:
    before = _run("a", _metrics(abstention=None), _case("A-1", "false"))
    after = _run("b", _metrics(abstention=0.5), _case("A-1", "false"))
    comparison = compare_runs(before, after)
    [abstention] = [d for d in comparison.metrics if d.metric == "abstention"]
    assert abstention.before is None
    assert abstention.after == pytest.approx(0.5)
    assert abstention.change is None


def test_only_cases_with_another_outcome_are_listed() -> None:
    before = _run("a", _metrics(), _case("A-1", "false"), _case("A-2", "false"))
    after = _run("b", _metrics(), _case("A-1", "false"), _case("A-2", "confirmed"))
    comparison = compare_runs(before, after)
    [changed] = comparison.changed_cases
    assert (changed.case_id, changed.before, changed.after) == (
        "A-2",
        "correct",
        "wrong_decisive",
    )
    assert changed.predicted_before == "false"
    assert changed.predicted_after == "confirmed"


def test_a_case_in_one_run_only_is_listed_as_added_or_removed() -> None:
    before = _run("a", _metrics(), _case("A-1", "false"))
    after = _run("b", _metrics(), _case("A-1", "false"), _case("A-3", "false"))
    comparison = compare_runs(before, after)
    assert comparison.only_after == ("A-3",)
    assert comparison.only_before == ()


def test_a_run_without_metrics_cannot_be_compared() -> None:
    failed = EvalRun(
        id="f", case_set="golden", status="failed", corpus_version="v1", started_at=T0
    )
    good = _run("b", _metrics())

    with pytest.raises(ValueError, match="finished"):
        compare_runs(failed, good)
