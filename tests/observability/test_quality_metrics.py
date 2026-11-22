"""Fact-checking quality metrics on runs counted by hand (worker#170)."""

from collections.abc import Callable

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ClaimResult, ClaimReviewContext
from pydantic import HttpUrl

from meritum_worker.observability import CaseRun, GoldenCase, score_runs

type Make[T] = Callable[..., T]
type Case = Make[GoldenCase]
type Claim = Make[ClaimResult]
type Result = Make[CheckResult]
type Run = Make[CaseRun]


def _source(url: str) -> dict[str, str]:
    return {"url": url, "publisher": "Urząd", "title": "Komunikat", "quote": "Tak."}


def test_acceptable_alternative_is_a_correct_outcome(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    golden = case(expected_verdict="misleading", acceptable_verdicts=["false"])
    report = score_runs([run(golden, result(claims=(claim("false"),)))])
    assert report.outcomes[0].outcome == "correct"
    assert report.outcomes[0].predicted == "false"
    assert report.accuracy == pytest.approx(1.0)
    assert report.macro_f1 == pytest.approx(1.0)


def test_strict_macro_f1_counts_the_label_the_pipeline_gave(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    golden = case(expected_verdict="misleading", acceptable_verdicts=["false"])
    report = score_runs([run(golden, result(claims=(claim("false"),)))])
    assert report.macro_f1 == pytest.approx(1.0)
    assert report.macro_f1_strict == pytest.approx(0.0)


def test_accuracy_is_the_share_of_correct_cases(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    runs = [
        run(case(), result(claims=(claim("insufficient_evidence"),))),
        run(case(id="D-own-b"), result(claims=(claim("false"),))),
    ]
    assert score_runs(runs).accuracy == pytest.approx(0.5)


def test_abstention_rate_counts_every_answer_without_a_decision(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    runs = [
        run(case(), result(claims=(claim("insufficient_evidence"),))),
        run(case(id="D-own-b"), result(claims=(claim("not_verifiable"),))),
        run(case(id="D-own-c"), result(claims=(claim("false"),))),
        run(case(id="D-own-d"), result("technical_failure")),
    ]
    assert score_runs(runs).abstention_rate == pytest.approx(0.6667)


def test_source_recall_is_the_mean_share_of_expected_hosts_cited(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    two = case(
        expected_verdict="false",
        sources=[_source("https://www.gov.pl/a"), _source("https://pkw.gov.pl/b")],
    )
    one = case(id="D-own-b", sources=[_source("https://isap.sejm.gov.pl/x")])
    none = case(id="D-own-c")
    runs = [
        run(two, result(claims=(claim("false", cites=("https://gov.pl/inna",)),))),
        run(one, result(claims=(claim("insufficient_evidence"),))),
        run(none, result(claims=(claim("insufficient_evidence"),))),
    ]
    assert score_runs(runs).citation_recall == pytest.approx(0.25)


def test_fact_check_rating_counts_as_a_found_source_and_a_hit(
    case: Case, claim: Claim, result: Result, run: Run
) -> None:
    rated = "https://demagog.org.pl/wypowiedzi/x/"
    golden = case(
        expected_verdict="false",
        category="fact_checked",
        sources=[_source(rated)],
    )
    review = ClaimReviewContext.model_construct(url=HttpUrl(rated))
    found = claim("false").model_copy(update={"claim_reviews": [review]})
    missed = case(id="D-own-b", category="fact_checked", sources=[_source(rated)])
    runs = [
        run(golden, result(claims=(found,))),
        run(missed, result(claims=(claim("insufficient_evidence"),))),
        run(case(id="D-own-c"), result(claims=(claim("insufficient_evidence"),))),
    ]
    report = score_runs(runs)
    assert report.fact_check_hit_rate == pytest.approx(0.5)
    assert report.citation_recall == pytest.approx(0.5)


def test_quality_metrics_without_applicable_cases_are_none(
    case: Case, result: Result, run: Run
) -> None:
    report = score_runs([run(case(), result("out_of_scope"))])
    assert report.citation_recall is None
    assert report.fact_check_hit_rate is None
    assert report.abstention_rate is None
